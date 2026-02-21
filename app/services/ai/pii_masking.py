"""PII masking service for PDPO (Personal Data Privacy Ordinance) compliance.

Detects and masks Hong Kong-specific PII patterns before sending to LLM.
"""

import re
from dataclasses import dataclass, field


@dataclass
class MaskResult:
    masked_text: str
    pii_found: list[dict] = field(default_factory=list)


# Compiled regex patterns for HK-specific PII
_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    (
        "HKID",
        re.compile(r"[A-Z]{1,2}\d{6}\([0-9A]\)"),
        "[HKID]",
    ),
    (
        "UNIT_ADDRESS",
        re.compile(r"\d+座\d+樓[A-Z]室"),
        "[UNIT_REDACTED]",
    ),
    (
        "PHONE",
        re.compile(r"(?<!\d)[5689]\d{7}(?!\d)"),
        "[PHONE]",
    ),
]


class PIIMaskingService:
    """Detect and mask HKID, unit addresses, and phone numbers."""

    @staticmethod
    def mask(text: str) -> MaskResult:
        pii_found: list[dict] = []
        masked = text

        for pii_type, pattern, replacement in _PATTERNS:
            for match in pattern.finditer(masked):
                pii_found.append(
                    {
                        "type": pii_type,
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
            masked = pattern.sub(replacement, masked)

        return MaskResult(masked_text=masked, pii_found=pii_found)
