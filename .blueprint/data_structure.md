1. 數據架構總覽 (Architecture Overview)
本系統採用 PostgreSQL (搭配 pgvector) 作為核心數據庫，處理結構化數據與向量檢索；並使用 Redis 作為緩存層，處理對話 Session 與頻率限制 (Rate Limiting)。

2. 核心數據表設計 (Core Schema)
A. 用戶與權限模組 (User & Identity)
支持 Web 與 Telegram 雙端綁定及會員等級控制。
users	
id	UUID (PK)	用戶唯一識別碼
email	String (U)	登入郵箱
hashed_password	String	BCrypt 加密密碼
membership_tier	Enum	free, pro, enterprise
pref_lang	String	用戶偏好語言 (zh_hk, en)

user_identities	
user_id	UUID (FK)	關聯至 users.id
provider	String	登入平台 (email, telegram)
provider_uid	String	平台唯一 ID (如 Telegram chat_id)

知識庫：Parent-Child Indexing (RAG)
這是解決法律條文「斷章取義」的核心結構。我們將文檔分為「大塊背景 (Parent)」與「小塊索引 (Child)」。
parent_docs	
id	UUID (PK)	父區塊 ID (大段原文，約 1000-1500 tokens)
property_id	UUID	所屬大廈/屋苑 ID (用於多租戶隔離)
content	Text	完整法律條文、公契 (DMC) 或通告內容
doc_type	Enum	statute, dmc, circular, internal
metadata	JSONB	包含：章節 (Cap)、頁碼、原始文件連結
child_chunks
idUUID (PK)子區塊 ID (小段文字，約 200-300 tokens)
parent_idUUID (FK)關聯之父區塊 ID (檢索後提取 Parent 內容)
embeddingVector($d$)向量數據 ($d$ 維度依模型而定，如 1024 或 1536)
languageString內容語言標籤 (zh_hk, en)
search_text Text供全文搜尋 (Keyword Search) 使用的純文本



3. 安全審計與運維 (Security & Observability)
usage_quotas 表: 記錄用戶每日 LLM 調用次數，實施會員制配額限制。

audit_logs 表: 記錄敏感操作及 PII (個人隱私) 遮蔽攔截紀錄，確保數據合規（如符合 PCPD 要求）。

4. 關鍵運作邏輯 (Key Logic)
多語言檢索:
系統同時在 child_chunks 中進行搜尋。若用戶以中文詢問，Embedding 模型會匹配語義相近的 zh_hk 或 en 子區塊。

Parent-Child 還原:
向量數據庫回傳相似度最高的 child_chunks 後，系統根據 parent_id 從 parent_docs 提取大段上下文給 LLM。這保證了 AI 看到的法規細節是完整的，而非破碎的句子。

多租戶隔離 (Multi-tenancy):
所有 RAG 查詢必須帶有 property_id 過濾條件，確保 A 大廈的業主無法檢索到 B 大廈的內部財務通告。

5. 性能優化建議 (Performance Tips)
Index: 在 child_chunks.embedding 上建立 HNSW 索引以加速向量檢索。

Hybrid Search: 同時使用 embedding (語義) 和 search_text (關鍵字) 進行檢索，提高對「第 344 章」等精確詞彙的匹配度。

Partitioning: 如果文檔量達到萬級以上，可按 doc_type 或 property_id 進行物理分區。