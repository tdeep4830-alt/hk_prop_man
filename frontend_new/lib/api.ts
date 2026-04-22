/**
 * API client — all calls use relative URLs (/api/v1/…).
 * Next.js rewrites them to the FastAPI backend at build/runtime.
 *
 * Token is read directly from localStorage (not Zustand) to avoid
 * circular dependency with authStore.
 */

import type { LoginRequest, RegisterRequest, TokenResponse, UserResponse } from "@/types/api";

const BASE = "/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("propman_token");
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ─── Auth endpoints ────────────────────────────────────────────────────────

export const authApi = {
  login: (body: LoginRequest): Promise<TokenResponse> =>
    fetch(`${BASE}/auth/login`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    }).then((r) => {
      if (!r.ok) return r.json().then((e) => Promise.reject(e));
      return r.json();
    }),

  register: (body: RegisterRequest): Promise<UserResponse> =>
    fetch(`${BASE}/auth/register`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    }).then((r) => {
      if (!r.ok) return r.json().then((e) => Promise.reject(e));
      return r.json();
    }),

  me: (): Promise<UserResponse> =>
    fetch(`${BASE}/auth/me`, {
      headers: authHeaders(),
    }).then((r) => {
      if (!r.ok) return r.json().then((e) => Promise.reject(e));
      return r.json();
    }),
};

// ─── Admin endpoints ───────────────────────────────────────────────────────

export interface ChunkDetail {
  child_id:       string | null;
  parent_id:      string | null;
  combined_score: number;
  doc_type:       string;
}

export interface QueryLogEntry {
  id:             string;
  user_id:        string | null;
  user_email:     string | null;
  created_at:     string;
  masked_query:   string | null;
  original_query: string | null;
  pii_types:      string[];
  intent:         string | null;
  complexity:     string | null;
  category:       string | null;
  latency_ms:     number | null;
  llm_model:      string | null;
  chunks:         ChunkDetail[];
  chunk_count:    number;
}

export interface QueryLogPage {
  total:   number;
  page:    number;
  limit:   number;
  entries: QueryLogEntry[];
}

export const adminApi = {
  getQueryLogs: (page = 1, limit = 20, intent?: string): Promise<QueryLogPage> => {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (intent) params.set("intent", intent);
    return fetch(`${BASE}/admin/query-logs?${params}`, {
      headers: authHeaders(),
    }).then((r) => {
      if (!r.ok) return r.json().then((e) => Promise.reject(e));
      return r.json();
    });
  },
};

// ─── Chat history endpoints ────────────────────────────────────────────────

export interface ConversationSummary {
  id:         string;
  title:      string;
  created_at: string;
}

export interface MessageOut {
  id:         string;
  role:       "user" | "assistant";
  content:    string;
  citations:  unknown[] | null;
  created_at: string;
}

export const chatApi = {
  getConversations: (): Promise<ConversationSummary[]> =>
    fetch(`${BASE}/chat/conversations`, {
      headers: authHeaders(),
    }).then((r) => {
      if (!r.ok) return r.json().then((e) => Promise.reject(e));
      return r.json();
    }),

  getMessages: (convId: string): Promise<MessageOut[]> =>
    fetch(`${BASE}/chat/conversations/${convId}/messages`, {
      headers: authHeaders(),
    }).then((r) => {
      if (!r.ok) return r.json().then((e) => Promise.reject(e));
      return r.json();
    }),
};

// ─── Chat SSE stream ────────────────────────────────────────────────────────

/**
 * Open an SSE stream for a chat message.
 * Returns the raw Response so the caller can read the body as a stream.
 */
export function chatStream(
  message:        string,
  conversationId?: string,
  signal?:        AbortSignal,
): Promise<Response> {
  return fetch(`${BASE}/chat`, {
    method:  "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body:   JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });
}
