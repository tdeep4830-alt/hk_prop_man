"""Processor for scraped court case .txt files from HK Judiciary LRS.

The scraper (scripts/download_court_case.py) outputs one paragraph per line.
This processor reuses CourtCaseProcessor's splitting strategies directly —
heading-based split or numbered-paragraph grouping — on the plain text.
"""

from pathlib import Path

from app.services.ingestion.base import (
    BaseProcessor,
    ChildChunk,
    ParentChunk,
    detect_language,
)
from app.services.ingestion.court_case.court_case_processor import CourtCaseProcessor

_inner = CourtCaseProcessor()


class ScrapedCaseProcessor(BaseProcessor):
    """Parse scraped .txt court judgment files into parent-child chunks."""

    def process(self, file_path: Path) -> tuple[list[ParentChunk], list[ChildChunk]]:
        text = file_path.read_text(encoding="utf-8")
        case_no = file_path.stem          # e.g. LDBM110_2009
        lang = detect_language(text)

        # Delegate to CourtCaseProcessor's existing splitting logic.
        # It operates on plain text — identical to what antiword produces.
        import re
        has_heading = any(
            re.search(rf"^(?:\d+\.\s*)?{kw}$", text, re.MULTILINE | re.IGNORECASE)
            for kw in _inner.HEADING_KEYWORDS
        )

        if has_heading:
            return _inner._split_by_headings(text, case_no, lang)
        else:
            return _inner._split_by_numbers(text, case_no, lang)
