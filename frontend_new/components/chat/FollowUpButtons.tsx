"use client";

import { MessageCircle } from "lucide-react";

interface FollowUpButtonsProps {
  suggestions: string[];
  onSelect:    (text: string) => void;
  disabled?:   boolean;
}

export function FollowUpButtons({ suggestions, onSelect, disabled }: FollowUpButtonsProps) {
  if (suggestions.length === 0) return null;

  return (
    <div className="mt-3 flex flex-col gap-2">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 flex items-center gap-1.5">
        <MessageCircle className="w-3 h-3" />
        延伸問題
      </p>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((text, i) => (
          <button
            key={i}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(text)}
            className="text-xs border border-zinc-200 rounded-lg px-3 py-1.5
                       text-zinc-600 bg-white text-left leading-snug
                       hover:border-zinc-400 hover:text-zinc-900 hover:bg-zinc-50
                       disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors"
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
