/**
 * chatStore — in-memory conversation history (not persisted).
 *
 * The backend holds the canonical history; this store only drives the UI.
 */

import { create } from "zustand";
import type { CitationItem } from "@/types/api";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Message {
  id:          string;
  role:        "user" | "assistant";
  content:     string;
  citations?:  CitationItem[];
  followUps?:  string[];
  disclaimer?: string;
  isStreaming: boolean;
  timestamp:   number;
}

export interface Conversation {
  id:             string;  // frontend UUID
  backendConvId?: string;  // backend UUID from SSE conversation_id event
  title:          string;
  messages:       Message[];
  createdAt:      number;
}

// ─── State ────────────────────────────────────────────────────────────────────

interface ChatState {
  conversations: Conversation[];
  activeConvId:  string | null;

  activeConversation: () => Conversation | null;
  newConversation:    () => string;
  selectConversation: (id: string) => void;
  setBackendConvId:   (localId: string, backendId: string) => void;
  addMessage:         (localConvId: string, msg: Message) => void;
  appendToken:        (localConvId: string, token: string) => void;
  patchLastMessage:   (localConvId: string, patch: Partial<Message>) => void;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function updateLastAssistant(
  messages: Message[],
  patch: (m: Message) => Message,
): Message[] {
  const msgs = [...messages];
  const idx  = msgs.length - 1;
  if (idx < 0 || msgs[idx].role !== "assistant") return messages;
  msgs[idx] = patch(msgs[idx]);
  return msgs;
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useChatStore = create<ChatState>()((set, get) => ({
  conversations: [],
  activeConvId:  null,

  activeConversation: () => {
    const { conversations, activeConvId } = get();
    return conversations.find((c) => c.id === activeConvId) ?? null;
  },

  newConversation: () => {
    const id = crypto.randomUUID();
    set((s) => ({
      activeConvId:  id,
      conversations: [
        { id, title: "新對話", messages: [], createdAt: Date.now() },
        ...s.conversations,
      ],
    }));
    return id;
  },

  selectConversation: (id) => set({ activeConvId: id }),

  setBackendConvId: (localId, backendId) =>
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === localId ? { ...c, backendConvId: backendId } : c,
      ),
    })),

  addMessage: (localConvId, msg) =>
    set((s) => ({
      conversations: s.conversations.map((c) => {
        if (c.id !== localConvId) return c;
        const title =
          c.messages.length === 0 && msg.role === "user"
            ? msg.content.slice(0, 28) + (msg.content.length > 28 ? "…" : "")
            : c.title;
        return { ...c, title, messages: [...c.messages, msg] };
      }),
    })),

  appendToken: (localConvId, token) =>
    set((s) => ({
      conversations: s.conversations.map((c) => {
        if (c.id !== localConvId) return c;
        return {
          ...c,
          messages: updateLastAssistant(c.messages, (m) => ({
            ...m,
            content: m.content + token,
          })),
        };
      }),
    })),

  patchLastMessage: (localConvId, patch) =>
    set((s) => ({
      conversations: s.conversations.map((c) => {
        if (c.id !== localConvId) return c;
        return {
          ...c,
          messages: updateLastAssistant(c.messages, (m) => ({ ...m, ...patch })),
        };
      }),
    })),
}));
