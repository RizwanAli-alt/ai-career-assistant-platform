"""
Base Scraper Infrastructure.

IMPROVEMENTS (v2.1):

  FIX #7 — Ethics: Added optional robots.txt checking via Python's built-in
  urllib.robotparser. When RESPECT_ROBOTS is True in matcher.py, BaseScraper
  checks whether the target URL is allowed before making the request. Results
  are cached per domain (ROBOTS_CACHE) so the robots.txt file is fetched at
  most once per domain per scraper session.

  Note: LinkedIn's robots.txt explicitly disallows /jobs/search/ for all
  user-agents. Enabling RESPECT_ROBOTS will therefore return 0 LinkedIn
  results in live mode. Demo mode is unaffected.

  Other SRS requirements unchanged:
    BR-1: 2-second delay between consecutive requests per portal
    BR-2: Listings older than 30 days automatically purged
    BR-3: Portal failures logged, pipeline continues
    BR-4: Public listings only, no authentication
"""

import time
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

REQUEST_DELAY_SECONDS = 2.0
LISTING_MAX_AGE_DAYS  = 30

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]
_UA_INDEX = 0

# FIX #7: per-domain robots.txt cache { "www.linkedin.com": RobotFileParser }
ROBOTS_CACHE: dict = {}


def _next_ua() -> str:
    global _UA_INDEX
    ua = _USER_AGENTS[_UA_INDEX % len(_USER_AGENTS)]
    _UA_INDEX += 1
    return ua


def _is_allowed_by_robots(url: str) -> bool:
    """
    Check whether the given URL is allowed by the target site's robots.txt.

    FIX #7: Called by BaseScraper._get() when RESPECT_ROBOTS is True.
    RobotFileParser instances are cached per domain so each domain's
    robots.txt is fetched at most once per session.

    Args:
        url: Full URL to check.

    Returns:
        True if allowed (or robots.txt is unreachable), False if disallowed.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"

        if domain not in ROBOTS_CACHE:
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                ROBOTS_CACHE[domain] = rp
                logger.debug(f"[robots.txt] Fetched and cached for {domain}")
            except Exception as e:
                logger.warning(f"[robots.txt] Could not fetch {robots_url}: {e}. Allowing.")
                return True     # fail-open: if robots.txt is unreachable, allow

        rp = ROBOTS_CACHE[domain]
        allowed = rp.can_fetch("*", url)
        if not allowed:
            logger.warning(f"[robots.txt] Disallowed: {url}")
        return allowed

    except Exception as e:
        logger.warning(f"[robots.txt] Check failed for {url}: {e}. Allowing.")
        return True   # fail-open


@dataclass
class JobListing:
    """Canonical job listing returned by every portal scraper."""
    title:            str
    company:          str
    location:         str
    modality:         str
    portal:           str
    url:              str
    description:      str = ""
    skills_mentioned: List[str] = field(default_factory=list)
    scraped_at:       datetime  = field(default_factory=datetime.utcnow)
    match_score:      float     = 0.0

    def is_expired(self) -> bool:
        return (datetime.utcnow() - self.scraped_at).days >= LISTING_MAX_AGE_DAYS

    def to_dict(self) -> dict:
        return {
            "title":            self.title,
            "company":          self.company,
            "location":         self.location,
            "modality":         self.modality,
            "portal":           self.portal,
            "url":              self.url,
            "description":      self.description,
            "skills_mentioned": self.skills_mentioned,
            "scraped_at":       self.scraped_at.isoformat(),
            "match_score":      self.match_score,
        }


def _detect_modality(text: str) -> str:
    t = text.lower()
    if "remote" in t:
        return "Remote"
    if "hybrid" in t:
        return "Hybrid"
    if any(w in t for w in ("on-site", "onsite", "on site", "in-office", "in office")):
        return "On-site"
    return "Unknown"


def _extract_skills_from_text(text: str, skill_db: Optional[dict] = None) -> List[str]:
    if not skill_db:
        return []
    found      = []
    text_lower = text.lower()
    for skill in skill_db.get("technical", []) + skill_db.get("soft", []):
        pattern = rf"\b{re.escape(skill.lower())}\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return list(set(found))


def _build_session() -> requests.Session:
    session = requests.Session()
    retry   = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update({
        "Accept-Language":  "en-US,en;q=0.9",
        "Accept":           "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding":  "gzip, deflate, br",
        "Connection":       "keep-alive",
        "DNT":              "1",
    })
    return session


class BaseScraper:
    """
    Base class for all portal scrapers.

    Subclasses implement:
        scrape(query, location, max_results) -> List[JobListing]
    """

    PORTAL_NAME: str = "Unknown"

    def __init__(self, skill_db: Optional[dict] = None):
        self._session           = _build_session()
        self._last_request_time = 0.0
        self._skill_db          = skill_db or {}

    def _throttle(self) -> None:
        """SCR-FR-01 BR-1: enforce 2-second delay between requests."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request_time = time.monotonic()

    def _get(
        self,
        url: str,
        params: Optional[dict] = None,
        timeout: int = 15,
    ) -> Optional[requests.Response]:
        """
        GET with rate limiting, rotating UA, robots.txt check, and graceful
        error handling. SCR-FR-01 BR-3: failures logged, None returned.

        FIX #7: Checks robots.txt when RESPECT_ROBOTS is True (imported
        from matcher.py to keep the flag in one place).
        """
        # FIX #7: robots.txt gate
        try:
            from .matcher import RESPECT_ROBOTS as _respect
        except ImportError:
            _respect = False

        if _respect and not _is_allowed_by_robots(url):
            logger.warning(
                f"[{self.PORTAL_NAME}] Skipping {url} — disallowed by robots.txt"
            )
            return None

        self._throttle()
        self._session.headers["User-Agent"] = _next_ua()

        try:
            resp = self._session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            logger.info(f"[{self.PORTAL_NAME}] GET {url} → {resp.status_code}")
            return resp
        except requests.exceptions.HTTPError as e:
            logger.warning(f"[{self.PORTAL_NAME}] HTTP error for {url}: {e}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"[{self.PORTAL_NAME}] Connection error for {url}: {e}")
        except requests.exceptions.Timeout:
            logger.warning(f"[{self.PORTAL_NAME}] Timeout for {url}")
        except Exception as e:
            logger.error(f"[{self.PORTAL_NAME}] Unexpected error for {url}: {e}")
        return None

    def _make_listing(
        self,
        title:       str,
        company:     str,
        location:    str,
        url:         str,
        description: str = "",
    ) -> JobListing:
        return JobListing(
            title            = title,
            company          = company,
            location         = location,
            modality         = _detect_modality(f"{title} {location} {description}"),
            portal           = self.PORTAL_NAME,
            url              = url,
            description      = description,
            skills_mentioned = _extract_skills_from_text(description, self._skill_db),
        )

    def scrape(
        self, query: str, location: str = "", max_results: int = 20
    ) -> List[JobListing]:
        raise NotImplementedError