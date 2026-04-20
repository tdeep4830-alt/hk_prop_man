"use client";

import { useEffect, useRef } from "react";
import type { Message } from "@/stores/chatStore";
import { ChatBubble } from "./ChatBubble";
import { MessageSquare } from "lucide-react";

const STARTER_PROMPTS = [
  "業主立案法團有何法律地位？",
  "管理費追討的法律程序？",
  "大廈公契與管理公司的責任界定",
  "召開業主大會的法定要求是甚麼？",
];

interface ChatMessagesProps {
  messages:         Message[];
  onFollowUpSelect: (text: string) => void;
  streamingActive:  boolean;
}

export function ChatMessages({ messages, onFollowUpSelect, streamingActive }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-6 text-center">
        <div className="w-12 h-12 rounded-2xl bg-zinc-100 flex items-center justify-center mb-4">
          <MessageSquare className="w-5 h-5 text-zinc-400" />
        </div>
        <h2 className="font-semibold text-zinc-900 text-lg mb-1">
          有甚麼物業管理法律問題？
        </h2>
        <p className="text-zinc-400 text-sm mb-8 max-w-sm leading-relaxed">
          AI 將引用《建築物管理條例》Cap.&nbsp;344 及真實判例即時為您作答。
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-md">
          {STARTER_PROMPTS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => onFollowUpSelect(p)}
              className="border border-zinc-200 rounded-xl px-4 py-3 text-sm
                         text-zinc-600 bg-white text-left leading-snug
                         hover:border-zinc-400 hover:text-zinc-900 hover:bg-zinc-50
                         transition-colors"
            >
              {p}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-2xl mx-auto flex flex-col gap-6">
        {messages.map((msg, i) => {
          const isLast = i === messages.length - 1;
          return (
            <ChatBubble
              key={msg.id}
              message={msg}
              onFollowUpSelect={onFollowUpSelect}
              isLastMessage={isLast && msg.role === "assistant"}
              streamingActive={streamingActive}
            />
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
