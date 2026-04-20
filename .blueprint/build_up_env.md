PropManAI 環境搭建指南
前置條件
工具	版本要求	檢查指令
Docker Desktop	≥ 24	docker --version
Docker Compose	≥ 2.20	docker compose version
Python	3.10+	python3 --version
Node.js	≥ 18	node --version
Step 1 — 配置環境變數
.env 已存在，但需要填入真實 API Key：


# 打開 .env 填入以下必填項目
SILICONFLOW_API_KEY=sk-xxxx          # 必填 — 主 LLM + Router
OPENAI_API_KEY=sk-xxxx               # 選填 — LLM 最終 fallback
JWT_SECRET=your_random_secret_here   # 必填 — 改掉預設值
.env 裡嘅 SILICONFLOW_BASE_URL 現在係 https://api.siliconflow.com/v1，記得確認係正確嘅 endpoint。

Step 2 — 啟動後端基礎設施（Docker）

# 喺項目根目錄執行
docker compose up -d db redis phoenix
等待 DB 健康檢查通過（約 10 秒）：


docker compose ps   # db 應顯示 healthy
Step 3 — 執行資料庫 Migration

# 方法 A：直接用本地 Python（推薦開發用）
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 改 DATABASE_URL 指向本地（非 Docker 內部）
export DATABASE_URL=postgresql+asyncpg://propman:propman_secret@localhost:5432/propman_ai
alembic upgrade head
或者方法 B（用 Docker）：


docker compose run --rm api alembic upgrade head
Step 4 — 資料攝入（RAG 文件建索引）

# 本地執行
export DATABASE_URL=postgresql+asyncpg://propman:propman_secret@localhost:5432/propman_ai
python scripts/run_ingestion.py
rag_data/ 已有三類文件：legislation/、guideline/、Count_case/。

此步驟時間較長（需要 embed 所有文件），視乎文件數量可能需要數分鐘。

Step 5 — 啟動 API Server
方法 A：全 Docker 模式


docker compose up -d
方法 B：本地開發模式（熱重載更快）


source .venv/bin/activate
export DATABASE_URL=postgresql+asyncpg://propman:propman_secret@localhost:5432/propman_ai
export REDIS_URL=redis://localhost:6379/0
export PHOENIX_ENDPOINT=http://localhost:6006/v1/traces
uvicorn app.main:app --reload --port 8000
Step 6 — 啟動前端

cd frontend_new
npm install
npm run dev        # http://localhost:3000
Step 7 — 啟動可觀測性工具（選填）

docker compose up -d prometheus grafana
服務	URL	帳密
Phoenix（LLM Tracing）	http://localhost:6006	—
Prometheus	http://localhost:9090	—
Grafana	http://localhost:3001	admin / admin
完整啟動順序（一鍵版）

# 1. 起基礎設施
docker compose up -d db redis phoenix

# 2. 等 DB 就緒後 migrate
sleep 10
docker compose run --rm api alembic upgrade head

# 3. 起其餘服務
docker compose up -d

# 4. 起前端（另一個 terminal）
cd frontend_new && npm install && npm run dev
驗證環境是否正常

# API 健康
curl http://localhost:8000/health

# API 文檔
open http://localhost:8000/docs

# 前端
open http://localhost:3000