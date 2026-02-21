"""Legislation processor: parse Hong Kong ordinances (RTF) into Parent-Child chunks.

Preserves the original ParentChildParser logic:
  Part (部) → Sub-part (次分部) → Section (條) → Subsection (款)

Parent = full section text (一整『條』的內容)
Child  = individual subsections or ~300 char segments for embedding
"""

import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from striprtf.striprtf import rtf_to_text

from app.models.knowledge import DocType
from app.services.ingestion.base import (
    BaseProcessor,
    ChildChunk,
    ParentChunk,
    language_from_filename,
)


class LegislationProcessor(BaseProcessor):
    """Parse .rtf ordinance files into parent-child chunks."""

    def __init__(self) -> None:
        self.part_pattern = re.compile(
            r"^第\s*([0-9A-Z]+|[IVXLCDM]+)\s*(部|分部)(?:\s*[——|—\-]\s*(.*))?$",
            re.IGNORECASE,
        )
        self.subpart_pattern = re.compile(
            r"^第\s*([0-9A-Z]+|[IVXLCDM]+)\s*次分部(?:\s*[——|—\-]\s*(.*))?$",
            re.IGNORECASE,
        )
        self.section_pattern = re.compile(r"^(\d+[A-Z]?)\.\s*(.*)")
        self.subsection_pattern = re.compile(r"^\((\d+[A-Z]?)\)\s*(.*)")
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300, chunk_overlap=50
        )

    def process(self, file_path: Path) -> tuple[list[ParentChunk], list[ChildChunk]]:
        # --- Read RTF ---
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        text = rtf_to_text(raw)
        lang = language_from_filename(file_path.name)

        # Extract ordinance ID from filename: "Cap 344 RTF ..." → "Cap344"
        cap_match = re.search(r"Cap\s*(\d+[A-Z]?)", file_path.name, re.IGNORECASE)
        ordinance_id = f"Cap{cap_match.group(1)}" if cap_match else file_path.stem

        # --- Parse structure ---
        parents, children = self._parse(text, ordinance_id, lang)
        return parents, children

    def _parse(
        self, full_text: str, ordinance_id: str, lang: str
    ) -> tuple[list[ParentChunk], list[ChildChunk]]:
        parents: list[ParentChunk] = []
        children: list[ChildChunk] = []

        lines = [line.strip() for line in full_text.split("\n") if line.strip()]

        current_part = "未分類"
        current_subpart = "一般規定"
        section_buffer: list[str] = []
        current_sec_num: str | None = None
        current_sec_title: str | None = None

        def flush_section() -> None:
            nonlocal current_sec_num, current_sec_title
            if not current_sec_num or not section_buffer:
                return

            # --- Parent: full section content ---
            full_section_text = "\n".join(section_buffer)
            parent_idx = len(parents)
            parent = ParentChunk(
                content=full_section_text,
                doc_type=DocType.STATUTE,
                language=lang,
                metadata={
                    "ordinance": ordinance_id,
                    "part": current_part,
                    "subpart": current_subpart,
                    "section": current_sec_num,
                    "title": current_sec_title,
                },
            )
            parents.append(parent)

            # --- Children: subsection-based splitting ---
            sub_children = self._create_children(
                section_buffer, parent_idx, ordinance_id,
                current_sec_num, current_sec_title,
                current_part, current_subpart, lang,
            )
            children.extend(sub_children)
            section_buffer.clear()

        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect Part (部 / 分部)
            part_match = self.part_pattern.match(line)
            if part_match:
                flush_section()
                num = part_match.group(1)
                type_name = part_match.group(2)
                title = part_match.group(3)
                if not title and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if not self.part_pattern.match(next_line) and not self.section_pattern.match(next_line):
                        title = next_line
                        i += 1
                current_part = f"第{num}{type_name} ({title if title else ''})"
                current_subpart = "一般規定"
                i += 1
                continue

            # Detect Sub-part (次分部)
            subpart_match = self.subpart_pattern.match(line)
            if subpart_match:
                flush_section()
                num = subpart_match.group(1)
                title = subpart_match.group(2)
                if not title and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if not self.part_pattern.match(next_line) and not self.section_pattern.match(next_line):
                        title = next_line
                        i += 1
                current_subpart = f"第{num}次分部 ({title if title else ''})"
                i += 1
                continue

            # Detect Section (條)
            sec_match = self.section_pattern.match(line)
            if sec_match:
                flush_section()
                current_sec_num = sec_match.group(1)
                current_sec_title = sec_match.group(2).strip()
                section_buffer.append(line)
            elif current_sec_num:
                section_buffer.append(line)

            i += 1

        flush_section()
        return parents, children

    def _create_children(
        self,
        buffer: list[str],
        parent_idx: int,
        ordinance_id: str,
        sec_num: str,
        sec_title: str | None,
        part: str,
        subpart: str,
        lang: str,
    ) -> list[ChildChunk]:
        """Split a section into subsection-based child chunks.

        Each child's search_text is enriched with contextual breadcrumbs
        for better retrieval accuracy.
        """
        nodes: list[ChildChunk] = []
        current_sub_id = "intro"
        current_sub_text: list[str] = []

        def save_child() -> None:
            content = "\n".join(current_sub_text).strip()
            if not content:
                return
            # Enriched search text with breadcrumbs
            enriched = (
                f"[{ordinance_id}] [{part}] [{subpart}] "
                f"[第{sec_num}條: {sec_title}] (第{current_sub_id}款) {content}"
            )
            # If enriched text is too long, further split
            if len(enriched) > 400:
                chunks = self.child_splitter.split_text(enriched)
                for chunk in chunks:
                    nodes.append(ChildChunk(
                        search_text=chunk, parent_index=parent_idx, language=lang
                    ))
            else:
                nodes.append(ChildChunk(
                    search_text=enriched, parent_index=parent_idx, language=lang
                ))
            current_sub_text.clear()

        for line in buffer:
            sub_match = self.subsection_pattern.match(line)
            if sub_match:
                save_child()
                current_sub_id = sub_match.group(1)
                current_sub_text.append(line)
            else:
                current_sub_text.append(line)

        save_child()
        return nodes
