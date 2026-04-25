"""
CV Quality Scoring Engine.

IMPROVEMENTS (v2.1):
  FIX #11 — Performance: word token list computed ONCE in score() and passed
  to all sub-scorers, eliminating redundant text.split() calls that previously
  occurred independently in _dim_keywords() and get_text_statistics().

  SRS CV-FR-02 weight compliance (unchanged from v2.0):
    keywords (30%), completeness (25%), skill density (25%), formatting (20%)

  The four SRS dimensions are computed from sub-components:
    ┌─────────────────────────────────────────────────────────────────┐
    │  SRS Dimension   Weight   Sub-components (internal)             │
    ├─────────────────────────────────────────────────────────────────┤
    │  keywords         0.30    action verbs + keyword density        │
    │  completeness     0.25    section headers + contact + education │
    │  skill_density    0.25    technical skills + soft skills        │
    │  formatting       0.20    structure + bullets + links           │
    └─────────────────────────────────────────────────────────────────┘

  UI detail sub-scores (experience, education, projects) are returned in
  the breakdown dict for display but do NOT affect the weighted total.
"""

import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # Safe for library / Django use

# ---------------------------------------------------------------------------
# SRS-compliant scoring weights  (must sum to 1.0  — SRS Table 4 / CV-FR-02)
# ---------------------------------------------------------------------------
SRS_WEIGHTS = {
    "keywords":      0.30,
    "completeness":  0.25,
    "skill_density": 0.25,
    "formatting":    0.20,
}

assert abs(sum(SRS_WEIGHTS.values()) - 1.0) < 1e-9, "SRS weights must sum to 1.0"


# ---------------------------------------------------------------------------
# Standalone text statistics (FIX #11: accepts pre-computed tokens)
# ---------------------------------------------------------------------------

def get_text_statistics(text: str, words: List[str] = None) -> dict:
    """
    Calculate statistics about the text.

    FIX #11: Accepts an optional pre-computed word list to avoid a second
    text.split() call when the caller already has the token list.

    Args:
        text:  Input text
        words: Pre-split word list (computed once in CVScorer.score()).
               If None, splits text internally (backward-compatible).

    Returns:
        Dictionary with word_count, character_count, sentence_count,
        average_word_length.
    """
    if words is None:
        words = text.split()

    sentences = re.split(r"[.!?]+", text)

    return {
        "word_count": len(words),
        "character_count": len(text),
        "sentence_count": len([s for s in sentences if s.strip()]),
        "average_word_length": round(len(text) / len(words), 2) if words else 0,
    }


class CVScorer:
    """
    Score CV quality across the four SRS-defined dimensions (CV-FR-02).

    Each dimension is scored 0–100 internally, then multiplied by its SRS
    weight to produce the weighted 0–100 total.

    FIX #11: text.split() is called exactly ONCE per score() invocation.
    The resulting token list is forwarded to every sub-scorer and to
    get_text_statistics(), eliminating all redundant re-splits.
    """

    def score(self, text: str, extracted_skills: Dict) -> Dict:
        """
        Calculate comprehensive CV score (0–100).

        Args:
            text: Full CV text
            extracted_skills: {"technical": [...], "soft": [...]}

        Returns:
            {"score": float, "breakdown": {...}}
        """
        # ── FIX #11: tokenise ONCE ───────────────────────────────────────────
        words: List[str] = text.split()

        # ── 4 SRS-defined dimension scores (each 0–100) ─────────────────────
        dim_keywords      = self._dim_keywords(text, words)
        dim_completeness  = self._dim_completeness(text)
        dim_skill_density = self._dim_skill_density(extracted_skills)
        dim_formatting    = self._dim_formatting(text)

        # ── Weighted total per SRS Table 4 ────────────────────────────────────
        total = (
            dim_keywords      * SRS_WEIGHTS["keywords"]
            + dim_completeness  * SRS_WEIGHTS["completeness"]
            + dim_skill_density * SRS_WEIGHTS["skill_density"]
            + dim_formatting    * SRS_WEIGHTS["formatting"]
        )

        # ── Extra UI detail sub-scores (NOT used in weighted total) ──────────
        ui_experience = self._ui_experience(text)
        ui_education  = self._ui_education(text)
        ui_projects   = self._ui_projects(text)

        # ── Text statistics — reuse pre-computed word list (FIX #11) ────────
        stats = get_text_statistics(text, words=words)

        breakdown = {
            # SRS-defined dimension scores (drive the total)
            "keywords_score":      round(dim_keywords,      1),
            "completeness_score":  round(dim_completeness,  1),
            "skill_density_score": round(dim_skill_density, 1),
            "formatting_score":    round(dim_formatting,    1),

            # UI detail scores (display only, not weighted)
            "skills_relevance_score": round(dim_skill_density, 1),   # alias
            "experience_score":       round(ui_experience,     1),
            "education_score":        round(ui_education,      1),
            "keyword_density_score":  round(dim_keywords,      1),   # alias
            "projects_score":         round(ui_projects,       1),

            # Text statistics
            "word_count":      stats["word_count"],
            "character_count": stats["character_count"],
            "sentence_count":  stats["sentence_count"],
        }

        return {"score": round(total, 1), "breakdown": breakdown}

    # =========================================================================
    # SRS Dimension 1 — Keywords (30%)
    # =========================================================================

    def _dim_keywords(self, text: str, words: List[str]) -> float:
        """
        SRS Dimension: Keyword Relevance (0–100).

        FIX #11: Accepts pre-computed word list instead of calling text.split()
        internally.

        Evaluates action verbs, quantified achievements, and word-count
        sweet-spot (300–1 000 words is ATS-optimal).
        """
        if not words:
            return 0.0

        score = 0.0

        # Word count sweet spot
        word_count = len(words)
        if 300 <= word_count <= 1000:
            score += 30
        elif 150 <= word_count < 300 or 1000 < word_count <= 2000:
            score += 15

        # Action verbs (+5 each, capped at 40)
        action_verbs = [
            "led", "managed", "developed", "implemented", "created", "designed",
            "improved", "achieved", "increased", "reduced", "built", "launched",
            "delivered", "optimized", "collaborated", "mentored",
        ]
        verb_hits = sum(
            1 for v in action_verbs if re.search(rf"\b{v}\b", text, re.I)
        )
        score += min(verb_hits * 5, 40)

        # Quantified results (+5 each, capped at 30)
        quantified = re.findall(
            r"\b\d+\%|\$\d+|\d+[xX]|\d+\s*(?:days|weeks|months|years|hours|users|clients)\b",
            text, re.I,
        )
        score += min(len(quantified) * 5, 30)

        return min(score, 100.0)

    # =========================================================================
    # SRS Dimension 2 — Completeness (25%)
    # =========================================================================

    def _dim_completeness(self, text: str) -> float:
        """SRS Dimension: Section Completeness (0–100)."""
        score = 0.0

        sections = {
            "experience": r"\b(experience|employment|work history|work experience)\b",
            "education":  r"\b(education|academic|university|college|degree)\b",
            "skills":     r"\b(skills?|competencies|technical skills)\b",
            "summary":    r"\b(summary|objective|profile|about)\b",
            "projects":   r"\b(projects?|portfolio)\b",
        }
        for pattern in sections.values():
            if re.search(pattern, text, re.I):
                score += 12

        # Contact completeness (40 pts)
        if re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text):
            score += 15
        if re.search(r"(\+?\d[\d\s\-().]{7,}\d)", text):
            score += 10
        if re.search(r"(linkedin\.com|github\.com|portfolio|https?://)", text, re.I):
            score += 15

        return min(score, 100.0)

    # =========================================================================
    # SRS Dimension 3 — Skill Density (25%)
    # =========================================================================

    def _dim_skill_density(self, extracted_skills: Dict) -> float:
        """SRS Dimension: Skill Density (0–100)."""
        tech_count = len(extracted_skills.get("technical", []))
        soft_count = len(extracted_skills.get("soft", []))
        return min(tech_count * 6, 60) + min(soft_count * 8, 40)

    # =========================================================================
    # SRS Dimension 4 — Formatting (20%)
    # =========================================================================

    def _dim_formatting(self, text: str) -> float:
        """SRS Dimension: Formatting Assessment (0–100)."""
        score = 0.0
        if "\n" in text:
            score += 20
        if "•" in text or re.search(r"\n\s*[-*]\s", text):
            score += 25
        if re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text):
            score += 20
        if re.search(r"(\+?\d[\d\s\-().]{7,}\d)", text):
            score += 15
        if re.search(r"(https?://|github\.com|linkedin\.com|portfolio)", text, re.I):
            score += 20
        return min(score, 100.0)

    # =========================================================================
    # UI Detail Sub-scores (NOT used in SRS weighted total — display only)
    # =========================================================================

    def _ui_experience(self, text: str) -> float:
        score = 0.0
        if re.search(r"\b(experience|employment|work history|work experience)\b", text, re.I):
            score += 40
        date_ranges = re.findall(
            r"\d{4}\s*[-–]\s*(?:\d{4}|present|current|now)", text, re.I
        )
        score += min(len(date_ranges) * 15, 45)
        quantified = re.findall(r"\b\d+\s*[%$]|\$\s*\d+|\d+[xX]\b", text)
        score += min(len(quantified) * 5, 15)
        return min(score, 100.0)

    def _ui_education(self, text: str) -> float:
        score = 0.0
        if re.search(r"\b(education|academic|university|college|degree)\b", text, re.I):
            score += 30
        degrees = ["bachelor", "master", "phd", "diploma", "associate",
                   r"b\.sc", r"m\.sc", "bs", "ms"]
        for deg in degrees:
            if re.search(rf"\b{deg}\b", text, re.I):
                score += 15
                break
        if re.search(r"\bgpa\b.*?[\d.]+", text, re.I):
            score += 10
        if re.search(r"\b(20\d{2}|19\d{2})\b", text):
            score += 10
        fields = ["computer science", "software engineering", "information technology",
                  "data science", "electrical", "mathematics"]
        for field in fields:
            if field in text.lower():
                score += 15
                break
        return min(score, 100.0)

    def _ui_projects(self, text: str) -> float:
        return 100.0 if re.search(
            r"\b(projects?|portfolio|personal projects?)\b", text, re.I
        ) else 0.0


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def calculate_score(text: str, extracted_skills: Dict) -> Dict:
    """
    Calculate CV quality score using the 4 SRS-defined weighted dimensions.

    Args:
        text: CV text
        extracted_skills: {"technical": [...], "soft": [...]}

    Returns:
        {"score": float, "breakdown": {...}}
    """
    scorer = CVScorer()
    result = scorer.score(text, extracted_skills)
    logger.info(
        f"CV scored: {result['score']}/100 "
        f"(keywords:{SRS_WEIGHTS['keywords']}, "
        f"completeness:{SRS_WEIGHTS['completeness']}, "
        f"skill_density:{SRS_WEIGHTS['skill_density']}, "
        f"formatting:{SRS_WEIGHTS['formatting']})"
    )
    return result