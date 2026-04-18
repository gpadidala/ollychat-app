"""PII Detection Engine — scans text for 18 categories of personally identifiable information.

Adapted from llm-o11y-platform/src/guardrails/pii.py with full regex patterns,
confidence scoring, and overlap detection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

PII_PATTERNS: dict[str, tuple[str, float, str]] = {
    # (pattern, confidence, redaction_label)
    "email": (
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        0.95, "[EMAIL_REDACTED]",
    ),
    "phone_us": (
        r"(?<!\d)(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)",
        0.85, "[PHONE_REDACTED]",
    ),
    "phone_international": (
        r"(?<!\d)\+\d{1,3}[\s.\-]?\d{2,4}[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}(?!\d)",
        0.70, "[PHONE_REDACTED]",
    ),
    "ssn": (
        r"(?<!\d)\d{3}[\s\-]\d{2}[\s\-]\d{4}(?!\d)",
        0.90, "[SSN_REDACTED]",
    ),
    "credit_card_visa": (
        r"(?<!\d)4\d{3}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)",
        0.90, "[CREDIT_CARD_REDACTED]",
    ),
    "credit_card_mastercard": (
        r"(?<!\d)5[1-5]\d{2}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)",
        0.90, "[CREDIT_CARD_REDACTED]",
    ),
    "credit_card_amex": (
        r"(?<!\d)3[47]\d{2}[\s\-]?\d{6}[\s\-]?\d{5}(?!\d)",
        0.90, "[CREDIT_CARD_REDACTED]",
    ),
    "ip_address_v4": (
        r"(?<!\d)(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?!\d)",
        0.80, "[IP_REDACTED]",
    ),
    "api_key_openai": (
        r"\bsk-[A-Za-z0-9]{20,}(?:\b|$)",
        0.95, "[API_KEY_REDACTED]",
    ),
    "api_key_github": (
        r"\bghp_[A-Za-z0-9]{36,}\b",
        0.95, "[API_KEY_REDACTED]",
    ),
    "api_key_slack": (
        r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b",
        0.90, "[API_KEY_REDACTED]",
    ),
    "api_key_aws": (
        r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
        0.95, "[API_KEY_REDACTED]",
    ),
    "api_key_generic": (
        r"(?:api[_-]?key|token|secret|password|bearer)\s*[=:]\s*['\"]?([A-Za-z0-9+/=\-_]{40,})['\"]?",
        0.70, "[API_KEY_REDACTED]",
    ),
    "date_of_birth": (
        r"(?<!\d)(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})(?!\d)",
        0.60, "[DOB_REDACTED]",
    ),
    "address_us": (
        r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s?){1,3}(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Road|Rd|Court|Ct|Way|Place|Pl)\b",
        0.65, "[ADDRESS_REDACTED]",
    ),
}

# Compile patterns once
_COMPILED: dict[str, re.Pattern] = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, (pattern, _, _) in PII_PATTERNS.items()
}


@dataclass
class PIIMatch:
    pii_type: str
    start: int
    end: int
    matched_text: str
    confidence: float
    redaction_label: str


@dataclass
class PIIDetectionResult:
    original_text: str
    redacted_text: str
    matches: list[PIIMatch] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return len(self.matches) > 0


class PIIDetector:
    """Scans text for PII patterns with overlap detection and configurable redaction."""

    def __init__(self, enabled_types: list[str] | None = None):
        self.enabled_types = enabled_types or list(PII_PATTERNS.keys())

    def scan(self, text: str) -> PIIDetectionResult:
        """Scan text for PII. Returns matches with positions and a redacted version."""
        all_matches: list[PIIMatch] = []

        for pii_type in self.enabled_types:
            if pii_type not in _COMPILED:
                continue
            pattern = _COMPILED[pii_type]
            _, confidence, label = PII_PATTERNS[pii_type]

            for m in pattern.finditer(text):
                all_matches.append(PIIMatch(
                    pii_type=pii_type,
                    start=m.start(),
                    end=m.end(),
                    matched_text=m.group(),
                    confidence=confidence,
                    redaction_label=label,
                ))

        # Remove overlapping matches (keep higher confidence)
        all_matches.sort(key=lambda m: (-m.confidence, m.start))
        filtered: list[PIIMatch] = []
        used_ranges: list[tuple[int, int]] = []
        for match in all_matches:
            overlaps = any(
                match.start < end and match.end > start
                for start, end in used_ranges
            )
            if not overlaps:
                filtered.append(match)
                used_ranges.append((match.start, match.end))

        filtered.sort(key=lambda m: m.start)

        # Build redacted text
        redacted = text
        for match in reversed(filtered):
            redacted = redacted[:match.start] + match.redaction_label + redacted[match.end:]

        return PIIDetectionResult(
            original_text=text,
            redacted_text=redacted,
            matches=filtered,
        )


# Singleton
_detector: PIIDetector | None = None

def get_pii_detector() -> PIIDetector:
    global _detector
    if _detector is None:
        _detector = PIIDetector()
    return _detector
