"""Offline IMDb charts built from the official IMDb datasets
(https://developer.imdb.com/non-commercial-datasets/, free for personal and
non-commercial use). No scraping of imdb.com involved.

Only charts that can be derived from ratings/basics are supported
(IMDb's boxoffice, moviemeter, ... are not part of the datasets).
The ranking uses IMDb's published weighted-rating formula, so the result is
very close to, but not guaranteed identical with, the website's chart.
"""
import csv
import gzip
import json
import os
import re
import tempfile
import time
import unicodedata

import requests
from loguru import logger

BASE_URL = 'https://datasets.imdbws.com/'
CACHE_DIR = os.path.join(tempfile.gettempdir(), 'jellyfin-auto-collections-imdb')
CACHE_MAX_AGE = 24 * 3600  # datasets are refreshed daily by IMDb
MIN_VOTES = 25000          # IMDb requires 25000 votes for the Top 250 charts
POOL_MIN_VOTES = 1000      # titles used to estimate the mean rating

CHARTS = {
    'top': {
        'name': 'IMDb Top 250 Movies',
        'description': 'As rated by IMDb users (computed from the official IMDb datasets)',
        'types': {'movie'},
    },
    'toptv': {
        'name': 'IMDb Top 250 TV Shows',
        'description': 'As rated by IMDb users (computed from the official IMDb datasets)',
        'types': {'tvSeries', 'tvMiniSeries'},
    },
}


def _download(name):
    """Streams a dataset file and yields its decoded lines."""
    r = requests.get(BASE_URL + name, stream=True, timeout=60,
                     headers={'User-Agent': 'jellyfin-auto-collections'})
    r.raise_for_status()
    with gzip.GzipFile(fileobj=r.raw) as gz:
        for line in gz:
            yield line.decode('utf-8')


def _build_chart(types, limit=250):
    ratings = {}
    for row in csv.reader(_download('title.ratings.tsv.gz'), delimiter='\t'):
        if row[0] == 'tconst':
            continue
        votes = int(row[2])
        if votes >= POOL_MIN_VOTES:
            ratings[row[0]] = (float(row[1]), votes)

    titles = []
    for row in csv.reader(_download('title.basics.tsv.gz'), delimiter='\t', quoting=csv.QUOTE_NONE):
        if row[1] in types and row[0] in ratings:
            year = int(row[5]) if row[5].isdigit() else None
            titles.append((row[0], row[1], row[2], year))

    if not titles:
        return []
    mean = sum(ratings[t[0]][0] for t in titles) / len(titles)

    def weighted(t):
        rating, votes = ratings[t[0]]
        return votes / (votes + MIN_VOTES) * rating + MIN_VOTES / (votes + MIN_VOTES) * mean

    eligible = [t for t in titles if ratings[t[0]][1] >= MIN_VOTES]
    eligible.sort(key=weighted, reverse=True)
    return [
        {'title': t[2], 'release_year': t[3], 'media_type': t[1], 'imdb_id': t[0]}
        for t in eligible[:limit]
    ]


def _normalize(title):
    """Lowercase, strip accents and everything but letters/digits for tolerant title comparison."""
    title = unicodedata.normalize('NFKD', title or '')
    title = ''.join(c for c in title if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', title.lower())


def resolve_imdb_ids(items, types=('movie', 'tvMovie')):
    """Adds an 'imdb_id' to items that only have title + release_year.

    Looks the (original/primary title, year) pair up in the official IMDb datasets.
    The year may be off by one (list sources and IMDb often disagree); among several
    candidates the one with the most votes wins. Items that cannot be resolved are left
    untouched so the caller can fall back to title matching. Results (including misses)
    are cached on disk so the datasets are only downloaded for unseen items.
    """
    cache_file = os.path.join(CACHE_DIR, 'resolved_ids.json')
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, encoding='utf-8') as f:
                cache = json.load(f)
        except (OSError, ValueError):
            cache = {}

    def key_of(item):
        year = str(item.get('release_year') or '')
        return f"{_normalize(item.get('title'))}|{year}" if year.isdigit() and _normalize(item.get('title')) else None

    pending = {}
    for item in items:
        key = key_of(item)
        if key and not item.get('imdb_id') and key not in cache:
            pending[key] = item

    if pending:
        wanted = {k.split('|')[0] for k in pending}
        candidates = {}  # normalized title -> [(year, tconst)]
        try:
            logger.info(f"Resolving {len(pending)} IMDb ids from the official datasets (first run downloads ~150 MB)")
            for row in csv.reader(_download('title.basics.tsv.gz'), delimiter='\t', quoting=csv.QUOTE_NONE):
                if len(row) < 6 or row[1] not in types or not row[5].isdigit():
                    continue
                for name in {_normalize(row[2]), _normalize(row[3])}:
                    if name in wanted:
                        candidates.setdefault(name, []).append((int(row[5]), row[0]))
            needed = {tconst for lst in candidates.values() for _, tconst in lst}
            votes = {}
            for row in csv.reader(_download('title.ratings.tsv.gz'), delimiter='\t'):
                if row[0] in needed:
                    votes[row[0]] = int(row[2])
        except requests.RequestException as e:
            logger.warning(f"Could not download IMDb datasets to resolve ids: {e}")
            pending = {}

        for key in pending:
            name, year = key.split('|')
            year = int(year)
            best = None
            for tolerance in (0, 1):
                matches = [t for y, t in candidates.get(name, []) if abs(y - year) == tolerance]
                if matches:
                    best = max(matches, key=lambda t: votes.get(t, 0))
                    break
            cache[key] = best

        if pending:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f)

    resolved = 0
    for item in items:
        key = key_of(item)
        if key and not item.get('imdb_id') and cache.get(key):
            item['imdb_id'] = cache[key]
            resolved += 1
    logger.info(f"Resolved IMDb ids for {resolved}/{len(items)} items")
    return items


def get_chart(chart_id):
    """Returns {'name', 'items', 'description'} for a supported chart id, else None."""
    chart = CHARTS.get(chart_id)
    if chart is None:
        return None

    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f'{chart_id}.json')
    items = None
    if os.path.exists(cache_file) and time.time() - os.path.getmtime(cache_file) < CACHE_MAX_AGE:
        with open(cache_file, encoding='utf-8') as f:
            items = json.load(f)
    if items is None:
        logger.info(f"Building IMDb chart '{chart_id}' from the official datasets (first run downloads ~200 MB)")
        try:
            items = _build_chart(chart['types'])
        except requests.RequestException as e:
            logger.warning(f"Could not download IMDb datasets: {e}")
            return None
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(items, f)

    return {'name': chart['name'], 'items': items, 'description': chart['description']}
