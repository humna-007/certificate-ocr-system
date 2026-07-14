"""
main.py
--------
Application entry point. Defines the FastAPI app and its REST endpoints.

Design note: routes here stay THIN — they handle HTTP concerns only
(receiving requests, returning responses, translating errors into
proper status codes). All actual logic lives in app/core and
app/utils, which we already built and tested independently. This
separation is what makes the codebase testable and maintainable.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.utils.file_handler import save_upload, cleanup_file
from app.core.ocr_engine import run_ocr
from app.core.extractor import extract_fields_hybrid

app = FastAPI(
    title="Certificate OCR System",
    description="Extracts structured data from certificate images/PDFs using Tesseract OCR",
    version="1.0.0"
)

# CORS: allows our frontend (served separately, e.g. from a different
# port during development) to actually call this API from the browser.
# In production this should be locked down to the real frontend domain
# instead of "*" — noted here deliberately as a security consideration.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Basic liveness check — used to confirm the server is up."""
    return {"status": "ok", "service": "certificate-ocr-system"}


@app.post("/extract")
async def extract_certificate(file: UploadFile = File(...)):
    """
    Main pipeline endpoint. Accepts one certificate file (image or PDF),
    runs it through: save -> OCR -> field extraction -> cleanup,
    and returns structured JSON.

    Every failure point is wrapped so the client always gets a clean
    JSON error response instead of a raw server crash / stack trace
    (which would both look unprofessional AND leak internal details —
    a real security concern).
    """
    saved_path: Path | None = None

    try:
        # Step 1: validate + save upload
        saved_path = save_upload(file)

        # Step 2: run OCR (includes preprocessing internally)
        raw_text = run_ocr(saved_path)

        if not raw_text.strip():
            # OCR ran but found nothing — likely a blank/blurry image.
            # This is a legitimate outcome, not a crash, so we respond
            # with a clear message rather than an empty/confusing result.
            raise HTTPException(
                status_code=422,
                detail="No text could be extracted from this image. "
                       "Try a clearer photo or scan."
            )

        # Step 3: parse structured fields from raw text
        structured_data = extract_fields_hybrid(raw_text)

        return {
            "success": True,
            "data": structured_data
        }

    except HTTPException:
        # Already a clean, intentional error (e.g. bad file type,
        # too large, no text found) — just let it propagate as-is.
        raise

    except RuntimeError as e:
        # Raised by our OCR/preprocessing layer for expected failure
        # modes (Tesseract missing, Poppler missing, corrupted image).
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        # Truly unexpected failure. We log this server-side in a real
        # deployment (not done here yet) but NEVER expose raw internal
        # error details to the client — that's an information leak.
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the file."
        )

    finally:
        # Always clean up the uploaded file, whether processing
        # succeeded or failed — we don't want failed uploads piling
        # up on disk either.
        if saved_path is not None:
            cleanup_file(saved_path)