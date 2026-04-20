import Link from "next/link";
import { ArrowRight } from "lucide-react";

export function Hero() {
  return (
    <section className="flex flex-col">

      {/* ── Sticky Nav ─────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-zinc-100">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">

          <div className="flex items-center gap-2.5">
            <span className="text-sm font-bold tracking-tight text-zinc-900">
              PropMan AI
            </span>
            <span className="hidden sm:inline-flex items-center text-[10px] font-semibold
                             bg-zinc-100 text-zinc-500 px-2 py-0.5 rounded-full
                             uppercase tracking-widest">
              Beta
            </span>
          </div>

          <div className="flex items-center gap-6 text-sm">
            <Link
              href="#features"
              className="hidden sm:inline text-zinc-500 hover:text-zinc-900 transition-colors"
            >
              功能介紹
            </Link>
            <Link
              href="/login"
              className="text-zinc-500 hover:text-zinc-900 transition-colors"
            >
              登入
            </Link>
            <Link
              href="/register"
              className="bg-zinc-900 text-white px-4 py-1.5 rounded-lg text-sm font-medium
                         hover:bg-zinc-700 active:bg-zinc-800 transition-colors"
            >
              免費試用
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero Content ───────────────────────────────────────────── */}
      <div className="flex flex-col items-center justify-center min-h-[88vh]
                      px-6 py-20 text-center">
        <div className="max-w-3xl mx-auto">

          <div className="mb-8 inline-flex items-center gap-2.5
                          border border-zinc-200 bg-zinc-50
                          px-4 py-1.5 rounded-full text-xs text-zinc-500">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse shrink-0" />
            基於真實香港法律文獻 · 土地審裁處判例 · 持續更新
          </div>

          <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold tracking-tight
                         text-zinc-900 leading-[1.05] mb-6">
            您的全天候
            <br />
            <span className="text-zinc-400">香港物業管理</span>
            <br />
            AI 法律顧問
          </h1>

          <p className="text-lg sm:text-xl text-zinc-500 leading-relaxed
                        max-w-xl mx-auto mb-10">
            業主立案法團、大廈公契、管理費追討、維修責任爭議……
            <br className="hidden sm:block" />
            一切香港物業管理法律問題，由 AI 即時引用{" "}
            <span className="text-zinc-700 font-semibold">Cap.&nbsp;344</span>{" "}
            及真實判例作答。
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6">
            <Link
              href="/chat"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2
                         bg-zinc-900 text-white px-8 py-3.5 rounded-xl font-medium text-base
                         hover:bg-zinc-700 active:bg-zinc-800 transition-colors shadow-sm"
            >
              立即開始對話
              <ArrowRight className="w-4 h-4" />
            </Link>

            <Link
              href="#features"
              className="w-full sm:w-auto inline-flex items-center justify-center
                         border border-zinc-200 text-zinc-600 px-8 py-3.5 rounded-xl
                         font-medium text-base hover:border-zinc-400 hover:text-zinc-900
                         transition-colors"
            >
              了解更多功能
            </Link>
          </div>

          <p className="text-xs text-zinc-400">
            免費試用 · 無需信用卡 · 支援繁體中文及英文
          </p>
        </div>
      </div>

      <div className="border-t border-zinc-100" />
    </section>
  );
}
