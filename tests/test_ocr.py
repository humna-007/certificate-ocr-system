"""
test_ocr.py
------------
Unit tests for the core OCR pipeline: preprocessing, text extraction,
and structured field extraction. These test the underlying functions
directly, without going through the API layer — faster to run and
easier to pinpoint exactly which stage breaks if something fails.
"""

import sys
from pathlib import Path

# Allow importing from the project root when running pytest from anywhere
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.preprocessor import preprocess_image
from app.core.ocr_engine import run_ocr
from app.core.extractor import extract_fields, extract_date, extract_certificate_id

SAMPLE_CERT = Path(__file__).parent.parent / "sample_certificates" / "test_cert.png"


def test_sample_certificate_exists():
    """
    Sanity check: the test fixture itself must exist before any other
    test can run meaningfully. Fails fast with a clear message instead
    of every other test failing with a confusing FileNotFoundError.
    """
    assert SAMPLE_CERT.exists(), (
        "Sample certificate not found. Run `python tests/generate_sample.py` first."
    )


def test_preprocess_image_returns_valid_array():
    """Preprocessing should return a non-empty image array, not crash or return None."""
    result = preprocess_image(SAMPLE_CERT)
    assert result is not None
    assert result.size > 0


def test_run_ocr_extracts_text():
    """OCR should extract some non-empty text from a valid certificate image."""
    text = run_ocr(SAMPLE_CERT)
    assert isinstance(text, str)
    assert len(text.strip()) > 0


def test_run_ocr_finds_expected_name():
    """
    The generated sample certificate contains a known name ('Humna Shaukat').
    OCR on a clean, synthetic image should reliably read this correctly —
    this test would catch a regression in the OCR/preprocessing pipeline.
    """
    text = run_ocr(SAMPLE_CERT)
    assert "Humna" in text or "Shaukat" in text


def test_extract_fields_returns_all_expected_keys():
    """
    extract_fields() must always return a dict with every expected key,
    even if a field couldn't be found (as None) — the API and frontend
    both depend on this consistent shape.
    """
    sample_text = "This certifies that John Doe has completed the course. Date: 12/05/2024"
    result = extract_fields(sample_text)
    expected_keys = {"candidate_name", "organization", "issue_date",
                      "certificate_id", "grade", "raw_text"}
    assert expected_keys.issubset(result.keys())


def test_extract_date_recognizes_numeric_format():
    assert extract_date("Date: 12/05/2024") == "12/05/2024"


def test_extract_date_recognizes_ordinal_format():
    assert extract_date("held on 6th July 2025") == "6th July 2025"


def test_extract_date_returns_none_when_absent():
    assert extract_date("no date information here") is None


def test_extract_certificate_id_recognizes_labeled_id():
    result = extract_certificate_id("Certificate ID: CERT-2026-0042")
    assert result == "CERT-2026-0042"


def test_extract_certificate_id_returns_none_when_absent():
    assert extract_certificate_id("no id here") is None