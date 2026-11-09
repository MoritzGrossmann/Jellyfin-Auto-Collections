from loguru import logger
from playwright.sync_api import sync_playwright, Error as PlaywrightError

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0'


class HeadlessBrowser:
    """Small context manager around a headless Chromium (playwright) for pages
    that don't answer plain `requests` calls (e.g. IMDb's bot protection
    returns HTTP 202 without content)."""

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            user_agent=USER_AGENT,
            locale='en-US',
            extra_http_headers={'Accept-Language': 'en-US'},
        )
        self._page = self._context.new_page()
        return self

    def __exit__(self, *exc):
        self._context.close()
        self._browser.close()
        self._playwright.stop()

    def get(self, url, wait_selector=None, timeout=30000):
        """Loads `url` and returns the rendered HTML, or None on failure.

        wait_selector: CSS selector that must be present in the DOM (used to
        wait until a JS challenge has been passed and the real page is loaded).
        """
        try:
            self._page.goto(url, wait_until='domcontentloaded', timeout=timeout)
            if wait_selector:
                self._page.wait_for_selector(wait_selector, state='attached', timeout=timeout)
            return self._page.content()
        except PlaywrightError as e:
            logger.warning(f"Could not load {url} with headless browser: {e}")
            return None
