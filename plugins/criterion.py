import json
from utils.base_plugin import ListScraper
import bs4
import requests
from loguru import logger
from utils import imdb_datasets
#from requests_cache import CachedSession, FileCache

class CriterionChannel(ListScraper):

    _alias_ = 'criterion_channel'

    def get_list(list_id, config=None):
        r = requests.get(f"https://www.criterionchannel.com/{list_id}")
        soup = bs4.BeautifulSoup(r.text, 'html.parser')

        list_name = soup.find("h1", class_="collection-title").text.strip()
        description = soup.find("div", class_="collection-description").text.strip()

        items = []
        for item in soup.find_all("li", class_="js-collection-item"):
            title = item.find("strong").text.strip()
            year = item.find("p")
            if year is not None and "•" in year.text:
                year = year.text.split("•")[1].strip()
            items.append({
                "title": title,
                "release_year": year,
                "media_type": "movie"
            })
        # The page has no ids: look them up so matching works with localized titles
        imdb_datasets.resolve_imdb_ids(items)
        return {'name': list_name, 'items': items, "description": description}
