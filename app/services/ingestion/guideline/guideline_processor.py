"""Guideline processor: parse Q&A JSON into Parent-Child chunks.

Parent = Question + Answer + Source (full context for LLM reasoning)
Child  = Question text (for embedding hit) + answer sub-chunks
"""

import json
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.knowledge import DocType
from app.services.ingestion.base import (
    BaseProcessor,
    ChildChunk,
    ParentChunk,
    detect_language,
)


class GuidelineProcessor(BaseProcessor):
    """Parse guideline JSON files into parent-child chunks."""

    def __init__(self) -> None:
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300, chunk_overlap=50
        )

    def process(self, file_path: Path) -> tuple[list[ParentChunk], list[ChildChunk]]:
        raw = file_path.read_text(encoding="utf-8")
        items: list[dict] = json.loads(raw)

        parents: list[ParentChunk] = []
        children: list[ChildChunk] = []

        for item in items:
            question = item.get("question", "")
            answer = item.get("answer", "")
            source = item.get("source", "")
            tags = item.get("tags", [])

            # --- Parent: full Q + A + Source context ---
            full_text = f"問題：{question}\n答案：{answer}\n參考依據：{source}"
            lang = detect_language(full_text)
            parent_idx = len(parents)

            parents.append(ParentChunk(
                content=full_text,
                doc_type=DocType.GUIDELINE,
                language=lang,
                metadata={
                    "source": source,
                    "tags": tags,
                    "type": "common_practice",
                },
            ))

            # --- Children ---
            # Child 1: the question itself (high retrieval hit rate)
            children.append(ChildChunk(
                search_text=question,
                parent_index=parent_idx,
                language=lang,
            ))

            # Child 2+: split the answer into ~300 char chunks
            if len(answer) > 300:
                answer_chunks = self.child_splitter.split_text(answer)
                for chunk in answer_chunks:
                    children.append(ChildChunk(
                        search_text=chunk,
                        parent_index=parent_idx,
                        language=lang,
                    ))
            else:
                children.append(ChildChunk(
                    search_text=answer,
                    parent_index=parent_idx,
                    language=lang,
                ))

        return parents, children
