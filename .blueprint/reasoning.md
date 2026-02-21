Phase 4 Implementation Plan: RAG AI Chat Pipeline                                     

                                                                                       

 Context                                                                               

                                                        

 Phase 1-3 complete: Docker infra, JWT auth, ingestion pipeline (4,801 parents, 35,646

  children with 1024d embeddings in DB). Phase 4 builds the complete RAG chat pipeline

  with PII masking, LLM routing, semantic intent classification, streaming output,

 citations, and observability.



 ---

 New File Structure



 app/services/ai/

     __init__.py

     pii_masking.py        # PIIMaskingService (PDPO regex)

     retriever.py          # HybridRetriever (vector + keyword, score threshold)

     llm_provider.py       # LLM factory with .with_fallbacks()

     prompts.py            # System prompts + 3 intent templates

     router.py             # SemanticRouter (intent classification)

     rag_chain.py          # Main orchestrator (ties everything together)

     memory.py             # DB-backed conversation memory (last 5 turns)

     telemetry.py          # AuditLog-based observability



 app/api/v1/chat.py        # POST /api/v1/chat (SSE streaming)

 app/schemas/chat.py        # ChatRequest, ChatResponse, CitationItem



 ---

 Implementation Order (15 steps)



 Step 1: Config additions (app/core/config.py)



 Add: OPENAI_API_KEY, RAG_SCORE_THRESHOLD (0.35), RAG_TOP_K (5), RAG_MAX_HISTORY_TURNS

  (5), LLM_PRIMARY_MODEL, LLM_FALLBACK_MODEL, LLM_ROUTER_MODEL, LLM_OPENAI_MODEL



 Step 2: Dependencies (requirements.txt)



 Add: langchain-openai>=0.1, langchain-core>=0.2



 Step 3: PII Masking (app/services/ai/pii_masking.py)



 - PIIMaskingService with 3 regex patterns:

   - HKID: [A-Z]{1,2}\d{6}\([0-9A]\) → [HKID]

   - UNIT_ADDRESS: \d+座\d+樓[A-Z]室 → [UNIT_REDACTED]

   - PHONE: (?<!\d)[5689]\d{7}(?!\d) → [PHONE]

 - Returns MaskResult(masked_text, pii_found: list[dict])

 - Pure sync function, no DB dependency



 Step 4: LLM Provider Factory (app/services/ai/llm_provider.py)



 - build_chat_llm(streaming=True) → ChatOpenAI with .with_fallbacks()

   - Primary: DeepSeek-V3 via SiliconFlow

   - Fallback 1: Qwen2.5-72B via SiliconFlow (same key, different model)

   - Fallback 2: GPT-4o-mini via OpenAI

 - build_router_llm() → Qwen2.5-7B (fast, cheap, no streaming, temp=0)

 - All use langchain-openai ChatOpenAI (SiliconFlow/OpenAI both OpenAI-compatible)



 Step 5: System Prompts (app/services/ai/prompts.py)



 - SYSTEM_PROMPT_BASE: 20-year HK property management consultant, strict context

 grounding, citation rules, HK Traditional Chinese

 - 3 intent suffixes:

   - INTENT_LEGAL_DEFINITION: blockquote original text + plain language

   - INTENT_SOP_PROCEDURE: numbered step list with responsible parties

   - INTENT_DISPUTE: neutral analysis + case citations + legal disclaimer

 - ROUTER_PROMPT: classify into legal_definition / sop_procedure / dispute

 - Placeholders: {context}, {chat_history}



 Step 6: Semantic Router (app/services/ai/router.py)



 - Intent enum: LEGAL_DEFINITION, SOP_PROCEDURE, DISPUTE

 - SemanticRouter.classify(query) → Intent

 - LCEL: ROUTER_PROMPT | router_llm | StrOutputParser()

 - Default to LEGAL_DEFINITION on parse error



 Step 7: Hybrid Retriever (app/services/ai/retriever.py)



 - RetrievedChunk dataclass: child_id, parent_id, parent_content, child_search_text,

 vector_score, keyword_score, combined_score, doc_type, metadata

 - HybridRetriever.retrieve(query, db, top_k, score_threshold)

 - Single SQL query with CTEs:

   a. vector_results: cosine similarity via cc.embedding <=> :query_vector, fetch 3x

 top_k

   b. keyword_results: ts_rank(pd.search_vector, plainto_tsquery('simple', :query))

   c. JOIN + weighted combination (0.7 vector + 0.3 keyword)

 - Anti-hallucination gate: if top score < threshold (0.35), return empty list →

 short-circuit

 - Reuse existing EmbeddingService.embed_single() for query embedding



 Step 8: Conversation Memory (app/services/ai/memory.py)



 - ConversationMemory.get_or_create_conversation(user_id, conv_id, platform, db) →

 Conversation

 - save_user_message(conv_id, content, db) → Message

 - save_assistant_message(conv_id, content, citations, db) → Message

 - get_history(conv_id, db) → last 5 turns (10 messages)

 - format_history_for_prompt(messages) → "User: ...\nAssistant: ..." text

 - Uses existing Conversation + Message models (no migration needed)



 Step 9: Telemetry Logger (app/services/ai/telemetry.py)



 - TelemetryLogger.log_query(user_id, original_query, masked_query, pii_found,

 retrieved_chunks, intent, token_usage, latency_ms, llm_model, db)

 - Writes to existing AuditLog table with action="rag_query"

 - Detail JSONB stores: masked_query, pii_types, chunk IDs+scores, intent, latency

 - PDPO: original_query stored ONLY if no PII detected



 Step 10: RAG Chain Orchestrator (app/services/ai/rag_chain.py)



 - RAGChain.astream(query, user, conv_id, db) → AsyncIterator[str] (SSE events)

 - Pipeline flow:

   a. PII mask user query

   b. Intent classification + retrieval (concurrent via asyncio.create_task)

   c. Anti-hallucination gate (empty chunks → graceful degradation with suggestions)

   d. Build prompt: base system + intent suffix + context + history

   e. Stream LLM response token-by-token

   f. After stream: extract citations, legal disclaimer, follow-up suggestions

   g. Save messages to DB, log telemetry

 - SSE event types: conversation_id, intent, content (multiple), citations (JSON),

 disclaimer, follow_ups (JSON), done

 - Static follow-up suggestions per intent (avoids extra LLM call)

 - Graceful degradation: "未能找到相關內容" + 3 alternative suggestions



 Step 11: Pydantic Schemas (app/schemas/chat.py)



 - ChatRequest(message: str, conversation_id: UUID | None, platform: str = "web")

 - CitationItem(parent_id, doc_type, title, excerpt, score)

 - ChatResponse (for non-streaming fallback)



 Step 12: Chat API Endpoint (app/api/v1/chat.py)



 - POST /api/v1/chat → StreamingResponse (SSE)

 - Dependencies: get_current_user, get_db

 - Flow: check_quota → increment_usage → RAGChain.astream()

 - Headers: Cache-Control: no-cache, Connection: keep-alive, X-Accel-Buffering: no

 - Session lifecycle: create session inside generator with async_session_factory() to

 keep alive throughout stream



 Step 13: Register chat router (app/main.py)



 - app.include_router(chat_router, prefix="/api/v1")



 Step 14: i18n updates (app/core/i18n/zh_hk.json, en.json)



 - Add chat.no_context, chat.disclaimer_legal, chat.pii_detected, chat.stream_error,

 chat.conversation_not_found



 Step 15: app/services/ai/__init__.py



 - Re-export key classes: RAGChain, PIIMaskingService, HybridRetriever



 ---

 Key Design Decisions



 1. No new migrations needed — existing conversations, messages, audit_logs tables

 support all Phase 4 data

 2. langchain-openai only — SiliconFlow, Groq, OpenAI all expose OpenAI-compatible

 API, no need for langchain-groq

 3. SSE streaming with typed events solves "citations after generation" — client

 renders tokens as they arrive, receives metadata at end

 4. Concurrent router + retrieval — intent classification and hybrid search run in

 parallel for speed

 5. Session management for streaming — use async_session_factory() inside generator

 instead of get_db dependency (session must outlive endpoint return)

 6. Static follow-up suggestions per intent — avoids extra LLM call, can upgrade to

 dynamic later



 ---

 Verification Plan



 1. Docker rebuild: docker compose up -d --build api

 2. Register user: POST /api/v1/auth/register

 3. Login: POST /api/v1/auth/login → get token

 4. Test PII masking: Send message with HKID/phone → check audit log shows masked

 version

 5. Test RAG chat: curl -N -H "Authorization: Bearer <token>" -H "Content-Type:

 application/json" -d '{"message": "業主可以點樣召開業主大會？"}'

 http://localhost:8000/api/v1/chat

 6. Verify streaming: Tokens arrive incrementally, then Citations/disclaimer/follow_ups at end

 7. Test anti-hallucination: Ask unrelated question → should get "未能找到相關內容"

 without LLM call

 8. Test conversation memory: Send follow-up question with same conversation_id → should reference previous context

 9. Test quota: Exhaust free tier (10 calls) → get 429 error

 10. Check observability: Query audit_logs table for rag_query entries with full telemetry