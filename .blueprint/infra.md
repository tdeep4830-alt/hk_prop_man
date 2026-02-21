1. 項目概覽 (Project Overview)
本項目開發一個專為香港物業管理設計的 AI 系統，利用 RAG (Retrieval-Augmented Generation) 技術，處理《建築物管理條例》(Cap. 344)、大廈公契 (DMC) 及各類物管公文。系統需支援 中英雙語，並透過 API 接入 Web 及 Telegram。

2. 技術棧 (Technical Stack)
Backend	Python 3.10+ / FastAPI
AI Framework	LangChain / LangGraph 處理 RAG 檢索、Agent 邏輯。
LLM APIs	DeepSeek-V3/R1, Qwen 2.5 經由 SiliconFlow / Groq 接入以獲取極速回應。
Vector DB	PostgreSQL + PGVector	同時處理結構化用戶數據與非結構化向量數據。
Cache/Queue	Redis	用於 Rate Limiting, Session 管理及 Telegram 異步任務。
Infrastructure	Docker / DigitalOcean	輕量化容器部署，平衡成本與擴展性。

3. 核心功能架構 (Core Features)
A. 雙語支援 (Multilingual Support)
檢索層： 使用多語言 Embedding 模型（如 BGE-M3），支援「中文提問，英文檢索」。

應用層： FastAPI Middleware 根據 Accept-Language 或用戶設定自動切換 UI 語言。

翻譯層： LLM 根據上下文自動判斷輸出語言，並確保香港特有術語（如「業主立案法團」）翻譯準確。

B. 會員與權限 (Auth & Membership)
JWT 認證： 整合 FastAPI OAuth2PasswordBearer。

等級劃分：

Free: 每日查詢限制，使用基礎模型。

Pro: 無限制查詢，使用 R1 強推理模型，支援個人文件上傳。

跨平台綁定： Web 帳號與 Telegram user_id 1-on-1 綁定。

4. 安全性與隱私 (Security & Privacy)
A. 數據保護
PII Masking： 傳送數據至外部 API 前，自動遮蔽香港身份證、電話、單位號碼（支援中英文識別）。

數據隔離： 向量資料庫使用 tenant_id 進行 Row-Level Security，確保用戶文件互不干擾。

B. 基礎設施安全
傳輸加密： 全站強制 HTTPS (Nginx + Let's Encrypt)。

WAF 防護： Cloudflare 接入，防止 DDoS 及注入攻擊。

Secret 管理： 所有 API Key 儲存於 .env 或 GitHub Secrets，嚴禁寫死在代碼。

5. 自動化與觀測性 (CI/CD & Observability)
A. CI/CD Pipeline (GitHub Actions)
Test: 執行 pytest 測試 Auth 及 RAG 檢索邏輯。

Eval: 使用 RAGAS 測試 AI 回答的準確度。

Build: 自動構建 Docker Image。

Deploy: 透過 SSH 部署至 DigitalOcean，執行 docker-compose up -d。

B. 監控系統
LangSmith: 追蹤 LLM 每一步推理，監控 Token 消耗。

Structured Logging: JSON 格式日誌，紀錄關鍵異常與安全事件。

6. 目錄結構 (Directory Structure)
Plaintext
/
├── app/
│   ├── api/ v1/         # Endpoint 邏輯 (chat, auth, users)
│   ├── core/
│   │   ├── i18n/        # 雙語資源 (zh_hk.json, en.json)
│   │   ├── security.py  # JWT, PII Masking, Hashing
│   │   └── config.py    # 環境變量加載
│   ├── services/
│   │   ├── rag_engine.py  # 向量檢索與重排 (Re-ranking)
│   │   └── llm_router.py  # 自動切換 DeepSeek/Qwen/Groq
│   ├── models/          # DB Schemas
│   └── main.py          # FastAPI 入口
├── infra/
│   ├── nginx/           # SSL & Proxy 設定
│   └── docker-compose.yml
├── .github/workflows/   # CI/CD 腳本
└── .env.example
7. 開發指令 (Instructions for AI)
Async First: 所有網絡 I/O 必須使用 async/await。

Strict Typing: 強制執行 Python Type Hints。

HK Context: LLM Prompt 必須包含「以香港物業管理專業語氣回答」的要求。
