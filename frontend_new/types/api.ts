/**
 * Shared TypeScript types mirroring the FastAPI backend schemas.
 */

// ─── Auth ──────────────────────────────────────────────────────────────────

export interface LoginRequest {
  email:    string;
  password: string;
}

export interface RegisterRequest {
  email:    string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type:   string;
}

export interface UserResponse {
  id:              string;
  email:           string;
  membership_tier: "free" | "pro" | "enterprise";
  created_at:      string;
}

// ─── Chat ──────────────────────────────────────────────────────────────────

export interface ChatRequest {
  message:          string;
  conversation_id?: string;
}

export interface CitationItem {
  doc_type: string;   // "statute" | "case_law" | "guideline" | "contract"
  title:    string;
  excerpt?: string;
  score:    number;   // 0–1 combined retrieval score
}

// ─── SSE event payloads ────────────────────────────────────────────────────

export type SSEEventType =
  | "conversation_id"
  | "intent"
  | "content"
  | "citations"
  | "disclaimer"
  | "follow_ups"
  | "done"
  | "error";

export interface ConversationIdPayload { conversation_id: string; }
export interface IntentPayload          { intent: string; }
export interface CitationsPayload       { citations: CitationItem[]; }
export interface FollowUpsPayload       { follow_ups: string[]; }
