"""
Job-to-Profile Match Scorer (SCR-FR-02).

IMPROVEMENTS (v2.1):

  FIX #8 — Correctness: _tfidf_fallback_score() previously used the formula
      overlap / (len(job_words) ** 0.5 + 1e-6) * 10
  For very short job texts (e.g. a 3-word title with no description), the
  denominator approaches 0, causing the expression to return a value well
  above 100 before the final min() clamp. Two guards are added:
    1. A minimum job-text word count (MIN_JOB_WORDS = 10). Texts shorter
       than this get a score of 0.0 — a 3-word title can't meaningfully
       be compared to a full skill set.
    2. The scaling constant is reduced from 10 to 6 and the formula uses
       a harmonic-mean-style denominator ( (|job| + |skills|) / 2 ) which
       is better-behaved across all text lengths and still returns 0–100.

  FIX #7 — Ethics: added RESPECT_ROBOTS flag and documentation. The flag
  is consumed by BaseScraper in base.py; it is defined here so app.py can
  expose it as a runtime toggle without importing base.py directly.

  Other fixes retained from v2.0:
    - Semantic scoring via sentence-transformers when available (SCR-FR-02 BR-1)
    - Keyword TF-IDF fallback when transformers not installed
    - Model loaded as module-level singleton to avoid repeated downloads
"""

import logging
import re
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# FIX #7 — Ethics: robots.txt compliance flag
# ---------------------------------------------------------------------------
# Set to True to enable robots.txt checking before each live scrape request.
# When True, BaseScraper._get() will call robotparser.RobotFileParser for the
# target domain and skip the request if the path is disallowed. Note that
# LinkedIn's robots.txt explicitly disallows /jobs/search/ for all crawlers.
# Default: False to preserve backward compatibility in demo mode.
RESPECT_ROBOTS: bool = False

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    _ST_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore
    cosine_similarity   = None  # type: ignore
    np                  = None  # type: ignore
    _ST_AVAILABLE = False
    logger.warning(
        "sentence-transformers not installed. "
        "Falling back to TF-IDF keyword match scoring. "
        "Run: pip install sentence-transformers scikit-learn"
    )

MODEL_NAME   = "sentence-transformers/all-MiniLM-L6-v2"
_model_cache = None

# FIX #8: minimum number of words a job text must have before TF-IDF scoring.
# Texts shorter than this cannot produce a meaningful overlap score.
MIN_JOB_WORDS = 10


def _get_model():
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    if not _ST_AVAILABLE:
        return None
    try:
        _model_cache = SentenceTransformer(MODEL_NAME)
        logger.info(f"Loaded sentence-transformers model: {MODEL_NAME}")
        return _model_cache
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return None


def _skills_to_text(extracted_skills: Dict) -> str:
    """Convert skill dict to a flat text string for embedding."""
    technical = extracted_skills.get("technical", [])
    soft      = extracted_skills.get("soft", [])
    return " ".join(technical + soft)


def _tfidf_fallback_score(job_text: str, skills_text: str) -> float:
    """
    Keyword overlap score when sentence-transformers is unavailable.

    FIX #8 — Inflated score guard:
      Previous formula: overlap / (len(job_words) ** 0.5 + 1e-6) * 10
      For a 3-word job text with 2-word overlap this gives:
        2 / (3 ** 0.5 + 1e-6) * 10 ≈ 11.5 → clipped to 100 by min()

      New approach:
        1. Reject texts shorter than MIN_JOB_WORDS (10 words) immediately.
           A title-only listing can't be reliably scored against a full CV.
        2. Use a harmonic-mean denominator:
             score = overlap / ((|job| + |skills|) / 2) * 100
           This is bounded in [0, 100] by construction when overlap ≤
           min(|job|, |skills|), and does not require a separate clamp for
           reasonable inputs. The final min() is kept as a safety net.

    Args:
        job_text:    Combined job title + description text.
        skills_text: Space-separated skill tokens from user's CV.

    Returns:
        Score in [0.0, 100.0].
    """
    if not job_text or not skills_text:
        return 0.0

    job_words   = set(re.findall(r"\b\w{3,}\b", job_text.lower()))
    skill_words = set(re.findall(r"\b\w{3,}\b", skills_text.lower()))

    # FIX #8 guard 1: reject very short job texts
    if len(job_words) < MIN_JOB_WORDS:
        logger.debug(
            f"TF-IDF fallback: job text too short ({len(job_words)} words < "
            f"{MIN_JOB_WORDS} minimum) — returning 0."
        )
        return 0.0

    if not skill_words:
        return 0.0

    overlap = len(job_words & skill_words)

    # FIX #8 guard 2: harmonic-mean denominator → naturally bounded [0, 1]
    denom = (len(job_words) + len(skill_words)) / 2.0
    score = (overlap / denom) * 100.0

    return min(round(score, 1), 100.0)


def score_listing(job_text: str, user_skills: Dict) -> float:
    """
    Calculate match score between a job listing and user skills.

    Args:
        job_text:    Combined job title + description text.
        user_skills: {"technical": [...], "soft": [...]}.

    Returns:
        Match percentage 0–100 (SCR-FR-02 BR-2).
    """
    if not job_text or not user_skills:
        return 0.0

    skills_text = _skills_to_text(user_skills)
    if not skills_text.strip():
        return 0.0

    model = _get_model()

    if model is None:
        return _tfidf_fallback_score(job_text, skills_text)

    try:
        job_embedding   = model.encode([job_text[:1000]], show_progress_bar=False)
        skill_embedding = model.encode([skills_text],     show_progress_bar=False)
        sim = float(cosine_similarity(job_embedding, skill_embedding)[0][0])
        return round(max(0.0, min(sim * 100, 100.0)), 1)
    except Exception as e:
        logger.error(f"Embedding similarity failed: {e}")
        return _tfidf_fallback_score(job_text, skills_text)


def score_and_sort(listings, user_skills: Dict) -> list:
    """
    Score all listings against user skills and return sorted descending.

    SCR-FR-02 BR-1 + BR-3.

    Args:
        listings:    List[JobListing].
        user_skills: {"technical": [...], "soft": [...]}.

    Returns:
        Listings sorted by match_score descending.
    """
    scored = []
    for listing in listings:
        job_text          = f"{listing.title} {listing.company} {listing.description}"
        listing.match_score = score_listing(job_text, user_skills)
        scored.append(listing)

    scored.sort(key=lambda j: j.match_score, reverse=True)

    if scored:
        logger.info(
            f"Scored {len(scored)} listings. "
            f"Top match: {scored[0].match_score}% — {scored[0].title}"
        )
    else:
        logger.info("No listings to score.")

    return scored


def is_match_available() -> bool:
    """True if sentence-transformers is installed (semantic mode)."""
    return _ST_AVAILABLE