"""
extractor.py
-------------
Parses raw OCR text and extracts structured certificate fields:
candidate name, organization, issue date, certificate number, etc.

Why regex + keyword anchoring instead of a heavy NLP/NER model:
Certificates follow fairly predictable patterns ("This certifies that
[NAME]", "Date: [DATE]", "Certificate ID: [XXXX]"). A lightweight,
explainable rule-based approach is faster, has zero extra dependencies,
and is easy to debug/extend — appropriate for this project's scope.
(A full NER model is mentioned in the task doc as a *future* LLM-pipeline
direction, not a requirement here.)
"""

import re
from typing import Optional, Dict


# ---- Regex patterns for common certificate fields ----
# Each pattern is deliberately permissive (case-insensitive, flexible
# whitespace) because OCR output is never perfectly clean.

DATE_PATTERN = re.compile(
    r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})|"          # 12/05/2024, 12-05-24
    r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})",              # May 12, 2024
    re.IGNORECASE
)

CERT_ID_PATTERN = re.compile(
    r"(?:certificate\s*(?:id|no|number)?)\s*[:\-]?\s*([A-Z0-9\-]{4,20})",
    re.IGNORECASE
)

# Ordinal dates like "6th July 2025", "23rd December 2024"
ORDINAL_DATE_PATTERN = re.compile(
    r"\d{1,2}(?:st|nd|rd|th)\s+[A-Za-z]+\s+\d{4}",
    re.IGNORECASE
)

# "This certifies that JOHN DOE has..." / "Presented to JOHN DOE"
NAME_PATTERN = re.compile(
    r"(?:certifies that|presented to|awarded to|this is to certify that)\s+"
    r"([A-Z][a-zA-Z.\s]{2,50}?)(?=\s+has|\s+for|\n|$)",
    re.IGNORECASE
)

# Grade/score like "Grade: A" or "Score: 95%"
GRADE_PATTERN = re.compile(
    r"(?:grade|score)\s*[:\-]?\s*([A-Za-z0-9+\-%.]{1,10})",
    re.IGNORECASE
)


def extract_date(text: str) -> Optional[str]:
    """
    Finds the first date-like pattern in the text. Checks ordinal
    dates ("6th July 2025") first since they're common on certificates
    but easy to miss with generic date regex, then falls back to
    numeric/standard formats.
    """
    match = ORDINAL_DATE_PATTERN.search(text)
    if match:
        return match.group(0).strip()

    match = DATE_PATTERN.search(text)
    return match.group(0).strip() if match else None


def extract_certificate_id(text: str) -> Optional[str]:
    """Finds a certificate ID/number, anchored on nearby keywords."""
    match = CERT_ID_PATTERN.search(text)
    return match.group(1).strip() if match else None


def extract_candidate_name(text: str) -> Optional[str]:
    """
    Finds the recipient's name by anchoring on common certificate
    phrasing. Falls back to None (rather than guessing) if no
    confident match is found — we prefer "unknown" over "wrong".
    """
    match = NAME_PATTERN.search(text)
    if match:
        name = re.sub(r"\s+", " ", match.group(1)).strip()

        # Strip leading OCR noise: real names never start with a
        # single stray lowercase letter (an artifact from misread
        # nearby marks/signatures). If the first token is a single
        # lowercase character, drop it.
        tokens = name.split(" ")
        if tokens and len(tokens[0]) == 1 and tokens[0].islower():
            tokens = tokens[1:]
        name = " ".join(tokens).strip()

        return name if name else None
    return None


def extract_grade(text: str) -> Optional[str]:
    match = GRADE_PATTERN.search(text)
    return match.group(1).strip() if match else None


# Explicit "Issued by" / "Organization:" style labels — most reliable
# signal when present, so we check this FIRST before falling back
# to heuristics.
ORG_LABEL_PATTERN = re.compile(
    r"(?:issued by|organization|institute|authority)\s*[:\-]?\s*"
    r"([A-Za-z0-9.,&\s]{3,60}?)(?=\n|$)",
    re.IGNORECASE
)

# Common legal/institutional suffixes. If a line contains one of these,
# it's very likely the organization name — this is a strong, language-
# agnostic-ish signal that doesn't depend on where the line sits on
# the page.
ORG_SUFFIXES = (
    "pvt", "ltd", "limited", "inc", "llc", "corp", "corporation",
    "university", "institute", "academy", "college", "foundation",
    "association", "society", "organization", "company", "group"
)


def extract_organization(text: str) -> Optional[str]:
    """
    Attempts organization extraction in order of confidence:

    1. Explicit label match ("Issued by: X", "Organization: X") —
       highest confidence, since the certificate is telling us directly.
    2. Suffix heuristic — scan all lines for legal/institutional
       suffixes like "Pvt Ltd", "University", "Institute" etc.
       Fairly reliable since these words rarely appear except in
       an organization's actual name.
    3. Positional fallback — assume it's near the top of the document
       (common for headers/logos), as a last resort.

    Returns None if nothing confident is found, rather than guessing
    wildly — a wrong "confident-looking" answer is worse than an
    honest "couldn't determine this field."
    """
    # --- Attempt 1: explicit label ---
    match = ORG_LABEL_PATTERN.search(text)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()

    # --- Attempt 2: suffix heuristic ---
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines:
        lower_line = line.lower()
        if any(suffix in lower_line for suffix in ORG_SUFFIXES):
            return line

    # --- Attempt 2b: ALL-CAPS line heuristic ---
    # Certificate headers/logos are very often rendered in full caps
    # (e.g. "TEEROP PVT. LIMITED"). A line that's mostly uppercase
    # letters and reasonably short is a decent signal too.
    for line in lines[:5]:  # only check near the top, caps further down are less likely to be the org
        letters = [c for c in line if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8 \
                and 3 <= len(line) <= 60 \
                and "certificate" not in line.lower():
            return line

    # --- Attempt 3: positional fallback (original approach) ---
    for line in lines[:3]:
        if "certificate" not in line.lower() and len(line) > 3:
            return line

    return None


def extract_fields(raw_text: str) -> Dict[str, Optional[str]]:
    """
    Main entry point: runs all field extractors against the raw OCR
    text and returns a single structured dictionary.

    Fields that couldn't be confidently extracted are returned as None
    rather than omitted, so the API response shape is always predictable
    for the frontend (no need for defensive "key in dict" checks there).
    """
    return {
        "candidate_name": extract_candidate_name(raw_text),
        "organization": extract_organization(raw_text),
        "issue_date": extract_date(raw_text),
        "certificate_id": extract_certificate_id(raw_text),
        "grade": extract_grade(raw_text),
        "raw_text": raw_text,
    }
def extract_fields_hybrid(raw_text: str) -> Dict[str, Optional[str]]:
    """
    Two-stage extraction pipeline:
    1. Regex-based extraction (extract_fields) — always runs first,
       as a reliable baseline that works offline with zero cost/latency.
    2. LLM pass — if available, treated as AUTHORITATIVE and overrides
       regex results field-by-field, since it can reason through OCR
       noise (garbled logos, typos) far better than pattern matching.
       Regex output is only kept as the final answer for a field if
       the LLM is unavailable, fails, or itself returns null for it.

    Why LLM-first instead of "fill only what's missing": regex can
    return a WRONG but non-empty value (e.g. "one g LQ" instead of
    "Cartonyx") — a naive "only fill missing fields" check would
    wrongly treat that as already solved. Trusting the LLM's judgment
    when it's available avoids that trap.
    """
    from app.core.llm_extractor import is_available, llm_extract_fields

    regex_result = extract_fields(raw_text)

    if is_available():
        llm_result = llm_extract_fields(raw_text)
        if llm_result:
            for field in ("candidate_name", "organization", "issue_date",
                          "certificate_id", "grade"):
                if llm_result.get(field):
                    regex_result[field] = llm_result[field]
                    regex_result[f"{field}_source"] = "llm"
                elif regex_result.get(field):
                    regex_result[f"{field}_source"] = "regex"
            return regex_result

    # LLM unavailable or failed entirely — regex result stands as-is.
    for field in ("candidate_name", "organization", "issue_date",
                  "certificate_id", "grade"):
        if regex_result.get(field):
            regex_result[f"{field}_source"] = "regex"

    return regex_result