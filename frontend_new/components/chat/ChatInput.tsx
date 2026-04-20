"use client";

import { useRef, useEffect, useCallback, type KeyboardEvent, type ChangeEvent } from "react";
import { ArrowUp, Square } from "lucide-react";

interface ChatInputProps {
  value:        string;
  onChange:     (v: string) => void;
  onSubmit:     () => void;
  onStop:       () => void;
  isStreaming:  boolean;
  disabled?:    boolean;
  placeholder?: string;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isStreaming,
  disabled,
  placeholder = "輸入您的物管法律問題…",
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 192)}px`;
  }, []);

  useEffect(() => { resize(); }, [value, resize]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && value.trim()) onSubmit();
    }
  };

  const canSend = !isStreaming && value.trim().length > 0 && !disabled;

  return (
    <div className="flex items-end gap-2 border border-zinc-200 rounded-2xl
                    bg-white px-4 py-3 shadow-sm
                    focus-within:border-zinc-400 transition-colors">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        disabled={disabled && !isStreaming}
        placeholder={placeholder}
        className="flex-1 resize-none bg-transparent text-sm text-zinc-900
                   placeholder:text-zinc-400 outline-none leading-relaxed
                   min-h-[24px] max-h-[192px] overflow-y-auto"
      />

      {isStreaming ? (
        <button
          type="button"
          onClick={onStop}
          className="shrink-0 w-8 h-8 flex items-center justify-center
                     rounded-xl bg-zinc-900 text-white
                     hover:bg-zinc-700 transition-colors"
          aria-label="停止生成"
        >
          <Square className="w-3.5 h-3.5 fill-white" />
        </button>
      ) : (
        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSend}
          className="shrink-0 w-8 h-8 flex items-center justify-center
                     rounded-xl bg-zinc-900 text-white
                     hover:bg-zinc-700 transition-colors
                     disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="發送"
        >
          <ArrowUp className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
