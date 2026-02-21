"""LLM provider factory with automatic fallback chain.

All providers (SiliconFlow, OpenAI) expose OpenAI-compatible APIs,
so we use langchain-openai's ChatOpenAI for everything.
"""

from langchain_openai import ChatOpenAI

from app.core.config import settings


def build_chat_llm(streaming: bool = True) -> ChatOpenAI:
    """Primary chat LLM with fallback chain.

    Chain: DeepSeek-V3 (SiliconFlow) → Qwen2.5-72B (SiliconFlow) → GPT-4o-mini (OpenAI)
    """
    primary = ChatOpenAI(
        model=settings.LLM_PRIMARY_MODEL,
        api_key=settings.SILICONFLOW_API_KEY,
        base_url=settings.SILICONFLOW_BASE_URL,
        streaming=streaming,
        temperature=0.3,
        max_tokens=2048,
    )

    fallback_silicon = ChatOpenAI(
        model=settings.LLM_FALLBACK_MODEL,
        api_key=settings.SILICONFLOW_API_KEY,
        base_url=settings.SILICONFLOW_BASE_URL,
        streaming=streaming,
        temperature=0.3,
        max_tokens=2048,
    )

    fallback_openai = ChatOpenAI(
        model=settings.LLM_OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        streaming=streaming,
        temperature=0.3,
        max_tokens=2048,
    )

    return primary.with_fallbacks([fallback_silicon, fallback_openai])


def build_router_llm() -> ChatOpenAI:
    """Fast, cheap LLM for intent classification (no streaming, temp=0)."""
    return ChatOpenAI(
        model=settings.LLM_ROUTER_MODEL,
        api_key=settings.SILICONFLOW_API_KEY,
        base_url=settings.SILICONFLOW_BASE_URL,
        streaming=False,
        temperature=0,
        max_tokens=64,
    )
