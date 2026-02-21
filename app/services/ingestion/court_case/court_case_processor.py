"""Court case processor: parse HK legal judgments (.doc) into Parent-Child chunks.

Preserves the original HybridLegalSplitter strategies:
  Strategy A: Split by detected headings (BACKGROUND, DISCUSSION, etc.)
  Strategy B: Group adjacent numbered paragraphs (3 per parent)

Parent = full heading section OR group of 3 adjacent paragraphs
Child  = ~300 char sub-chunks for embedding

Uses `antiword` (installed in Docker) to convert .doc → plain text.
"""

import re
import subprocess
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.knowledge import DocType
from app.services.ingestion.base import (
    BaseProcessor,
    ChildChunk,
    ParentChunk,
    detect_language,
)


def _read_doc_antiword(file_path: Path) -> str:
    """Convert .doc to plain text using antiword (Docker) or textutil (macOS)."""
    # Try antiword first (available in Docker)
    try:
        result = subprocess.run(
            ["antiword", str(file_path)],
            capture_output=True, text=True, check=True,
        )
        return result.stdout
    except FileNotFoundError:
        pass

    # Fallback: macOS textutil
    try:
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(file_path)],
            capture_output=True, text=True, check=True,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    raise RuntimeError(f"Cannot read .doc file: {file_path}. Install antiword or use macOS.")


class CourtCaseProcessor(BaseProcessor):
    """Parse .doc court judgment files into parent-child chunks."""

    # Common heading keywords in HK legal judgments (EN + ZH)
    HEADING_KEYWORDS = [
        "BACKGROUND", "THE FACTS", "FACTS", "THE ISSUE", "GROUNDS OF APPEAL",
        "DISCUSSION", "CONCLUSION", "REASONS FOR JUDGMENT", "JUDGMENT",
        "背景", "事實", "事實背景", "爭議事項", "爭議點", "法律原則",
        "判決理由", "判決理由書", "結論", "判決",
    ]

    def __init__(self) -> None:
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300, chunk_overlap=50
        )

    def process(self, file_path: Path) -> tuple[list[ParentChunk], list[ChildChunk]]:
        text = _read_doc_antiword(file_path)
        case_no = file_path.stem
        lang = detect_language(text)

        has_heading = any(
            re.search(rf"^(?:\d+\.\s*)?{kw}$", text, re.MULTILINE | re.IGNORECASE)
            for kw in self.HEADING_KEYWORDS
        )

        if has_heading:
            return self._split_by_headings(text, case_no, lang)
        else:
            return self._split_by_numbers(text, case_no, lang)

    # ------------------------------------------------------------------
    # Strategy A: Heading-based splitting
    # ------------------------------------------------------------------
    def _split_by_headings(
        self, text: str, case_no: str, lang: str
    ) -> tuple[list[ParentChunk], list[ChildChunk]]:
        """Split text at heading boundaries. Each heading section = one parent."""
        # Convert headings to markdown markers for splitting
        processed = text
        for kw in self.HEADING_KEYWORDS:
            pattern = re.compile(rf"^(?:\d+\.\s*)?({kw})$", re.MULTILINE | re.IGNORECASE)
            processed = pattern.sub(r"### \1", processed)

        sections = re.split(r"(?=^### )", processed, flags=re.MULTILINE)

        parents: list[ParentChunk] = []
        children: list[ChildChunk] = []

        for section in sections:
            content = section.replace("### ", "").strip()
            if not content:
                continue

            parent_idx = len(parents)
            parents.append(ParentChunk(
                content=content,
                doc_type=DocType.COURT_CASE,
                language=lang,
                metadata={
                    "case_no": case_no,
                    "strategy": "heading",
                },
            ))

            # Create children from this section
            chunks = self.child_splitter.split_text(content)
            for chunk in chunks:
                children.append(ChildChunk(
                    search_text=f"[{case_no}] {chunk}",
                    parent_index=parent_idx,
                    language=lang,
                ))

        return parents, children

    # ------------------------------------------------------------------
    # Strategy B: Numbered paragraph grouping (3 adjacent = 1 parent)
    # ------------------------------------------------------------------
    def _split_by_numbers(
        self, text: str, case_no: str, lang: str
    ) -> tuple[list[ParentChunk], list[ChildChunk]]:
        """Group every 3 numbered paragraphs into one parent."""
        paragraphs = re.split(r"\n(?=\d+\.\s+)", text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        parents: list[ParentChunk] = []
        children: list[ChildChunk] = []

        for i in range(0, len(paragraphs), 3):
            group = paragraphs[i : i + 3]
            combined = "\n\n".join(group)

            # Extract paragraph numbers
            para_nums = []
            for p in group:
                m = re.match(r"^(\d+)\.", p)
                if m:
                    para_nums.append(m.group(1))

            para_range = f"{para_nums[0]}-{para_nums[-1]}" if para_nums else "unknown"
            parent_idx = len(parents)

            parents.append(ParentChunk(
                content=combined,
                doc_type=DocType.COURT_CASE,
                language=lang,
                metadata={
                    "case_no": case_no,
                    "strategy": "numbered_group",
                    "para_range": para_range,
                },
            ))

            # Create children
            chunks = self.child_splitter.split_text(combined)
            for chunk in chunks:
                children.append(ChildChunk(
                    search_text=f"[{case_no}] (para {para_range}) {chunk}",
                    parent_index=parent_idx,
                    language=lang,
                ))

        return parents, children
