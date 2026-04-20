"use client";

import { PlusIcon, MessageSquare, LogOut, ChevronLeft } from "lucide-react";
import type { Conversation } from "@/stores/chatStore";
import type { UserResponse } from "@/types/api";

interface SidebarProps {
  conversations: Conversation[];
  activeConvId:  string | null;
  user:          UserResponse | null;
  isOpen:        boolean;
  onNewChat:     () => void;
  onSelectConv:  (id: string) => void;
  onClose:       () => void;
  onLogout:      () => void;
}

export function Sidebar({
  conversations,
  activeConvId,
  user,
  isOpen,
  onNewChat,
  onSelectConv,
  onClose,
  onLogout,
}: SidebarProps) {
  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/40 md:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}

      <aside
        className={`fixed md:relative inset-y-0 left-0 z-30
                    flex flex-col w-64 bg-zinc-950 text-zinc-100
                    transition-transform duration-200
                    ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
      >
        <div className="flex items-center justify-between px-4 py-4 border-b border-zinc-800">
          <span className="text-sm font-bold tracking-tight">PropMan AI</span>
          <button
            type="button"
            onClick={onClose}
            className="md:hidden text-zinc-500 hover:text-zinc-200 transition-colors"
            aria-label="關閉側欄"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        </div>

        <div className="px-3 py-3">
          <button
            type="button"
            onClick={onNewChat}
            className="w-full flex items-center gap-2 px-3 py-2.5
                       rounded-xl border border-zinc-700 text-sm text-zinc-300
                       hover:bg-zinc-800 hover:text-white transition-colors"
          >
            <PlusIcon className="w-4 h-4 shrink-0" />
            新對話
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pb-2 space-y-0.5">
          {conversations.length === 0 && (
            <p className="text-xs text-zinc-600 px-2 py-3">尚無對話記錄</p>
          )}
          {conversations.map((conv) => {
            const isActive = conv.id === activeConvId;
            return (
              <button
                key={conv.id}
                type="button"
                onClick={() => onSelectConv(conv.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left
                             text-sm transition-colors truncate
                             ${isActive
                               ? "bg-zinc-800 text-white"
                               : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"}`}
              >
                <MessageSquare className="w-3.5 h-3.5 shrink-0 text-zinc-500" />
                <span className="truncate">{conv.title}</span>
              </button>
            );
          })}
        </nav>

        <div className="border-t border-zinc-800 px-3 py-3">
          <div className="flex items-center gap-2.5 px-2 py-1.5">
            <div className="w-7 h-7 rounded-full bg-zinc-700 flex items-center justify-center
                            text-xs font-semibold text-zinc-300 shrink-0">
              {(user?.email?.[0] ?? "U").toUpperCase()}
            </div>
            <span className="text-xs text-zinc-400 truncate flex-1">
              {user?.email ?? ""}
            </span>
            <button
              type="button"
              onClick={onLogout}
              className="shrink-0 text-zinc-600 hover:text-zinc-200 transition-colors"
              aria-label="登出"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
