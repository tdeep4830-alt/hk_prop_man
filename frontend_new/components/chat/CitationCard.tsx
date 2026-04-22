"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, FileText, Scale, BookOpen, Search } from "lucide-react";
import type { CitationItem } from "@/types/api";

const DOC_TYPE_LABELS: Record<string, string> = {
  statute:     "法規",
  case_law:    "判例",
  court_case:  "法庭案例",
  guideline:   "指引",
  contract:    "公契",
};

const DOC_TYPE_ICONS: Record<string, React.ElementType> = {
  statute:     Scale,
  case_law:    Search,
  court_case:  Scale,
  guideline:   BookOpen,
  contract:    FileText,
};

function scoreColor(score: number): string {
  if (score >= 0.8) return "text-emerald-600 bg-emerald-50";
  if (score >= 0.6) return "text-amber-600 bg-amber-50";
  return "text-zinc-500 bg-zinc-100";
}

interface CitationCardProps {
  citation: CitationItem;
  index:    number;
}

export function CitationCard({ citation, index }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);

  const Icon       = DOC_TYPE_ICONS[citation.doc_type] ?? FileText;
  const typeLabel  = DOC_TYPE_LABELS[citation.doc_type] ?? citation.doc_type;
  const score      = Math.round(citation.score * 100);
  const hasExcerpt = !!citation.excerpt?.trim();

  return (
    <div className="border border-zinc-200 rounded-xl overflow-hidden bg-white text-sm">

      <button
        type="button"
        onClick={() => hasExcerpt && setExpanded((v) => !v)}
        className="w-full flex items-start gap-3 px-4 py-3 text-left
                   hover:bg-zinc-50 transition-colors group"
        aria-expanded={expanded}
      >
        <span className="shrink-0 flex items-center justify-center
                          w-6 h-6 rounded-md bg-zinc-100 text-zinc-500 text-xs font-medium mt-0.5">
          {index + 1}
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold
                             uppercase tracking-wider text-zinc-400">
              <Icon className="w-3 h-3" />
              {typeLabel}
            </span>
            <span className={`ml-auto text-[10px] font-semibold px-1.5 py-0.5
                               rounded-full shrink-0 ${scoreColor(citation.score)}`}>
              {score}%
            </span>
          </div>
          <p className="text-zinc-800 font-medium leading-snug line-clamp-2">
            {citation.title || "未命名文件"}
          </p>
        </div>

        {hasExcerpt && (
          <span className="shrink-0 mt-1 text-zinc-400 group-hover:text-zinc-600 transition-colors">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </span>
        )}
      </button>

      {expanded && hasExcerpt && (
        <div className="border-t border-zinc-100 px-4 py-3 bg-zinc-50">
          <p className="text-zinc-500 text-xs leading-relaxed line-clamp-[8]">
            {citation.excerpt!.slice(0, 400)}
            {citation.excerpt!.length > 400 && "…"}
          </p>
        </div>
      )}
    </div>
  );
}
