HK-PropTech AI Assistant - Development Protocol
1. Project Identity & Objective
Project Name: HK-PropTech AI Assistant

Objective: 一個針對香港物業管理（第 344 章《建築物管理條例》、公契 DMC、建築物條例）的專業 RAG 系統。

Target UI: Web (React/Next.js) 與 Telegram Bot。


Key Value: 透過 Parent-Child Indexing 與 語義分段 解決法律條文「斷章取義」的問題，確保 AI 具備法例的前文後理 (Full Context) 。
+4

2. Technical Stack & Environment

Backend: Python 3.10+ / FastAPI (Asynchronous) 。
+1


Orchestration: LangChain (核心框架) / LangGraph (用於處理複雜的糾錯與多步檢索邏輯) 。

LLM Providers: * Primary: DeepSeek-V3/R1 (經由 SiliconFlow)。

Failover: Qwen 2.5 (經由 Groq) 或 Gemini 2.0 (經由 Google Vertex AI)。

Database: PostgreSQL + pgvector (存儲 Vector Embeddings)。

Cache: Redis (用於速率限制、Telegram Session 及檢索快取)。

Infrastructure: Docker Compose, Nginx, DigitalOcean Droplet。

3. Data Schema & RAG Strategy
Parent-Child Indexing Structure

Parent Chunks: 完整的法律條文（如整個 Section 14 ）。存儲於 parent_docs 表。


Child Chunks: 細分的款項（如 Section 14(1) ），帶有 Vector Embeddings。

Retrieval Logic: 1.  使用 Child Vector 進行語義搜索。
2.  根據命中 Child 的 parent_id 提取整個 Parent 內容 。
3.  將 Parent 全文與標題 (Title) 傳遞給 LLM。
+3

Database Tables (pgvector)
parent_docs: 存儲 ID, Content, Metadata (Ordinance, Part, Subpart, Title)。

child_chunks: 存儲 ID, Parent_ID, Embedding, Enriched_Content。

conversations: 支援串流輸出 (Streaming) 與引用來源標註 (Citations)。

4. Development Rules (Strict Adherence)
A. Coding Style

Async First: 所有數據庫查詢、LLM 請求、I/O 操作必須使用 async/await 。
+1

LangChain Expression Language (LCEL): 優先使用 LCEL 構建檢索鏈。

Type Hinting: 強制使用 Pydantic V2 模型與 Python 類型標註。

B. Security & Privacy (HK Compliance)
PII Masking: 在傳送到外部 API 之前，必須進行香港身份證 (HKID)、電話、室號的去隱私化處理。

Rate Limiting: 基於 Redis 的每用戶限流。

Audit Log: 紀錄所有法律查詢的檢索結果，以便進行 Observability 分析。

C. AI Prompts & Output
Language: 預設使用 繁體中文 (香港)。


Citations: 答案必須附帶精確引用（例如：「根據《條例》第 14 條 (1) 款...」）。

Confidence Score: 如果檢索到的內容相似度過低，AI 必須誠實回答「找不到相關法例」。

5. Directory Structure
Plaintext
/app
  ├── api/v1/           # API 路由 (FastAPI)
  ├── core/             # 安全、配置、i18n、自定義異常
  ├── db/               # pgvector 連接、Migrations (Alembic)
  ├── services/         
  │     ├── ai/         # LangChain 邏輯 (Chains, Retrievers, Graphs)
  │     │     ├── parsers/  # Regex Parser (法例) & LLM Structurer (指引)
  │     │     └── prompts/  # 專業物管語境 Prompts
  │     ├── security/   # PII 過濾、JWT
  │     └── telegram/   # Bot 處理器
  └── main.py           # 進入點
6. Implementation Roadmap
Phase 1: Docker 基礎建設 (PGVector + Redis) 與 FastAPI 框架。

Phase 2: 雙軌 Ingestion Pipeline：


法例: Regex Parser (Parent-Child) 。


指引: Markdown 轉換 + DeepSeek 語意分段 。

Phase 3: LangChain ParentDocumentRetriever 整合。

Phase 4: LangGraph 錯誤補償機制 (如果搜尋不到，自動放寬檢索條件)。

Phase 5: Telegram Bot 整合與 Web UI (Streaming 支援)。

Phase 6: Observability: 整合 LangSmith 追蹤檢索準確度與 Token 消耗。

7. Instructions for AI Coder (System Prompt)
"當為此項目編寫代碼時，請確保所有數據庫操作均使用 AsyncSession。針對 LLM 的交互，請實施重試邏輯，當一個供應商 (SiliconFlow) 失敗時，自動切換至備份供應商 (Groq)。所有法律解析必須保留 Metadata 中的 part 與 subpart 標籤 。請優先使用 Traditional Chinese (Hong Kong) 回覆。"
+3