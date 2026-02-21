/root
├── app/
│   ├── main.py                 # FastAPI 入口，初始化 Middleware & Router
│   ├── api/                    # 路由層 (Controllers)
│   │   ├── v1/
│   │   │   ├── auth.py         # 登入、註冊、Token 發放
│   │   │   ├── chat.py         # RAG 對話接口 (Web 用)
│   │   │   ├── documents.py    # 文件上傳與處理 (Admin/Pro)
│   │   │   └── members.py      # 會員資料與訂閱管理
│   ├── core/                   # 核心配置與安全性
│   │   ├── config.py           # 環境變量 (Pydantic Settings)
│   │   ├── security.py         # JWT 簽名、密碼 Hash
│   │   ├── middleware/         # i18n 多語言切換、Rate Limiting
│   │   └── exceptions.py       # 定義全局錯誤處理
│   ├── db/                     # 數據庫連接與 Session 管理
│   │   ├── base.py             # SQLAlchemy Base
│   │   └── session.py          # Async Session 產生器
│   ├── models/                 # 數據庫實體 (SQLAlchemy Models)
│   │   ├── user.py
│   │   ├── document.py         # Parent-Child 結構在此定義
│   │   └── chat.py
│   ├── schemas/                # 數據驗證 (Pydantic Models)
│   │   ├── user.py
│   │   ├── chat.py
│   │   └── token.py
│   ├── services/               # 業務邏輯層 (Business Logic)
│   │   ├── ai/                 # LangChain 核心
│   │   │   ├── rag_chain.py    # Parent-Child 檢索邏輯
│   │   │   ├── llm_factory.py  # 選擇 DeepSeek / Qwen / Groq
│   │   │   └── prompts.py      # 儲存中英文 Prompt Templates
│   │   ├── auth_service.py     # 會員邏輯
│   │   ├── telegram_bot.py     # Telegram Bot 異步處理邏輯
│   │   └── pii_masking.py      # 隱私過濾器
│   └── utils/                  # 工具類 (Logger, PDF Parser)
├── tests/                      # 自動化測試
│   ├── conftest.py
│   ├── test_api/               # API 單元測試
│   └── test_rag/               # RAGAS 準確度測試
├── infra/                      # 基礎設施配置
│   ├── docker/
│   │   ├── app.Dockerfile
│   │   └── nginx.conf
│   └── docker-compose.yml
├── .env                        # 敏感密鑰 (不進入 Git)
├── .env.example
├── alembic/                    # 數據庫遷移腳本 (Migration)
└── requirements.txt
核心模組說明
1. services/ai/ (AI 核心)
不要將 LangChain 邏輯直接寫在 API Endpoint 裡。

rag_chain.py: 負責處理 Parent-Child Indexing。它會調用向量數據庫尋找 Child，然後返回 Parent 內容給 LLM。

llm_factory.py: 實現 Fallback 機制。如果 SiliconFlow 報錯，自動切換到 Groq 或官方 API。

2. core/middleware/ (攔截器)
i18n: 檢測 Header 中的語言設定，並將當前語言存入 contextvars，方便全域調用翻譯。

Rate Limiting: 根據 user_id 在 Redis 紀錄請求頻率，防止 API 費用爆炸。

3. services/telegram_bot.py
與 Web API 共用同一套 rag_chain。

建議使用 Webhook 模式而非 Polling，這樣你可以統一在 FastAPI 裡處理 Telegram 的請求。

4. utils/pii_masking.py (安全性)
在調用外部 LLM API 之前，透過正則表達式或輕量化 NLP 模型檢查 content，將「陳大文」替換為 [NAME]，確保符合香港私隱條例。