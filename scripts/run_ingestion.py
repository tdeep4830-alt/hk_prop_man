"""CLI entry point for the RAG ingestion pipeline.

Usage:
    # Process all document types
    python scripts/run_ingestion.py --all

    # Process a specific type
    python scripts/run_ingestion.py --type legislation
    python scripts/run_ingestion.py --type court_case
    python scripts/run_ingestion.py --type guideline

    # Process a single file
    python scripts/run_ingestion.py --file rag_data/legislation/Cap_344.rtf

    # Dry run (parse only, no DB writes or embeddings)
    python scripts/run_ingestion.py --all --dry-run
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.logger import logger
from app.db.session import async_session_factory
from app.services.ingestion.pipeline import IngestionPipeline, _DIR_MAP, _PROCESSORS

DEFAULT_DATA_DIR = PROJECT_ROOT / "rag_data"


async def main(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)

    async with async_session_factory() as db:
        pipeline = IngestionPipeline(db=db, dry_run=args.dry_run)

        if args.file:
            # Single file mode
            file_path = Path(args.file)
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return

            # Determine processor from file extension (and path for .txt)
            ext = file_path.suffix.lower()
            if ext == ".txt":
                processor_key = "scraped_case"
            else:
                processor_key = {".rtf": "legislation", ".doc": "court_case", ".json": "guideline"}.get(ext)
            if not processor_key:
                logger.error(f"Unknown file type: {ext}. Supported: .rtf, .doc, .json, .txt")
                return

            processor = _PROCESSORS[processor_key]
            await pipeline.process_file(processor, file_path)
            pipeline._print_summary()

        elif args.type:
            # Single type mode
            if args.type not in _PROCESSORS:
                logger.error(f"Unknown type: {args.type}. Choose from: {list(_PROCESSORS.keys())}")
                return

            # Find matching directory
            for subdir_name, (proc_key, glob_pattern) in _DIR_MAP.items():
                if proc_key == args.type:
                    subdir = data_dir / subdir_name
                    if not subdir.exists():
                        logger.error(f"Directory not found: {subdir}")
                        return
                    await pipeline.run_type(args.type, subdir, glob_pattern)
                    break

            pipeline._print_summary()

        elif args.all:
            await pipeline.run_all(data_dir)

        else:
            logger.error("Specify --all, --type, or --file. Use --help for usage.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HK-PropTech AI RAG Ingestion Pipeline")
    parser.add_argument("--all", action="store_true", help="Process all document types")
    parser.add_argument("--type", type=str, help="Process a specific type (legislation, court_case, guideline)")
    parser.add_argument("--file", type=str, help="Process a single file")
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR), help="Path to rag_data directory")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, skip DB writes and embeddings")
    args = parser.parse_args()

    asyncio.run(main(args))
