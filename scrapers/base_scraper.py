# scrapers/base_scraper.py
"""
Base HTTP scraper with rate-limiting, retry, and session management.
All team scrapers inherit from this.
"""
import time
import random
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config.settings import settings

logger = logging.getLogger(__name__)


class BaseScraper:
    def __init__(
        self,
        delay_min: float = settings.SCRAPE_DELAY_MIN,
        delay_max: float = settings.SCRAPE_DELAY_MAX,
        max_retries: int = 3,
    ):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def _sleep(self):
        t = random.uniform(self.delay_min, self.delay_max)
        logger.debug(f"Sleeping {t:.1f}s")
        time.sleep(t)

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET with retry + polite delay."""
        for attempt in range(1, self.max_retries + 1):
            try:
                self._sleep()
                r = self.session.get(url, timeout=20, **kwargs)
                r.raise_for_status()
                logger.info(f"GET {url} → {r.status_code}")
                return r
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    wait = 30 * attempt
                    logger.warning(f"Rate limited. Waiting {wait}s (attempt {attempt})")
                    time.sleep(wait)
                elif e.response.status_code in (403, 404):
                    logger.warning(f"HTTP {e.response.status_code} — {url}")
                    raise
                else:
                    logger.warning(f"HTTP error attempt {attempt}: {e}")
                    if attempt == self.max_retries:
                        raise
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error attempt {attempt}: {e}")
                if attempt == self.max_retries:
                    raise
        raise RuntimeError(f"Failed after {self.max_retries} attempts: {url}")

    def soup(self, url: str, **kwargs) -> BeautifulSoup:
        """GET + parse with BeautifulSoup."""
        r = self.get(url, **kwargs)
        return BeautifulSoup(r.text, "lxml")
