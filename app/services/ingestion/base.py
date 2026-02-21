"""Base classes and shared utilities for the RAG ingestion pipeline."""

import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.models.knowledge import DocType

# Shared UUID representing public/common knowledge (statutes, court cases, guidelines).
# Queries should use: WHERE property_id IN (user_property_id, COMMON_PROPERTY_ID)
COMMON_PROPERTY_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


@dataclass
class ParentChunk:
    """A large context block (1000-1500 tokens) to be stored in parent_docs.

    This is the full content that gets fed to the LLM for reasoning.
    For legislation: a complete section (條).
    For court cases: a heading section or group of 3 adjacent paragraphs.
    For guidelines: Q + A + Source combined.
    """

    content: str
    doc_type: DocType
    property_id: uuid.UUID = field(default_factory=lambda: COMMON_PROPERTY_ID)
    metadata: dict = field(default_factory=dict)
    language: str = "zh_hk"


@dataclass
class ChildChunk:
    """A small indexed unit (200-300 tokens) stored in child_chunks.

    Carries the search_text for embedding (BGE-M3 1024d) and keyword search.
    Links back to its parent via parent_index.
    """

    search_text: str
    parent_index: int  # index into the parent list returned by the same processor
    language: str = "zh_hk"


class BaseProcessor(ABC):
    """Abstract base for all document processors.

    Each subclass reads a specific file format and splits it into
    Parent-Child pairs following the data_structure.md contract.
    """

    @abstractmethod
    def process(self, file_path: Path) -> tuple[list[ParentChunk], list[ChildChunk]]:
        """Parse a file and return (parents, children).

        Every ChildChunk.parent_index must be a valid index into the parents list.
        """
        ...


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------
_CJK_RANGE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def detect_language(text: str) -> str:
    """Heuristic language detection: >50% CJK characters → zh_hk, else en."""
    if not text:
        return "zh_hk"
    cjk_count = len(_CJK_RANGE.findall(text))
    total = len(text.replace(" ", "").replace("\n", ""))
    if total == 0:
        return "zh_hk"
    return "zh_hk" if cjk_count / total > 0.3 else "en"


def language_from_filename(filename: str) -> str:
    """Detect language from filenames like 'Cap 344 ... (English).rtf'."""
    lower = filename.lower()
    if "english" in lower:
        return "en"
    if "chinese" in lower or "traditional" in lower:
        return "zh_hk"
    return "zh_hk"
