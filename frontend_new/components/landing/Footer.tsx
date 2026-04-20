export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-zinc-100 bg-white">
      <div className="max-w-5xl mx-auto px-6 py-14">

        <div className="flex flex-col md:flex-row items-start justify-between gap-10 mb-10">
          <div className="shrink-0">
            <p className="font-bold text-zinc-900 text-sm mb-1.5">PropMan AI</p>
            <p className="text-xs text-zinc-400 leading-relaxed">
              香港物業管理
              <br />
              AI 法律顧問系統
            </p>
          </div>

          <div className="max-w-lg">
            <p className="text-xs font-semibold text-zinc-500 mb-2 uppercase tracking-wide">
              法律免責聲明
            </p>
            <p className="text-xs text-zinc-400 leading-relaxed">
              本系統所提供之所有資訊及分析僅供一般參考用途，並不構成法律意見，
              亦不應視為業主與律師之間的委託關係。如閣下需就特定法律事宜獲取意見，
              請諮詢具備香港執業資格的律師。本系統之內容以現行香港法律為基礎，
              如相關法律有所更改，本系統之資訊未必即時反映有關修訂，恕不另行通知。
            </p>
          </div>
        </div>

        <div className="border-t border-zinc-100 pt-6
                        flex flex-col sm:flex-row items-center justify-between
                        gap-3 text-xs text-zinc-400">
          <span>© {year} PropMan AI. All rights reserved.</span>
          <span className="hidden sm:inline text-zinc-200">|</span>
          <span>Powered by RAG · Built for Hong Kong Property Owners</span>
        </div>
      </div>
    </footer>
  );
}
