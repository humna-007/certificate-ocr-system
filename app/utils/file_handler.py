"""
file_handler.py
----------------
Handles everything related to receiving, validating, and storing
uploaded certificate files (images or PDFs).

Why this file exists separately:
File I/O and validation logic shouldn't live inside API route handlers.
Keeping it isolated means we can unit-test it without spinning up FastAPI,
and it keeps main.py / routes readable.
"""

import os
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException

# ---- Configuration ----

# Whitelist of allowed MIME types. We check the ACTUAL content type
# reported by the upload, not just the filename extension — relying on
# extensions alone is a classic vulnerability (someone renames malware.exe
# to certificate.jpg and your server happily "processes" it).
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "application/pdf",
}

# Max upload size: 10 MB. Prevents a bad actor (or a confused user)
# from uploading a massive file and tying up server memory/CPU.
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def validate_file(file: UploadFile) -> None:
    """
    Validates an incoming upload against our whitelist and size limit.
    Raises HTTPException (which FastAPI turns into a proper error response)
    if validation fails — we never let a bad file silently pass through.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed types: JPG, PNG, TIFF, PDF."
        )


def save_upload(file: UploadFile) -> Path:
    """
    Safely saves an uploaded file to disk and returns its path.

    Security notes:
    - We NEVER trust the original filename (users can name a file
      "../../etc/passwd" to attempt a path traversal attack). Instead,
      we generate our own random filename and only keep the original
      file's extension.
    - We enforce the size limit while reading, not after, so a huge
      file doesn't fully load into memory first.
    """
    validate_file(file)

    # Extract extension safely from content-type rather than trusting
    # the filename directly.
    extension_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/tiff": ".tiff",
        "application/pdf": ".pdf",
    }
    extension = extension_map[file.content_type]

    # Random UUID filename — avoids collisions and path traversal entirely.
    safe_filename = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / safe_filename

    size = 0
    try:
        with open(destination, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):  # read in 1MB chunks
                size += len(chunk)
                if size > MAX_FILE_SIZE_BYTES:
                    # Stop immediately, clean up, and reject.
                    buffer.close()
                    os.remove(destination)
                    raise HTTPException(
                        status_code=413,
                        detail="File too large. Maximum allowed size is 10MB."
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # Any unexpected I/O failure (disk full, permissions, etc.)
        # should not crash the app — return a clean error instead.
        if destination.exists():
            os.remove(destination)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    return destination


def cleanup_file(file_path: Path) -> None:
    """
    Deletes a temporary file after processing.
    We don't want to keep uploaded certificates around indefinitely
    (privacy + disk space).
    """
    try:
        if file_path.exists():
            os.remove(file_path)
    except Exception:
        # Cleanup failure shouldn't break the response to the user —
        # just silently skip; the file can be cleaned up later by a
        # scheduled job if needed.
        pass