"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter }                         from "next/navigation";
import { Menu }                              from "lucide-react";

import { useAuthStore, selectIsAuthenticated, selectIsHydrated } from "@/stores/authStore";
import { useChatStore }   from "@/stores/chatStore";
import { useChatStream }  from "@/hooks/useChatStream";
import { chatApi }        from "@/lib/api";

import { Sidebar }      from "@/components/chat/Sidebar";
import { ChatMessages } from "@/components/chat/ChatMessages";
import { ChatInput }    from "@/components/chat/ChatInput";

export default function ChatPage() {
  const router = useRouter();

  // ── Auth ─────────────────────────────────────────────────────────────────
  const isHydrated      = useAuthStore(selectIsHydrated);
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  const user            = useAuthStore((s) => s.user);
  const logout          = useAuthStore((s) => s.logout);

  useEffect(() => {
    if (isHydrated && !isAuthenticated) router.replace("/login");
  }, [isHydrated, isAuthenticated, router]);

  // ── Chat store ────────────────────────────────────────────────────────────
  const {
    conversations,
    activeConvId,
    activeConversation,
    newConversation,
    selectConversation,
    setBackendConvId,
    addMessage,
    appendToken,
    patchLastMessage,
    historyLoaded,
    hydrateConversations,
    hydrateMessages,
  } = useChatStore();

  // Load conversation list from backend once after auth hydration
  useEffect(() => {
    if (!isHydrated || !isAuthenticated || historyLoaded) return;
    chatApi.getConversations()
      .then((convs) => {
        if (convs.length > 0) {
          hydrateConversations(convs);
        } else {
          newConversation();
        }
      })
      .catch(() => newConversation());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isHydrated, isAuthenticated]);

  // Lazy-load messages when switching to a conversation with no messages
  useEffect(() => {
    if (!activeConvId) return;
    const conv = useChatStore.getState().conversations.find((c) => c.id === activeConvId);
    if (!conv?.backendConvId || conv.messages.length > 0) return;
    chatApi.getMessages(conv.backendConvId)
      .then((msgs) => hydrateMessages(conv.backendConvId!, msgs))
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConvId]);

  const activeConv = activeConversation();

  // ── Stream ────────────────────────────────────────────────────────────────
  const { sendMessage, isStreaming, abort } = useChatStream();

  // ── Local UI state ────────────────────────────────────────────────────────
  const [inputValue,   setInputValue]   = useState("");
  const [sidebarOpen,  setSidebarOpen]  = useState(false);

  // ── Send ──────────────────────────────────────────────────────────────────
  const handleSend = useCallback(
    async (text?: string) => {
      const userText = (text ?? inputValue).trim();
      if (!userText || isStreaming) return;

      let convId = activeConvId;
      if (!convId) convId = newConversation();

      setInputValue("");

      addMessage(convId, {
        id:          crypto.randomUUID(),
        role:        "user",
        content:     userText,
        isStreaming: false,
        timestamp:   Date.now(),
      });

      addMessage(convId, {
        id:          crypto.randomUUID(),
        role:        "assistant",
        content:     "",
        isStreaming: true,
        timestamp:   Date.now(),
      });

      const backendConvId = useChatStore
        .getState()
        .conversations.find((c) => c.id === convId)?.backendConvId;

      await sendMessage(userText, backendConvId, {
        onConversationId: (id)       => setBackendConvId(convId!, id),
        onToken:          (token)    => appendToken(convId!, token),
        onCitations:      (citations) => patchLastMessage(convId!, { citations }),
        onDisclaimer:     (disclaimer) => patchLastMessage(convId!, { disclaimer }),
        onFollowUps:      (followUps)  => patchLastMessage(convId!, { followUps }),
        onDone:           ()          => patchLastMessage(convId!, { isStreaming: false }),
        onError: (msg) => patchLastMessage(convId!, {
          content: msg === "__quota_exceeded__"
            ? "🙏 感謝您使用 PropManAI Beta！\n\n您今日的免費查詢次數已用盡。此為 Beta 測試版本，每位用戶每日可免費查詢 10 次。\n\n正式版本即將推出，屆時將提供無限次查詢及更多功能，敬請期待！"
            : `⚠️ 出現錯誤：${msg}`,
          isStreaming: false,
        }),
      });
    },
    [inputValue, isStreaming, activeConvId, newConversation, addMessage,
     sendMessage, setBackendConvId, appendToken, patchLastMessage],
  );

  const handleNewChat    = () => { newConversation(); setSidebarOpen(false); };
  const handleSelectConv = (id: string) => { selectConversation(id); setSidebarOpen(false); };
  const handleLogout    = () => { abort(); logout(); router.push("/login"); };

  // ── Hydration guard ───────────────────────────────────────────────────────
  if (!isHydrated) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-50">
        <div className="w-5 h-5 rounded-full border-2 border-zinc-300 border-t-zinc-900 animate-spin" />
      </div>
    );
  }
  if (!isAuthenticated) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <div className="w-5 h-5 rounded-full border-2 border-zinc-300 border-t-zinc-900 animate-spin" />
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen overflow-hidden bg-white">

      <Sidebar
        conversations={conversations}
        activeConvId={activeConvId}
        user={user}
        isOpen={sidebarOpen}
        onNewChat={handleNewChat}
        onSelectConv={handleSelectConv}
        onClose={() => setSidebarOpen(false)}
        onLogout={handleLogout}
      />

      <div className="flex flex-col flex-1 min-w-0">

        <header className="flex items-center gap-3 px-4 py-3 border-b border-zinc-100 md:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="text-zinc-500 hover:text-zinc-900 transition-colors"
            aria-label="開啟側欄"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="text-sm font-semibold text-zinc-900 truncate">
            {activeConv?.title ?? "新對話"}
          </span>
        </header>

        <ChatMessages
          messages={activeConv?.messages ?? []}
          onFollowUpSelect={(text) => handleSend(text)}
          streamingActive={isStreaming}
        />

        <div className="border-t border-zinc-100 px-4 py-4 bg-white">
          <div className="max-w-2xl mx-auto">
            <ChatInput
              value={inputValue}
              onChange={setInputValue}
              onSubmit={() => handleSend()}
              onStop={abort}
              isStreaming={isStreaming}
            />
            <p className="text-center text-[10px] text-zinc-400 mt-2">
              AI 回答僅供參考，不構成法律意見。如需法律建議，請諮詢執業律師。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
