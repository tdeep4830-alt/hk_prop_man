"""Async embedding service using Qwen3-Embedding via SiliconFlow API (1024d)."""

import asyncio

import httpx

from app.core.config import settings
from app.core.logger import logger

# SiliconFlow Qwen3-Embedding model (1024-d, cross-lingual zh/en)
_MODEL = "Qwen/Qwen3-Embedding-0.6B"
_BATCH_SIZE = 32
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2  # seconds, doubles each retry


class EmbeddingService:
    """Generate 1024-dimensional embeddings via SiliconFlow's Qwen3-Embedding endpoint."""

    def __init__(self) -> None:
        self._base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")
        self._api_key = settings.SILICONFLOW_API_KEY
        self._url = f"{self._base_url}/embeddings"

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, automatically chunked into batches of 32.

        Returns a list of 1024-d float vectors in the same order as input.
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
