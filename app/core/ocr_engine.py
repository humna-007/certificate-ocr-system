"""
ocr_engine.py
--------------
Wraps Tesseract OCR (via pytesseract) to extract raw text from
preprocessed images, and handles PDF-to-image conversion.

Why wrap it instead of calling pytesseract directly in routes.py:
- Keeps Tesseract-specific config (path, language, page segmentation mode)
  in ONE place, so if we ever need to tune OCR settings, we change it here
  and nowhere else.
- Makes it easy to swap OCR engines later (e.g. add EasyOCR as a fallback)
  without touching the rest of the app.
"""

import pytesseract
import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path
from typing import List
import numpy as np
from PIL import Image

from app.core.preprocessor import preprocess_image

# ---- Tesseract Configuration ----
# On Windows, pytesseract often can't find tesseract.exe automatically
# unless it's on PATH. If you hit "TesseractNotFoundError", uncomment
# and set this to your actual install path:
#
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Page Segmentation Mode 6 = "Assume a single uniform block of text".
# Certificates are usually laid out this way, so this mode performs
# better than Tesseract's default (which tries to detect complex
# multi-column layouts, unnecessary for our use case).
TESSERACT_CONFIG = "--oem 3 --psm 6"


def pdf_to_images(pdf_path: Path) -> List[Image.Image]:
    """
    Converts each page of a PDF into a PIL Image, so the OCR pipeline
    can treat PDFs and photos identically downstream.

    Uses PyMuPDF (fitz) instead of pdf2image/Poppler — PyMuPDF is a
    self-contained Python library with no external system dependency,
    which avoids Poppler installation/PATH issues entirely and makes
    the project easier to set up on any machine.
    """
    try:
        images = []
        pdf_document = fitz.open(str(pdf_path))
        for page in pdf_document:
            # Render at 2x zoom for better OCR accuracy on smaller text
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        pdf_document.close()
        return images
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed. Original error: {e}")


def extract_text_from_image(preprocessed_image: np.ndarray) -> str:
    """
    Runs Tesseract on a single already-preprocessed image array
    and returns the raw extracted text.
    """
    try:
        text = pytesseract.image_to_string(
            preprocessed_image, config=TESSERACT_CONFIG
        )
        return text.strip()
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "Tesseract OCR engine not found. Verify installation and "
            "that it's added to your system PATH."
        )
    except Exception as e:
        raise RuntimeError(f"OCR text extraction failed: {e}")


def run_ocr(file_path: Path) -> str:
    """
    Main entry point for OCR. Detects whether the input is a PDF or
    an image and routes accordingly, then returns the combined
    extracted text (all pages, for multi-page PDFs).

    This is the ONE function the API layer needs to call — it hides
    all the PDF-vs-image branching logic.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        pages = pdf_to_images(file_path)
        all_text = []
        for i, page in enumerate(pages):
            # Save each page temporarily as an image so our existing
            # preprocess_image() function (which expects a file path)
            # can be reused without duplicating logic.
            temp_page_path = file_path.parent / f"{file_path.stem}_page{i}.png"
            page.save(temp_page_path)
            try:
                preprocessed = preprocess_image(temp_page_path)
                page_text = extract_text_from_image(preprocessed)
                all_text.append(page_text)
            finally:
                # Always clean up the temp page image, even if OCR fails
                # on this page — we don't want orphaned files piling up.
                if temp_page_path.exists():
                    temp_page_path.unlink()
        return "\n\n".join(all_text)

    else:
        # Standard image formats (jpg, png, tiff)
        preprocessed = preprocess_image(file_path)
        return extract_text_from_image(preprocessed)