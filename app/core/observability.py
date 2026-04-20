"""Observability setup: Phoenix tracing + Prometheus metrics.

Initialise once at application startup via setup_tracing() and setup_metrics().
All LangChain spans (LLM calls, Retriever, Chain) are automatically captured
by the OpenInference instrumentor and exported to Phoenix via OTLP.
"""

from openinference.instrumentation.langchain import LangChainInstrumentor
from phoenix.otel import register
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# ---------------------------------------------------------------------------
# Custom RAG metrics
# ---------------------------------------------------------------------------

RAG_QUERY_TOTAL = Counter(
    "rag_query_total",
    "Total RAG queries processed",
    ["intent", "membership_tier"],
)

RAG_LATENCY = Histogram(
    "rag_latency_seconds",
    "End-to-end RAG pipeline latency in seconds",
    buckets=[0.5, 1, 2, 5, 10],
)

LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "LLM tokens consumed",
    ["model", "type"],  # type: "prompt" | "completion"
)

RAG_COMPLEXITY_TOTAL = Counter(
    "rag_complexity_total",
    "RAG queries broken down by complexity tier",
    ["complexity"],  # simple | medium | hard
)

RAG_CATEGORY_TOTAL = Counter(
    "rag_category_total",
    "RAG queries broken down by domain category",
    ["category"],  # one of the 14 Category enum values
)


# ---------------------------------------------------------------------------
# Initialisation helpers
# ---------------------------------------------------------------------------

def setup_tracing(phoenix_endpoint: str) -> None:
    """Configure Phoenix tracing using the official recommended pattern.

    Uses phoenix.otel.register() which correctly captures all LangChain
    metadata (prompt variables, token counts, model params) automatically.
    Avoids manually wiring TracerProvider/OTLPSpanExporter which would
    miss LangChain-specific semantic conventions.
    """
    register(endpoint=phoenix_endpoint)   # configures OTLP exporter automatically
    LangChainInstrumentor().instrument()  # auto-traces all LangChain spans


def setup_metrics(app) -> None:
    """Mount Prometheus /metrics endpoint on FastAPI."""
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
