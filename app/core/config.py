"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for HK-PropTech AI."""

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://propman:propman_secret@db:5432/propman_ai"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- LLM Providers ---
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # --- RAG (Phase 4) ---
    RAG_SCORE_THRESHOLD: float = 0.35
    RAG_TOP_K: int = 5
    RAG_MAX_HISTORY_TURNS: int = 5
    LLM_PRIMARY_MODEL: str = "deepseek-ai/DeepSeek-V3"
    LLM_FALLBACK_MODEL: str = "Qwen/Qwen2.5-72B-Instruct"
    LLM_ROUTER_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    LLM_OPENAI_MODEL: str = "gpt-4o-mini"

    # --- JWT ---
    JWT_SECRET: str = "change_me_to_a_random_secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # --- Observability (Phase 6) ---
    PHOENIX_ENDPOINT: str = "http://phoenix:6006/v1/traces"
    ENABLE_TRACING: bool = True

    # --- App ---
    ENVIRONMENT: str = "development"
    DEFAULT_LANG: str = "zh_hk"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # --- Membership quota (daily LLM calls) ---
    QUOTA_LIMITS: dict[str, int] = {"free": 10, "pro": 100, "enterprise": -1}

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
