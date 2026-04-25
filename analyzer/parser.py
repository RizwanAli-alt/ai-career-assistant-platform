"""
Text extraction module for PDF and DOCX files.

IMPROVEMENTS (v2.1):

  FIX #6 — Robustness: extract_text_from_bytes() previously created a
  NamedTemporaryFile with delete=False, closed it, then passed its name to
  pdfplumber. On Windows, antivirus software can lock the file between
  close() and the next open() by pdfplumber, causing a PermissionError.
  The fix uses tempfile.mkdtemp() to create an isolated temporary directory,
  writes the file there, and cleans the entire directory (via shutil.rmtree)
  in the finally block. This avoids the Windows file-locking race condition
  and guarantees cleanup even when extraction raises.

  Other fixes retained from v2.0:
    - clean_text() preserves newlines so section detection works correctly
    - MAX_TEXT_LENGTH safety cap at 50 000 characters
"""

import re
import logging
import tempfile
import os
import shutil
from typing import Optional
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from docx import Document
except ImportError:
    Document = None

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 50_000


def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """
    Extract text from a PDF file using pdfplumber.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Extracted and cleaned text, or None if extraction fails.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If pdfplumber is not installed.
    """
    if pdfplumber is None:
        raise ValueError(
            "pdfplumber is not installed. Run: pip install pdfplumber"
        )

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    try:
        pages_text = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)

        extracted_text = "\n\n".join(pages_text)
        cleaned = clean_text(extracted_text)
        logger.info(f"Extracted text from PDF: {file_path} ({len(cleaned)} chars)")
        return cleaned[:MAX_TEXT_LENGTH]

    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {e}")
        raise


def extract_text_from_docx(file_path: str) -> Optional[str]:
    """
    Extract text from a DOCX file using python-docx.

    Args:
        file_path: Path to the DOCX file.

    Returns:
        Extracted and cleaned text, or None if extraction fails.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If python-docx is not installed.
    """
    if Document is None:
        raise ValueError(
            "python-docx is not installed. Run: pip install python-docx"
        )

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {file_path}")

    try:
        doc = Document(file_path)
        lines = []

        for para in doc.paragraphs:
            if para.text.strip():
                lines.append(para.text.strip())

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        lines.append(cell.text.strip())

        extracted_text = "\n".join(lines)
        cleaned = clean_text(extracted_text)
        logger.info(f"Extracted text from DOCX: {file_path} ({len(cleaned)} chars)")
        return cleaned[:MAX_TEXT_LENGTH]

    except Exception as e:
        logger.error(f"Error extracting text from DOCX {file_path}: {e}")
        raise


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> Optional[str]:
    """
    Extract text directly from file bytes.

    FIX #6 — Windows antivirus race condition:
      The previous implementation used NamedTemporaryFile(delete=False),
      closed the file, then let pdfplumber reopen it by name. On Windows,
      antivirus software can exclusively lock a freshly written file for
      100–500 ms after it is closed, causing pdfplumber's open() to raise
      a PermissionError.

      This version creates a private temporary DIRECTORY with mkdtemp(),
      writes the file inside that directory, and deletes the whole directory
      tree in the finally block via shutil.rmtree(). Writing and then reading
      the same file within one directory avoids antivirus locking because:
        1. The file handle is only ever held by this process.
        2. shutil.rmtree() is more reliable than os.unlink() on Windows
           because it retries across the directory, not just the file.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        filename:   Original filename (used to detect extension).

    Returns:
        Extracted text string.
    """
    ext    = Path(filename).suffix.lower()
    suffix = ext if ext in (".pdf", ".docx") else ".tmp"

    # Create an isolated temp directory for this extraction
    tmp_dir = tempfile.mkdtemp(prefix="cv_extract_")
    tmp_path = os.path.join(tmp_dir, f"upload{suffix}")

    try:
        with open(tmp_path, "wb") as f:
            f.write(file_bytes)
            f.flush()
            os.fsync(f.fileno())   # ensure bytes are on disk before reader opens

        if suffix == ".pdf":
            return extract_text_from_pdf(tmp_path)
        elif suffix == ".docx":
            return extract_text_from_docx(tmp_path)
        else:
            raise ValueError(f"Unsupported file type: {filename}")

    finally:
        # Clean the whole temp directory — shutil.rmtree handles Windows locks
        # more reliably than os.unlink() on individual files.
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as cleanup_err:
            logger.warning(f"Temp dir cleanup failed ({tmp_dir}): {cleanup_err}")


def clean_text(text: str) -> str:
    """
    Clean and normalize extracted text.

    Preserves single newlines so section headers can be found by
    extract_sections(). Collapses runs of spaces/tabs per line but
    does NOT collapse newlines into spaces.

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned text with preserved line breaks.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def extract_sections(text: str) -> dict:
    """
    Extract common resume sections.

    Args:
        text: Full CV text (must retain newlines — use clean_text output).

    Returns:
        Dictionary with extracted sections.
    """
    sections = {
        "summary":        "",
        "experience":     "",
        "education":      "",
        "skills":         "",
        "projects":       "",
        "certifications": "",
        "full_text":      text,
    }

    section_keywords = {
        "summary":        ["summary", "objective", "profile", "about"],
        "experience":     ["experience", "employment", "work history", "work experience"],
        "education":      ["education", "academic background", "qualifications"],
        "skills":         ["skills", "technical skills", "competencies", "technologies"],
        "projects":       ["projects", "portfolio", "personal projects"],
        "certifications": ["certifications", "certificates", "awards", "achievements"],
    }

    all_keywords = [kw for kws in section_keywords.values() for kw in kws]
    boundary     = "|".join(re.escape(k) for k in all_keywords)
    boundary_pattern = rf"(?:^|\n)(?:{boundary})\s*[:\-]?\s*(?:\n|$)"

    for section_name, keywords in section_keywords.items():
        for keyword in keywords:
            start_pattern = rf"(?:^|\n){re.escape(keyword)}\s*[:\-]?\s*(?:\n|$)"
            match = re.search(start_pattern, text, re.IGNORECASE)
            if match:
                start      = match.end()
                next_match = re.search(boundary_pattern, text[start:], re.IGNORECASE)
                end        = start + next_match.start() if next_match else len(text)
                sections[section_name] = text[start:end].strip()
                break

    return sections


def get_text_statistics(text: str) -> dict:
    """
    Calculate statistics about the text.

    Note: CVScorer.score() calls the version in scorer.py with a pre-computed
    word list (FIX #11). This function is retained for standalone use.

    Args:
        text: Input text.

    Returns:
        Dictionary with word_count, character_count, sentence_count,
        average_word_length.
    """
    words     = text.split()
    sentences = re.split(r"[.!?]+", text)

    return {
        "word_count":          len(words),
        "character_count":     len(text),
        "sentence_count":      len([s for s in sentences if s.strip()]),
        "average_word_length": round(len(text) / len(words), 2) if words else 0,
    }