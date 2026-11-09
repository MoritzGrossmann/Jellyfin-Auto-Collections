from loguru import logger
from utils.base_plugin import ListScraper
from utils import imdb_datasets


class IMDBChart(ListScraper):

    _alias_ = 'imdb_chart'

    def get_list(list_id, config=None):
        # Charts derivable from the official IMDb datasets (top, toptv) need no scraping
        result = imdb_datasets.get_chart(list_id.strip('/'))
        if result is not None:
            return result

        # All other charts would need a headless browser, which is no longer supported
        logger.warning(f"IMDb chart '{list_id}' is not available from the IMDb datasets and scraping it requires a headless browser, which is not supported - skipping")
        return None
