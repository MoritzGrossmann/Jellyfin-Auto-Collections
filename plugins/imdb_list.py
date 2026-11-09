from loguru import logger
from utils.base_plugin import ListScraper


class IMDBList(ListScraper):

    _alias_ = 'imdb_list'

    def get_list(list_id, config=None):
        # IMDb list pages can't be fetched without a (headless) browser, which is no longer supported
        logger.warning(f"Plugin 'imdb_list' is disabled (requires a headless browser, which is not supported) - skipping list {list_id}")
        return None
