"""Unified RAG ingestion pipeline.

Scans rag_data/ subdirectories, dispatches to the appropriate processor,
generates embeddings via BGE-M3, and writes parent_docs + child_chunks to DB.
"""

import uuid
from pathlib import Path

from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.models.knowledge import ChildChunk as ChildChunkModel
from app.models.knowledge import ParentDoc
from app.services.ingestion.base import (
    COMMON_PROPERTY_ID,
    BaseProcessor,
    ChildChunk,
    ParentChunk,
    detect_language,
)
from app.services.ingestion.court_case.court_case_processor import CourtCaseProcessor
from app.services.ingestion.embedding import EmbeddingService
from app.services.ingestion.guideline.guideline_processor import GuidelineProcessor
from app.services.ingestion.legislation.legislation_parser import LegislationProcessor

# ---------------------------------------------------------------------------
# File type → processor mapping
# ---------------------------------------------------------------------------
_PROCESSORS: dict[str, BaseProcessor] = {
    "legislation": LegislationProcessor(),
    "court_case": CourtCaseProcessor(),
    "guideline": GuidelineProcessor(),
}

# Subdirectory name → processor key + file glob
_DIR_MAP: dict[str, tuple[str, str]] = {
    "legislation": ("legislation", "*.rtf"),
    "Count_case": ("court_case", "*.doc"),
    "guideline": ("guideline", "*.json"),
}


class IngestionPipeline:
    """Orchestrate the full ingestion flow: parse → embed → store."""

    def __init__(self, db: AsyncSession, dry_run: bool = False) -> None:
        self.db = db
        self.dry_run = dry_run
        self.embedding_service = EmbeddingService()

        # Counters
        self.total_parents = 0
        self.total_children = 0
        self.total_files = 0
        self.failed_files: list[str] = []

    async def run_all(self, data_dir: Path) -> None:
        """Scan all subdirectories in data_dir and process everything."""
        for subdir_name, (processor_key, glob_pattern) in _DIR_MAP.items():
            subdir = data_dir / subdir_name
            if not subdir.exists():
                logger.warning(f"Skipping missing directory: {subdir}")
                continue
            await self.run_type(processor_key, subdir, glob_pattern)

        self._print_summary()

    async def run_type(
        self, processor_key: str, directory: Path, glob_pattern: str
    ) -> None:
        """Process all files of a specific type in a directory."""
        processor = _PROCESSORS[processor_key]
        files = sorted(directory.glob(glob_pattern))
        logger.info(
            f"Processing {processor_key}",
            extra={"directory": str(directory), "file_count": len(files)},
        )

        for i, file_path in enumerate(files, 1):
            try:
                await self.process_file(processor, file_path)
                self.total_files += 1
                logger.info(
                    f"[{i}/{len(files)}] Done: {file_path.name}",
                    extra={"parents": self.total_parents, "children": self.total_children},
                )
            except Exception as e:
                self.failed_files.append(str(file_path))
                logger.error(f"Failed: {file_path.name}", extra={"error": str(e)})

    async def process_file(self, processor: BaseProcessor, file_path: Path) -> None:
        """Process a single file: parse → detect language → embed → store.

        Language detection is applied per-chunk on the actual content:
        - Parent: detect_language(content) — determines TSVector config
        - Child:  detect_language(search_text) — stored in child_chunks.language
        No translation is performed; original legal text is preserved as-is.
        BGE-M3's cross-lingual alignment handles mixed-language retrieval.
        """
        parents, children = processor.process(file_path)

        if not parents:
            logger.warning(f"No parents extracted from {file_path.name}")
            return

        # --- Per-chunk language detection ---
        # Parent: scan content to set language (used for TSVector config)
        for parent in parents:
            parent.language = detect_language(parent.content)

        # Child: scan each search_text independently
        lang_stats = {"zh_hk": 0, "en": 0}
        for child in children:
            child.language = detect_language(child.search_text)
            lang_stats[child.language] += 1

        if self.dry_run:
            logger.info(
                f"[DRY RUN] {file_path.name}",
                extra={
                    "parents": len(parents),
                    "children": len(children),
                    "lang_zh_hk": lang_stats["zh_hk"],
                    "lang_en": lang_stats["en"],
                },
            )
            self.total_parents += len(parents)
            self.total_children += len(children)
            return

        # --- Write parents to DB ---
        parent_id_map: dict[int, uuid.UUID] = {}
        for idx, parent in enumerate(parents):
            parent_id = uuid.uuid4()
            parent_id_map[idx] = parent_id

            db_parent = ParentDoc(
                id=parent_id,
                property_id=parent.property_id,
                content=parent.content,
                doc_type=parent.doc_type,
                metadata_=parent.metadata,
            )
            self.db.add(db_parent)

        await self.db.flush()

        # --- Update TSVector for parents (config depends on detected language) ---
        for idx, parent in enumerate(parents):
            pid = parent_id_map[idx]
            # English: full stemming/stop-words via 'english' config
            # Chinese: 'simple' config (no stemming, preserves all tokens)
            ts_config = "english" if parent.language == "en" else "simple"
            await self.db.execute(
                text(
                    "UPDATE parent_docs SET search_vector = to_tsvector(:cfg, content) "
                    "WHERE id = :pid"
                ),
                {"cfg": ts_config, "pid": pid},
            )

        # --- Generate embeddings for children via BGE-M3 (cross-lingual) ---
        # BGE-M3 natively handles zh/en in the same vector space;
        # no translation needed — original text goes directly to embedding.
        search_texts = [c.search_text for c in children]
        embeddings = await self.embedding_service.embed_batch(search_texts)

        # --- Write children to DB ---
        for child, embedding in zip(children, embeddings):
            parent_uuid = parent_id_map[child.parent_index]
            db_child = ChildChunkModel(
                id=uuid.uuid4(),
                parent_id=parent_uuid,
                embedding=embedding,
                language=child.language,
                search_text=child.search_text,
            )
            self.db.add(db_child)

        await self.db.commit()

        self.total_parents += len(parents)
        self.total_children += len(children)

    def _print_summary(self) -> None:
        logger.info(
            "Ingestion complete",
            extra={
                "files_processed": self.total_files,
                "total_parents": self.total_parents,
                "total_children": self.total_children,
                "failed_files": len(self.failed_files),
            },
        )
        if self.failed_files:
            logger.warning(f"Failed files: {self.failed_files}")
