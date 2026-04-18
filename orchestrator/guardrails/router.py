"""Guardrails API endpoints — PII scanning and content safety."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from guardrails.pii import get_pii_detector

router = APIRouter()


class ScanRequest(BaseModel):
    text: str
    enabled_types: list[str] | None = None


@router.post("/guardrails/scan")
async def scan_pii(body: ScanRequest):
    """Scan text for PII and return matches with redacted version."""
    detector = get_pii_detector()
    result = detector.scan(body.text)
    return {
        "has_pii": result.has_pii,
        "redacted_text": result.redacted_text,
        "matches": [
            {
                "type": m.pii_type,
                "start": m.start,
                "end": m.end,
                "confidence": m.confidence,
            }
            for m in result.matches
        ],
    }
