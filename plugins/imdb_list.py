import bs4
import json
from utils.base_plugin import ListScraper
from utils.browser import HeadlessBrowser

LD_JSON = 'script[type="application/ld+json"]'

class IMDBList(ListScraper):

    _alias_ = 'imdb_list'

    def get_list(list_id, config=None):
        config = config or {}
        with HeadlessBrowser() as browser:
            html = browser.get(f'https://www.imdb.com/list/{list_id}', wait_selector=LD_JSON)
            if html is None:
                return None
            soup = bs4.BeautifulSoup(html, 'html.parser')

            # Check if elements exist before accessing .text
            header_tag = soup.find('h1')
            json_script = soup.find("script", {"type": "application/ld+json"})

            if not header_tag or not json_script:
                return None

            list_name = header_tag.text

            # Safe check for description
            desc_tag = soup.find("div", {"class": "list-description"})
            description = desc_tag.text if desc_tag else ""

            ld_json = json.loads(json_script.text)
            movies = []
            for row in ld_json["itemListElement"]:
                url_parts = row["item"]["url"].split("/")
                url_parts = [p for p in url_parts if p!=""]

                release_year = None
                if config.get("add_release_year", False):
                    # Get release_date
                    item_html = browser.get(row["item"]["url"], wait_selector=LD_JSON)
                    if item_html:
                        soup_item = bs4.BeautifulSoup(item_html, 'html.parser')
                        item_script = soup_item.find("script", {"type": "application/ld+json"})
                        if item_script:
                            movie_json = json.loads(item_script.text)
                            release_year = movie_json.get("datePublished", "").split("-")[0]

                movies.append({
                    "title": row["item"]["name"],
                    "release_year": release_year,
                    "media_type": row["item"]["@type"],
                    "imdb_id": url_parts[-1]
                })

        return {'name': list_name, 'items': movies, "description": description}
