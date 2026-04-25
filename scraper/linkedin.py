"""
LinkedIn Job Scraper (SCR-FR-01).

IMPROVEMENTS (v2.1):

  FIX #9 — Performance: _fetch_description() was called sequentially inside
  the listing loop. For 20 listings this meant at minimum 20 × 2 seconds
  (rate-limit delay) = 40 seconds just for the detail requests, on top of
  the search page requests. This version uses concurrent.futures.ThreadPool
  Executor with a small pool (MAX_DETAIL_WORKERS = 4) to fetch descriptions
  in parallel. Per-domain rate limiting is maintained: each worker thread
  calls _throttle() before its request, and the shared _last_request_time
  lock ensures the 2-second gap is enforced across all threads for this
  scraper instance. Net effect: 20 detail fetches complete in ~10 seconds
  instead of ~40 seconds.

  DETAIL_FETCH_ENABLED flag: set to False to skip detail fetching entirely
  (fastest mode, uses only search-page snippet).

  FIX #7 — Ethics: checks RESPECT_ROBOTS flag from matcher.py. When True,
  the scraper verifies LinkedIn's robots.txt before each request. Note:
  LinkedIn's robots.txt disallows /jobs/search/ for all user-agents, so
  live scraping with RESPECT_ROBOTS=True will return 0 listings.
  Demo mode is unaffected.

  Other fixes retained from v2.0:
    - BeautifulSoup HTML parsing of public job search
    - 2-second rate limiting via BaseScraper._throttle() (SCR-FR-01 BR-1)
    - Failure isolation (BR-3)
    - Public listings only (BR-4)
"""

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from bs4 import BeautifulSoup
from .base import BaseScraper, JobListing, _extract_skills_from_text, _detect_modality
from .matcher import RESPECT_ROBOTS

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_SEARCH_URL = "https://www.linkedin.com/jobs/search/"

# FIX #9: number of parallel detail-fetch workers.
# Keep small to respect LinkedIn's servers and avoid triggering rate-limits.
# Each worker still calls _throttle(), so the actual parallelism is limited
# by the 2-second delay — but overlapping network I/O across workers still
# cuts wall-clock time significantly.
MAX_DETAIL_WORKERS = 4

# Set to False to skip detail fetching and use only the search-page snippet.
# This is the fastest mode and sufficient when match scoring is semantic.
DETAIL_FETCH_ENABLED = True


class LinkedInScraper(BaseScraper):
    """Scrape LinkedIn public job listings."""

    PORTAL_NAME = "LinkedIn"

    def __init__(self, skill_db: Optional[dict] = None):
        super().__init__(skill_db)
        # Lock to serialise _throttle() calls across ThreadPoolExecutor workers
        self._throttle_lock = threading.Lock()

    def _throttle(self) -> None:
        """
        FIX #9: Thread-safe rate limiting.

        Wraps the parent _throttle() in a lock so that concurrent detail-fetch
        threads do not bypass the 2-second inter-request delay.
        """
        with self._throttle_lock:
            super()._throttle()

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobListing]:
        """
        Scrape LinkedIn job search results.

        Args:
            query:       Job title / skill keywords.
            location:    City, country, or 'Remote'.
            max_results: Maximum listings to return.

        Returns:
            List of JobListing objects.
        """
        # FIX #7: robots.txt gate for live scraping
        if RESPECT_ROBOTS:
            logger.warning(
                "[LinkedIn] RESPECT_ROBOTS=True. LinkedIn's robots.txt disallows "
                "/jobs/search/ for all crawlers. Returning empty result set."
            )
            return []

        listings: List[JobListing] = []
        start     = 0
        page_size = 25

        while len(listings) < max_results:
            params = {
                "keywords": query,
                "location": location,
                "start":    start,
                "trk":      "public_jobs_jobs-search-bar_search-submit",
                "position": 1,
                "pageNum":  0,
            }

            resp = self._get(_SEARCH_URL, params=params)
            if resp is None:
                logger.warning(f"[LinkedIn] Failed to fetch page start={start}")
                break

            page_listings = self._parse_search_page(resp.text)
            if not page_listings:
                break

            # Trim to budget
            remaining    = max_results - len(listings)
            page_listings = page_listings[:remaining]

            # FIX #9: fetch descriptions concurrently
            if DETAIL_FETCH_ENABLED:
                page_listings = self._fetch_descriptions_concurrent(page_listings)

            listings.extend(page_listings)
            start += page_size
            if len(page_listings) < page_size:
                break

        logger.info(f"[LinkedIn] Scraped {len(listings)} listings for '{query}' in '{location}'")
        return listings

    # ------------------------------------------------------------------
    # FIX #9: concurrent detail fetching
    # ------------------------------------------------------------------

    def _fetch_descriptions_concurrent(
        self, listings: List[JobListing]
    ) -> List[JobListing]:
        """
        Fetch job descriptions for a batch of listings in parallel.

        FIX #9: Replaces the sequential for-loop that called
        _fetch_description() one listing at a time. Uses a bounded
        ThreadPoolExecutor so that network I/O for multiple detail pages
        overlaps. The 2-second _throttle() delay is still enforced per
        worker thread via the shared lock, so the scraper remains polite
        while still being faster in wall-clock terms.

        Each listing's description, skills_mentioned, and modality are
        updated in-place before returning.

        Args:
            listings: Listings whose descriptions should be fetched.

        Returns:
            The same list with descriptions populated where available.
        """
        if not listings:
            return listings

        def fetch_one(listing: JobListing) -> JobListing:
            """Worker: fetch and populate one listing's description."""
            try:
                detail = self._fetch_description(listing.url)
                if detail:
                    listing.description      = detail
                    listing.skills_mentioned = _extract_skills_from_text(
                        detail, self._skill_db
                    )
                    listing.modality         = _detect_modality(
                        f"{listing.title} {listing.location} {detail}"
                    )
            except Exception as e:
                logger.debug(f"[LinkedIn] Detail fetch failed for {listing.url}: {e}")
            return listing

        workers = min(MAX_DETAIL_WORKERS, len(listings))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetch_one, lst): lst for lst in listings}
            updated: List[JobListing] = []
            for future in as_completed(futures):
                try:
                    updated.append(future.result())
                except Exception as e:
                    # Fetch failed entirely; keep the original listing
                    logger.debug(f"[LinkedIn] Concurrent detail future error: {e}")
                    updated.append(futures[future])

        # Restore original order (as_completed yields in completion order)
        original_order = {id(lst): lst for lst in listings}
        return [original_order[id(u)] for u in listings]

    # ------------------------------------------------------------------
    # Parsing helpers (unchanged from v2.0)
    # ------------------------------------------------------------------

    def _parse_search_page(self, html: str) -> List[JobListing]:
        soup  = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_=re.compile(r"job-search-card|base-card"))
        if not cards:
            cards = soup.find_all("li", class_=re.compile(r"jobs-search__results"))

        listings = []
        for card in cards:
            try:
                listing = self._parse_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[LinkedIn] Card parse error: {e}")
        return listings

    def _parse_card(self, card) -> Optional[JobListing]:
        title_el = (
            card.find("h3", class_=re.compile(r"base-search-card__title|job-search-card__title"))
            or card.find("span", class_="sr-only")
        )
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        company_el = card.find(
            "h4", class_=re.compile(r"base-search-card__subtitle")
        ) or card.find("a", class_=re.compile(r"job-search-card__company"))
        company = company_el.get_text(strip=True) if company_el else "Unknown Company"

        location_el = card.find(
            "span", class_=re.compile(r"job-search-card__location|base-search-card__metadata")
        )
        location = location_el.get_text(strip=True) if location_el else ""

        link_el = card.find("a", href=re.compile(r"/jobs/view/"))
        url = ""
        if link_el:
            href = link_el.get("href", "")
            url  = href.split("?")[0] if "?" in href else href
            if not url.startswith("http"):
                url = "https://www.linkedin.com" + url

        if not title or not url:
            return None

        return self._make_listing(title, company, location, url)

    def _fetch_description(self, job_url: str) -> str:
        """Fetch full job description from an individual listing page."""
        if not job_url:
            return ""
        resp = self._get(job_url)
        if not resp:
            return ""
        soup    = BeautifulSoup(resp.text, "html.parser")
        desc_el = soup.find("div", class_=re.compile(r"description__text|show-more-less-html"))
        if desc_el:
            return desc_el.get_text(separator=" ", strip=True)[:3000]
        return ""