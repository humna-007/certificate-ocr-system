"""
llm_extractor.py
------------------
LLM-powered fallback extraction. Regex-based extraction (extractor.py)
is fast and works offline, but struggles with stylized logos, OCR
noise, and unconventional certificate layouts (e.g. a garbled brand
name like "iE cartonyx" instead of "CARTONYX").

This module sends the raw OCR text to an LLM (via Groq) and asks it
to intelligently identify fields, tolerating typos and noise the way
a human reader naturally would.

Design: this is a FALLBACK, not a replacement. We only call the LLM
for fields the regex pass couldn't confidently fill — keeps the app
functional (and free) even without an API key or internet connection,
and only pays the LLM cost/latency when actually needed.
"""

import os
import json
from typing import Dict, Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_api_key = os.getenv("GROQ_API_KEY")
_client = Groq(api_key=_api_key) if _api_key else None

LLM_MODEL = "llama-3.1-8b-instant"  # fast + free-tier friendly

EXTRACTION_PROMPT = """You are extracting structured data from noisy OCR text of a certificate.
The text may contain typos, garbled words, and OCR artifacts (e.g. "cartonyx" might appear as "iE cartonyx" or "CARTONVX").
Use context and reasoning to identify the correct values despite noise.

Guidelines:
- If a date has an obviously impossible day (e.g. "42th"), infer the
  most likely intended day from context and correct it.
- If the certificate mentions a date RANGE (e.g. "from X to Y"), use
  only the START date as issue_date, not the full range.
- If multiple organization names appear (e.g. a parent company and a
  specific project/team name), prefer the one most directly associated
  with issuing or awarding the certificate.

Return ONLY a valid JSON object with these exact keys (use null if a field genuinely cannot be determined):
{{
  "candidate_name": string or null,
  "organization": string or null,
  "issue_date": string or null,
  "certificate_id": string or null,
  "grade": string or null
}}

Do not include any explanation, markdown formatting, or text outside the JSON object.

OCR TEXT:
{text}
"""


def is_available() -> bool:
    """Lets calling code check upfront whether LLM fallback can even run."""
    return _client is not None


def llm_extract_fields(raw_text: str) -> Optional[Dict[str, Optional[str]]]:
    """
    Sends raw OCR text to the LLM and returns parsed structured fields.
    Returns None (rather than raising) on any failure — this is a
    best-effort enhancement, and the app must keep working on the
    regex-only result if the LLM call fails for any reason (no API
    key, network issue, rate limit, malformed response, etc.).
    """
    if _client is None:
        return None

    try:
        response = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "user", "content": EXTRACTION_PROMPT.format(text=raw_text)}
            ],
            temperature=0,  # deterministic extraction, not creative writing
            max_tokens=300,
        )
        content = response.choices[0].message.content.strip()

        # Defensive cleanup: some models wrap JSON in markdown fences
        # even when told not to — strip them if present.
        if content.startswith("```"):
            content = content.strip("`")
            content = content.replace("json\n", "", 1).strip()

        parsed = json.loads(content)

        # Only keep the keys we actually expect, ignore anything extra
        # the model might hallucinate into the response.
        expected_keys = {"candidate_name", "organization", "issue_date",
                          "certificate_id", "grade"}
        return {k: parsed.get(k) for k in expected_keys}

    except Exception:
        # Covers: API errors, network failure, invalid JSON response,
        # rate limits, etc. We fail silently here because the caller
        # already has a regex-based fallback result to use instead.
        return None