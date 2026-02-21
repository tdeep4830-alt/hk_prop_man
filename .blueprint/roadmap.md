香港物管 AI 總開發流程 (Roadmap)
第一階段：基礎設施與環境搭建 (The Foundation)
目標：建立穩定的開發環境與容器化架構。

環境初始化： 撰寫 docker-compose.yml，啟動 PostgreSQL (PGVector) 及 Redis。

項目結構： 按照之前建議的目錄結構建立資料夾。

基礎配置： 設置 .env（API Keys, DB 連接）及 core/config.py。

數據遷移： 使用 Alembic 初始化數據庫表（User, Parent-Child Docs）。

第二階段：核心身份驗證與多語言框架 (The Core)
目標：實現用戶管理與基礎 API 安全。

JWT Auth： 實作註冊、登入及 Token 驗證邏輯。

i18n Middleware： 實作語言檢測，確保系統能根據 Header 切換中英文錯誤訊息。

會員邏輯： 定義 membership_tier 的限制邏輯（如：Free 用戶每日只能問 10 題）。

第三階段：RAG 引擎與 Parent-Child 索引 (The Intelligence)
目標：這是 App 的大腦，處理物管文件的攝取與檢索。

文件攝取流 (Ingestion Pipeline)： * 使用 PyMuPDF 解析香港法例 PDF 或 DMC。

實作 Parent-Child Splitter：大塊存內容，小塊存向量。

向量存儲： 將 Embedding 寫入 PGVector，並建立 HNSW 索引。

檢索邏輯： 實作 Retriever，確保能根據 Child ID 找回 Parent 內容。

Hybrid Search： 整合語義搜尋與關鍵字搜尋（針對特定法例條號）。

第四階段：LLM 調度與 PII 過濾 (The Reasoning)
目標：與 LLM Provider 對接並確保數據安全。

LLM Factory： 接入 SiliconFlow (DeepSeek) 與 Groq，並實作自動 Failover 機制。

Prompt Engineering： 撰寫專為香港物管設計的 System Prompts（包含引用要求）。

PII Masking： 實作隱私過濾，確保身份證號碼等敏感字眼在送往 LLM 前被處理。

第五階段：多平台 UI 接入 (The Interface)
目標：讓用戶能透過不同渠道使用。

Web API： 完善 /chat 接口，支援串流輸出 (Streaming)。

Telegram Bot： 使用 Webhook 模式開發 Telegram 服務，共用後端 RAG 邏輯。

Citations： 在前端顯示引用來源（如：參考《建築物管理條例》第18條）。

第六階段：測試、觀測與部署 (The Quality)
目標：確保系統穩定並持續優化。

自動化測試： 撰寫 PyTest 測試 Auth 與 API；使用 RAGAS 測試回答準確率。

Observability： 接入 LangSmith 監控 LLM 運行過程。

CI/CD： 配置 GitHub Actions，自動運行測試並部署至 DigitalOcean。

SSL/CDN： 配置 Nginx 及 Cloudflare 加固安全。