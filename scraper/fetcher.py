"""
Core fetcher — wraps StealthyFetcher with retry logic.
"""
import time
import logging
from scrapling.fetchers import StealthyFetcher

log = logging.getLogger(__name__)

REDDIT_BASE = "https://www.reddit.com"


def fetch_page(url: str, retries: int = 3, wait: float = 4.0):
    for attempt in range(1, retries + 1):
        try:
            page = StealthyFetcher.fetch(
                url,
                headless=True,
                network_idle=True,
            )
            if page.status == 200:
                return page
            log.warning("Attempt %d: HTTP %s for %s", attempt, page.status, url)
        except Exception as exc:
            log.warning("Attempt %d error: %s", attempt, exc)
        if attempt < retries:
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")
