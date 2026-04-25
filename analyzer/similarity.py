"""
Semantic Similarity Analysis Module.

IMPROVEMENTS (v2.1):

  FIX #3 — Performance: SimilarityAnalyzer is now cached as a module-level
  singleton via get_similarity_analyzer(). Previously, every call to
  calculate_similarity() instantiated a new SimilarityAnalyzer, which
  triggered a full SentenceTransformer.load() — a multi-second operation
  even when the model is already on disk. The singleton is built once and
  reused for all subsequent calls. In Streamlit, app.py wraps
  get_similarity_analyzer() with @st.cache_resource for additional safety.

  FIX #5 — Security: sanitize_jd() strips HTML tags and control characters
  from the job description before embedding it. Raw JD text pasted from
  websites can contain <script>, HTML entities, and zero-width characters
  that skew the embedding. This is applied before the existing length cap.

  Other fixes retained from v2.0:
    - 'import re' at top of file (was at bottom — fixed in v2.0)
    - NullHandler for Django logging safety
    - Graceful fallback when sentence-transformers is not installed
    - Public function accepts optional job_description (SRS requirement)
"""

import re
import html
import logging
from typing import Optional

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

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
        "sentence-transformers or scikit-learn not installed. "
        "Similarity scoring will be unavailable. "
        "Run: pip install sentence-transformers scikit-learn"
    )

SAMPLE_JOB_DESCRIPTION = """
We are looking for a skilled software professional with:
- Strong technical background and programming skills (Python, JavaScript, Java)
- Experience with modern web frameworks (Django, React, Node.js)
- Database knowledge: SQL, PostgreSQL, MongoDB
- Cloud and DevOps: AWS, Docker, Kubernetes, CI/CD
- Problem-solving and analytical abilities
- Team collaboration and communication skills
- Degree in Computer Science, Software Engineering, or related field
- Portfolio, GitHub profile, or open-source contributions
- Understanding of software architecture and design patterns
- Version control with Git
"""

MODEL_NAME   = "sentence-transformers/all-MiniLM-L6-v2"
MAX_JD_LENGTH = 5_000

# ---------------------------------------------------------------------------
# Module-level singleton (FIX #3)
# ---------------------------------------------------------------------------
_analyzer_singleton: Optional["SimilarityAnalyzer"] = None


def get_similarity_analyzer() -> "SimilarityAnalyzer":
    """
    Return the module-level SimilarityAnalyzer singleton.

    FIX #3: Builds the analyzer (and loads SentenceTransformer) exactly once
    per process. Subsequent calls return the cached instance instantly.
    In Streamlit, wrap this with @st.cache_resource in app.py.

    Returns:
        Cached SimilarityAnalyzer instance.
    """
    global _analyzer_singleton
    if _analyzer_singleton is None:
        _analyzer_singleton = SimilarityAnalyzer()
    return _analyzer_singleton


# ---------------------------------------------------------------------------
# Input sanitization (FIX #5)
# ---------------------------------------------------------------------------

def sanitize_jd(raw_jd: str) -> str:
    """
    Strip HTML tags, decode HTML entities, and remove control characters
    from a raw job-description string before it is embedded.

    FIX #5 — Security: job descriptions pasted from websites frequently
    contain HTML markup, JavaScript snippets, HTML entities (&amp; &nbsp;),
    and invisible Unicode control characters. These do not carry semantic
    meaning for the similarity model but do shift the embedding vector and
    can potentially be used for prompt-injection-style attacks if the text
    is ever forwarded to an LLM. Sanitizing here is cheap and safe.

    Args:
        raw_jd: Unsanitized job description text.

    Returns:
        Clean plain-text string.
    """
    # 1. Decode HTML entities first (&amp; → &, &nbsp; → space, etc.)
    text = html.unescape(raw_jd)

    # 2. Strip HTML / XML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # 3. Remove control characters (keep \n \t)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # 4. Collapse excessive whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


class SimilarityAnalyzer:
    """
    Analyze semantic similarity between a CV and a job description.

    FIX #3: Instantiate via get_similarity_analyzer() to reuse the singleton.
    """

    def __init__(self):
        self.model = self._load_model()

    def _load_model(self):
        if not _ST_AVAILABLE:
            return None
        try:
            model = SentenceTransformer(MODEL_NAME)
            logger.info(f"Loaded sentence-transformers model: {MODEL_NAME}")
            return model
        except Exception as e:
            logger.error(f"Error loading sentence-transformers model: {e}")
            return None

    @property
    def model_available(self) -> bool:
        return self.model is not None

    def calculate_similarity(
        self, cv_text: str, job_description: Optional[str] = None
    ) -> float:
        """
        Calculate semantic similarity between CV and job description.

        FIX #5: job_description is sanitized via sanitize_jd() before
        embedding to remove HTML, entities, and control characters.

        Args:
            cv_text: Full CV text.
            job_description: Raw job description (HTML/plain). Falls back
                             to built-in sample JD when None or empty.

        Returns:
            Similarity percentage (0.0–100.0), or 0 if model unavailable.
        """
        if not cv_text or not cv_text.strip():
            return 0.0

        if self.model is None:
            logger.warning("Similarity model not available — returning 0.")
            return 0.0

        # FIX #5: sanitize before use
        if job_description and job_description.strip():
            jd = sanitize_jd(job_description)[:MAX_JD_LENGTH]
            if not jd:               # sanitization may have removed everything
                jd = SAMPLE_JOB_DESCRIPTION
        else:
            jd = SAMPLE_JOB_DESCRIPTION

        try:
            cv_chunks = self._chunk(cv_text, max_len=256)
            jd_chunks = self._chunk(jd,       max_len=256)

            if not cv_chunks or not jd_chunks:
                return 0.0

            cv_emb = self.model.encode(cv_chunks, show_progress_bar=False)
            jd_emb = self.model.encode(jd_chunks, show_progress_bar=False)

            sim_matrix = cosine_similarity(cv_emb, jd_emb)
            avg_sim    = float(np.mean(np.max(sim_matrix, axis=1)))
            pct        = round(avg_sim * 100, 1)

            logger.info(f"Similarity score: {pct}%")
            return pct

        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0

    @staticmethod
    def _chunk(text: str, max_len: int = 256) -> list:
        """Split text into sentence chunks within max_len characters."""
        if not text or not text.strip():
            return []
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks, current = [], ""
        for sent in sentences:
            if len(current) + len(sent) < max_len:
                current += sent + " "
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = sent + " "
        if current.strip():
            chunks.append(current.strip())
        return chunks if chunks else [text[:max_len]]


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def calculate_similarity(
    cv_text: str, job_description: Optional[str] = None
) -> float:
    """
    Calculate semantic similarity between CV and job description.

    FIX #3: Uses the module-level singleton so the model is loaded once.
    FIX #5: Sanitizes job_description before embedding.

    Args:
        cv_text: Full CV text.
        job_description: Optional job description. Uses built-in sample if None.

    Returns:
        Similarity percentage (0.0–100.0).
    """
    analyzer = get_similarity_analyzer()
    return analyzer.calculate_similarity(cv_text, job_description)


def is_similarity_available() -> bool:
    """Check whether the similarity model is installed and loadable."""
    return _ST_AVAILABLE