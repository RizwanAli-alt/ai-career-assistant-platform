"""
Skill extraction module.

IMPROVEMENTS (v2.1):

  FIX #2 — Performance: SkillExtractor is now exposed as a Streamlit
  @st.cache_resource singleton via get_skill_extractor(). The module-level
  extract_skills() function uses this cached instance so the JSON, spaCy
  model, and HF NER pipeline are loaded at most ONCE per process, not on
  every CV upload.

  FIX #10 — Correctness: HF BERT NER was truncating at 600 words, but the
  underlying bert-base model has a 512 *token* limit (≈ 350–400 words).
  Silently truncating mid-token produces garbage entity spans. This version
  implements a sliding-window approach: the text is split into overlapping
  128-word windows that each fit safely within the 512-token limit, and
  entities from all windows are merged and deduplicated.

  Strategy (SRS CV-FR-01: spaCy NLP + Hugging Face Transformers + keyword):
    1. Keyword matching against skills_db.json     — fast, high precision
    2. spaCy NER (if installed)                    — catches unlisted skills
    3. HF Transformer NER pipeline (sliding-window)— SRS-required 2nd ML pass
    4. Results merged and deduplicated
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# Optional spaCy import
# ---------------------------------------------------------------------------
try:
    import spacy
    _SPACY_AVAILABLE = True
except ImportError:
    spacy = None  # type: ignore
    _SPACY_AVAILABLE = False
    logger.warning(
        "spaCy not installed. Falling back to keyword-only extraction. "
        "Run: pip install spacy && python -m spacy download en_core_web_sm"
    )

# ---------------------------------------------------------------------------
# Optional Hugging Face Transformers import  (SRS CV-FR-01 requirement)
# ---------------------------------------------------------------------------
try:
    from transformers import pipeline as hf_pipeline
    _HF_AVAILABLE = True
except ImportError:
    hf_pipeline = None  # type: ignore
    _HF_AVAILABLE = False
    logger.warning(
        "Hugging Face transformers not installed — SRS CV-FR-01 requires it. "
        "Run: pip install transformers torch"
    )

_DEFAULT_SKILL_DB = Path(__file__).parent.parent / "models" / "skill_db.json"

_HF_NER_MODEL   = "dslim/bert-base-NER"
_HF_TECH_LABELS = {"ORG", "MISC"}

# FIX #10: safe window size (words) that reliably stays under 512 BERT tokens.
# 300 words ≈ 380–420 tokens for typical English CV text; stride of 150 words
# gives ~50% overlap so entities spanning a window boundary are still captured.
_HF_WINDOW_WORDS  = 300
_HF_STRIDE_WORDS  = 150

_TECH_TOKEN_RE = re.compile(
    r"^(?:[A-Z][a-zA-Z0-9.#+\-/]{1,}|[A-Z]{2,10}|[a-z]+[0-9]+[a-zA-Z0-9]*)$"
)

# ---------------------------------------------------------------------------
# Module-level singleton for the extractor (supports FIX #2 without Streamlit)
# ---------------------------------------------------------------------------
_extractor_singleton: Optional["SkillExtractor"] = None


def get_skill_extractor(skill_db_path: Optional[str] = None) -> "SkillExtractor":
    """
    Return a module-level SkillExtractor singleton.

    FIX #2: The extractor (including its JSON, spaCy model, and HF pipeline)
    is built once and reused across all calls. In Streamlit, wrap this with
    @st.cache_resource (see app.py); outside Streamlit the module-level
    singleton provides the same benefit.

    Args:
        skill_db_path: Optional override; ignored after first construction.

    Returns:
        Cached SkillExtractor instance.
    """
    global _extractor_singleton
    if _extractor_singleton is None:
        _extractor_singleton = SkillExtractor(skill_db_path)
    return _extractor_singleton


class SkillExtractor:
    """
    Extract skills from CV text using three complementary strategies:
      1. Keyword matching   — high precision, database-driven, always runs
      2. spaCy NER          — catches technology names not in the skill DB
      3. HF BERT NER        — SRS CV-FR-01 Transformer pass (sliding window)
    """

    def __init__(self, skill_db_path: Optional[str] = None):
        self.skill_db = self._load_skill_db(skill_db_path)
        self._nlp     = self._load_spacy()
        self._hf_ner  = self._load_hf_ner()

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def _load_skill_db(self, skill_db_path: Optional[str]) -> dict:
        path = Path(skill_db_path) if skill_db_path else _DEFAULT_SKILL_DB
        try:
            with open(path, "r", encoding="utf-8") as f:
                db = json.load(f)
            logger.info(f"Loaded skill database from {path}")
            db["technical"] = list(dict.fromkeys(db.get("technical", [])))
            db["soft"]       = list(dict.fromkeys(db.get("soft", [])))
            return db
        except FileNotFoundError:
            logger.warning(f"Skill database not found at {path}")
            return {"technical": [], "soft": []}
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in skill database at {path}")
            return {"technical": [], "soft": []}

    def _load_spacy(self):
        if not _SPACY_AVAILABLE:
            return None
        try:
            nlp = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy model: en_core_web_sm")
            return nlp
        except OSError:
            logger.warning(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )
            return None

    def _load_hf_ner(self):
        """
        Load Hugging Face NER pipeline (SRS CV-FR-01 requirement).

        Uses dslim/bert-base-NER (BERT fine-tuned on CoNLL-2003).
        aggregation_strategy="simple" merges sub-word tokens.
        Falls back gracefully when transformers/torch is not installed.
        """
        if not _HF_AVAILABLE:
            return None
        try:
            ner = hf_pipeline(
                "ner",
                model=_HF_NER_MODEL,
                aggregation_strategy="simple",
                device=-1,
            )
            logger.info(f"Loaded Hugging Face NER model: {_HF_NER_MODEL}")
            return ner
        except Exception as e:
            logger.error(
                f"Failed to load HF NER model '{_HF_NER_MODEL}': {e}. "
                "Extraction will proceed without the Transformer pass."
            )
            return None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract(self, text: str) -> Dict[str, List[str]]:
        """
        Extract skills from text using all available strategies.

        Args:
            text: CV full text

        Returns:
            {"technical": [...], "soft": [...]}
        """
        technical: set = set()
        soft: set = set()

        try:
            technical.update(self._keyword_match(text, self.skill_db.get("technical", [])))
            soft.update(self._keyword_match(text, self.skill_db.get("soft", [])))

            if self._nlp is not None:
                ner_technical, ner_soft = self._spacy_extract(text)
                technical.update(ner_technical)
                soft.update(ner_soft)

            if self._hf_ner is not None:
                hf_technical = self._hf_extract(text)
                technical.update(hf_technical)

        except Exception as e:
            logger.error(f"Error during skill extraction: {e}")

        return {
            "technical": sorted(technical),
            "soft":      sorted(soft),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _keyword_match(self, text: str, keywords: List[str]) -> set:
        matched: set = set()
        text_lower = text.lower()
        for keyword in keywords:
            try:
                pattern = rf"\b{re.escape(keyword.lower())}\b"
                if re.search(pattern, text_lower):
                    matched.add(keyword)
            except Exception as e:
                logger.debug(f"Keyword match error for '{keyword}': {e}")
        return matched

    def _spacy_extract(self, text: str):
        doc = self._nlp(text[:10_000])
        known_technical = {s.lower() for s in self.skill_db.get("technical", [])}
        known_soft      = {s.lower() for s in self.skill_db.get("soft", [])}
        extra_technical: set = set()
        extra_soft: set = set()

        for ent in doc.ents:
            token = ent.text.strip()
            token_lower = token.lower()
            if len(token) < 2 or len(token) > 40:
                continue
            if ent.label_ in ("ORG", "PRODUCT"):
                if token_lower not in known_technical and token_lower not in known_soft:
                    if _TECH_TOKEN_RE.match(token) or token.isupper():
                        extra_technical.add(token)

        return extra_technical, extra_soft

    def _hf_extract(self, text: str) -> set:
        """
        Hugging Face BERT NER extraction pass (SRS CV-FR-01).

        FIX #10 — Sliding-window chunking:
          The previous version truncated at 600 words and passed that single
          block to the model. However, bert-base has a hard 512-token limit
          (≈ 350–400 words for English). Words beyond ≈ 400 were silently
          truncated by the tokenizer, producing missed or mangled entities.

          This version splits the full CV text into overlapping word windows:
            • window size : _HF_WINDOW_WORDS  (300 words  ≈ 380–420 tokens)
            • stride      : _HF_STRIDE_WORDS  (150 words — 50 % overlap)

          Each window is independently processed by the NER model, and entity
          sets from all windows are union-merged and de-duplicated. The 50 %
          overlap ensures that entities near window boundaries are captured
          by at least one window.

        Returns:
            set of additional technical skill strings
        """
        known_technical = {s.lower() for s in self.skill_db.get("technical", [])}
        known_soft      = {s.lower() for s in self.skill_db.get("soft", [])}
        extra: set = set()

        all_words = text.split()
        if not all_words:
            return extra

        # Build overlapping windows
        windows: List[str] = []
        start = 0
        while start < len(all_words):
            end = min(start + _HF_WINDOW_WORDS, len(all_words))
            windows.append(" ".join(all_words[start:end]))
            if end == len(all_words):
                break
            start += _HF_STRIDE_WORDS

        logger.debug(
            f"HF NER: processing {len(windows)} window(s) "
            f"({len(all_words)} total words)"
        )

        for window_text in windows:
            try:
                entities = self._hf_ner(window_text)
                for ent in entities:
                    word  = ent.get("word", "").strip()
                    label = ent.get("entity_group", "")

                    if word.startswith("##") or len(word) < 2 or len(word) > 40:
                        continue
                    if label not in _HF_TECH_LABELS:
                        continue

                    word_lower = word.lower()
                    if word_lower in known_technical or word_lower in known_soft:
                        continue
                    if _TECH_TOKEN_RE.match(word) or word.isupper():
                        extra.add(word)
                        logger.debug(f"HF NER skill: '{word}' ({label})")

            except Exception as e:
                logger.error(f"HF NER window extraction failed: {e}")
                # Continue processing remaining windows even if one fails

        return extra


# ---------------------------------------------------------------------------
# Module-level availability flags
# ---------------------------------------------------------------------------

def is_hf_available() -> bool:
    """Return True if Hugging Face transformers is installed."""
    return _HF_AVAILABLE


# ---------------------------------------------------------------------------
# Public module-level function
# ---------------------------------------------------------------------------

def extract_skills(text: str, skill_db_path: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Extract skills from CV text using all available strategies.

    FIX #2: Uses the module-level SkillExtractor singleton so models are
    loaded only once. In Streamlit, app.py wraps get_skill_extractor() with
    @st.cache_resource for even stronger caching guarantees.

    Args:
        text: CV text
        skill_db_path: Optional path to skill database JSON

    Returns:
        {"technical": [...], "soft": [...]}
    """
    extractor = get_skill_extractor(skill_db_path)
    skills = extractor.extract(text)
    logger.info(
        f"Extracted {len(skills['technical'])} technical and "
        f"{len(skills['soft'])} soft skills "
        f"(spaCy={'on' if _SPACY_AVAILABLE else 'off'}, "
        f"HF NER={'on' if _HF_AVAILABLE else 'off'}, "
        f"windows per run={max(1, len(text.split()) // _HF_STRIDE_WORDS)})"
    )
    return skills