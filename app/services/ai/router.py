"""Semantic intent router using a lightweight LLM for classification."""

import enum

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.logger import logger
from app.services.ai.llm_provider import build_router_llm
from app.services.ai.prompts import ROUTER_PROMPT


class Intent(str, enum.Enum):
    LEGAL_DEFINITION = "legal_definition"
    SOP_PROCEDURE = "sop_procedure"
    DISPUTE = "dispute"


_VALID_INTENTS = {i.value for i in Intent}

# Build LCEL chain once at module level (stateless, reusable)
_router_prompt = PromptTemplate.from_template(ROUTER_PROMPT)
_router_chain = _router_prompt | build_router_llm() | StrOutputParser()


class SemanticRouter:
    """Classify user queries into one of three intents."""

    @staticmethod
    async def classify(query: str) -> Intent:
        try:
            raw = await _router_chain.ainvoke({"query": query})
            intent_str = raw.strip().lower()
            if intent_str in _VALID_INTENTS:
                return Intent(intent_str)
            logger.warning("Router returned unknown intent", extra={"raw": raw})
        except Exception as e:
            logger.warning("Router classification failed", extra={"error": str(e)})

        return Intent.LEGAL_DEFINITION
