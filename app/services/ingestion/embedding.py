"""Async embedding service using Qwen3-Embedding-4B via SiliconFlow API.

Upgraded from Qwen3-Embedding-0.6B (1024d) to Qwen3-Embedding-4B with
Matryoshka truncation to 1536d.

Why 1536d:
  - Qwen3-Embedding-4B has 7x more parameters → much better semantic quality
  - Matryoshka representation learning lets us request any sub-dimension
  - 1536d stays within pgvector HNSW's 2000-dimension hard limit
  - 50% more signal than 1024d with the same DB schema

pgvector HNSW limit: 2000d (both HNSW and IVFFlat).
"""

import asyncio

import httpx

from app.core.config import settings
from app.core.logger import logger

# Qwen3-Embedding-4B with Matryoshka truncation to 1536d
# Stays within pgvector's 2000d HNSW limit while using the stronger 4B model.
_MODEL = "Qwen/Qwen3-Embedding-4B"
_EMBEDDING_DIM = 1536
_BATCH_SIZE = 32
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2  # seconds, doubles each retry


class EmbeddingService:
    """Generate 1536-dimensional embeddings via SiliconFlow's Qwen3-Embedding-4B endpoint."""

    def __init__(self) -> None:
        self._base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")
        self._api_key = settings.SILICONFLOW_API_KEY
        self._url = f"{self._base_url}/embeddings"

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, automatically chunked into batches of 32.

        Returns a list of 1536-d float vectors in the same order as input.
        """
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            embeddings = await self._call_api(batch)
            all_embeddings.extend(embeddings)
            logger.info(
                "Embedded batch",
                extra={"batch": f"{i // _BATCH_SIZE + 1}", "size": len(batch)},
            )

        return all_embeddings

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text string."""
        result = await self._call_api([text])
        return result[0]

    async def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Call SiliconFlow embedding API with retry + exponential backoff."""
        payload = {
            "model": _MODEL,
            "input": texts,
            "encoding_format": "float",
            "dimensions": _EMBEDDING_DIM,   # Matryoshka truncation to 1536d
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(self._url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    # OpenAI-compatible response: data["data"][i]["embedding"]
                    sorted_items = sorted(data["data"], key=lambda x: x["index"])
                    return [item["embedding"] for item in sorted_items]
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                wait = _RETRY_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    "Embedding API error, retrying",
                    extra={"attempt": attempt, "error": str(e), "wait_s": wait},
                )
                if attempt == _MAX_RETRIES:
                    raise
                await asyncio.sleep(wait)

        raise RuntimeError("Embedding API call failed after all retries")
