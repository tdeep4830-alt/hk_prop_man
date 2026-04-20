一、 技術選型 (Tech Stack Recommendation)
要做到流暢嘅打字機效果同埋企業級嘅介面，我強烈建議使用以下黃金組合：

核心框架： Next.js (React) — 目前開發 AI Web App 嘅絕對首選，支援前後端分離，SEO 友好。

UI 組件庫： Tailwind CSS + shadcn/ui — 唔使自己由零寫 CSS，直接 Copy & Paste 高質素嘅對話框、按鈕、彈出視窗，外觀媲美 ChatGPT。

狀態管理： Zustand — 輕量級，用嚟記住用戶登入狀態同埋 Sidebar 嘅對話歷史。

Markdown 渲染： react-markdown — 因為 LLM 吐出嚟嘅會有 **粗體** 或者 > 引用，需要將佢轉靚做 HTML。

二、 核心 UI 規劃 (Core UI Layout)
成個 Web App 主要分為三大板塊：

1. 登入與註冊頁面 (Auth Pages)
簡潔嘅表單，收集業主 Email / 密碼。

登入後，將 FastAPI 傳過嚟嘅 JWT Token 存入前端（準備升級做 HttpOnly Cookie 增強安全性）。

2. 左側導覽列 (Sidebar - History & Settings)
New Chat 按鈕： 隨時開啟新話題。

歷史紀錄清單： 顯示最近的對話（例如：「外牆維修權責」、「成立法團步驟」），點擊可載入舊對話。

用戶資訊卡： 顯示當前登入者名稱及登出按鈕。

3. 主對話區 (Main Chat Area - 靈魂所在)
對話氣泡 (Chat Bubbles)： 右邊係業主嘅提問，左邊係 AI 嘅回覆。

串流打字機效果 (Streaming Effect)： 實時接收 SSE 數據，字體逐個顯示。

來源引用卡片 (Citation Cards)： 當 AI 答完，氣泡底部會出現類似 [Cap. 344 第 16 條] 或 [案例: LDBM 34/2002] 嘅小按鈕，Hover 或點擊可以睇到原文節錄。

追問按鈕 (Follow-up Suggestions)： AI 俾完答案後，底部自動出現 2-3 個建議按鈕（例如：「咁需要幾多業主同意？」），一撳即問。

三、 最具挑戰嘅技術點：SSE 串流對接 (The SSE Challenge)前端開發 AI 系統，最難搞嘅就係對接 Server-Sent Events (SSE)。傳統嘅 API 係 fetch 完等幾秒，一次過攞晒成個 JSON。但你 Phase 4 寫嘅 API 係「流式傳輸」，前端需要一邊收 Data 一邊 Update 畫面。我哋需要喺前端寫一個特製嘅 fetch 邏輯，去讀取 ReadableStream。佢要識得分辨傳過嚟嘅 Event 係咩類型：收到 content 事件 $\rightarrow$ 將字串加落畫面上嘅對話氣泡。收到 citations 事件 $\rightarrow$ 將 JSON 解析成引用卡片顯示喺底部。收到 done 事件 $\rightarrow$ 停止 Loading 動畫，顯示追問按鈕。

四、 實作路線圖 (Implementation Order)
為咗唔好一開波就亂，我哋分三步走：

Step 1: 基礎框架與 Auth (打好地基)

初始化 Next.js 專案。

建立 Login / Register 頁面，成功攞到 JWT 並存入 LocalStorage 或 Cookie。

Step 2: 靜態對話介面 (切圖與排版)

砌好 Sidebar、Chat Bubble、Input Box 嘅 UI（先用假 Data 測試排版）。

搞掂 react-markdown 渲染。

Step 3: 串流引擎與 API 對接 (注入靈魂)

寫最核心嘅 useChatStream Custom Hook。

真正對接你後端嘅 /api/v1/chat，處理 SSE 數據流。

加入 Citation 卡片同 Follow-up 按鈕

