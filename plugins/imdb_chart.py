import bs4
from utils.base_plugin import ListScraper
from utils.browser import HeadlessBrowser
from utils import imdb_datasets
import json

NEXT_DATA = 'script#__NEXT_DATA__'

class IMDBChart(ListScraper):

    _alias_ = 'imdb_chart'

    def get_list(list_id, config=None):
        # Charts derivable from the official IMDb datasets (top, toptv) need no scraping
        result = imdb_datasets.get_chart(list_id.strip('/'))
        if result is not None:
            return result

        with HeadlessBrowser() as browser:
            html = browser.get(f'https://www.imdb.com/chart/{list_id}', wait_selector=NEXT_DATA)
            if html is None:
                return None
            soup = bs4.BeautifulSoup(html, 'html.parser')

            # Check if IMDb blocked the request or returned an empty/challenge page
            title_tag = soup.find('title')
            data_tag = soup.find('script', id='__NEXT_DATA__')
            if not title_tag or not data_tag:
                return None

            list_name = title_tag.text
            description_tag = soup.find('meta', property='og:description')
            description = description_tag['content'] if description_tag else ""
            movies = []

            data = json.loads(data_tag.text)

            for movie in next(iter(data["props"]["pageProps"]["pageData"].values()))["edges"]:
                movie = movie["node"]
                if "titleText" not in movie:
                    # Get item details
                    item_html = browser.get(f'https://www.imdb.com/title/{movie["release"]["titles"][0]["id"]}', wait_selector=NEXT_DATA)
                    if not item_html:
                        continue
                    item_soup = bs4.BeautifulSoup(item_html, 'html.parser')

                    item_script = item_soup.find('script', id='__NEXT_DATA__')
                    if not item_script:
                        continue

                    item_data = json.loads(item_script.text)
                    movie = item_data["props"]["pageProps"]["aboveTheFoldData"]

                title = movie["titleText"]["text"]

                release_year = None
                if movie["releaseYear"] is not None:
                    release_year = movie["releaseYear"]["year"]

                media_type = movie["titleType"]["id"]
                imdb_id = movie["id"]

                movies.append({'title': title, 'release_year': release_year, "media_type": media_type, "imdb_id": imdb_id})
        return {'name': list_name, 'items': movies, "description": description}
