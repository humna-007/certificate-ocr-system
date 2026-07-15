"""
test_api.py
------------
Integration tests for the FastAPI endpoints. These test the full
request/response cycle through the actual API layer, using FastAPI's
TestClient (which doesn't require a running server).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SAMPLE_CERT = Path(__file__).parent.parent / "sample_certificates" / "test_cert.png"


def test_health_endpoint():
    """The health check should always return 200 with the expected shape."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_extract_with_valid_image_returns_200():
    """Uploading a valid certificate image should succeed and return structured data."""
    with open(SAMPLE_CERT, "rb") as f:
        response = client.post(
            "/extract",
            files={"file": ("test_cert.png", f, "image/png")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "candidate_name" in data["data"]


def test_extract_rejects_invalid_file_type():
    """
    Uploading a disallowed file type (e.g. plain text) should be rejected
    with a 400 error, not processed or silently accepted.
    """
    fake_file = ("not_a_certificate.txt", b"just some text content", "text/plain")
    response = client.post("/extract", files={"file": fake_file})
    assert response.status_code == 400


def test_extract_rejects_missing_file():
    """Calling /extract with no file attached should fail validation, not crash."""
    response = client.post("/extract")
    assert response.status_code == 422  # FastAPI's standard "missing required field" code