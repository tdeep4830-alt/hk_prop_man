"""Adaptive complexity classifier for query-based RAG routing.

Classifies user queries into three complexity tiers:
  simple → direct LLM answer (no retrieval)
  medium → standard single-step Hybrid RAG
  hard   → multi-hop retrieval and reasoning
"""

import enum

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.logger import logger
from app.services.ai.llm_provider import build_router_llm
from app.services.ai.prompts import COMPLEXITY_ROUTER_PROMPT


class Complexity(str, enum.Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    HARD = "hard"


_VALID_COMPLEXITIES = {c.value for c in Complexity}

_complexity_prompt = PromptTemplate.from_template(COMPLEXITY_ROUTER_PROMPT)
_complexity_chain = _complexity_prompt | build_router_llm() | StrOutputParser()


class ComplexityClassifier:
    """Classify a user query into a complexity tier to select the RAG strategy."""

    @staticmethod
    async def classify(query: str) -> Complexity:
        try:
            raw = await _complexity_chain.ainvoke({"query": query})
            complexity_str = raw.strip().lower()
            if complexity_str in _VALID_COMPLEXITIES:
                return Complexity(complexity_str)
            logger.warning(
                "Complexity classifier returned unknown value", extra={"raw": raw}
            )
        except Exception as e:
            logger.warning(
                "Complexity classification failed", extra={"error": str(e)}
            )

        # Safe fallback — always run standard RAG rather than skipping or over-fetching
        return Complexity.MEDIUM
