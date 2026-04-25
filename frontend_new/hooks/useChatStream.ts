"use client";

import { useCallback, useRef, useState } from "react";
import { chatStream } from "@/lib/api";
import type { CitationItem } from "@/types/api";

// ─── Public types ─────────────────────────────────────────────────────────────

export interface StreamCallbacks {
  onConversationId?: (id: string) => void;
  onToken:           (token: string) => void;
  onCitations:       (citations: CitationItem[]) => void;
  onFollowUps:       (followUps: string[]) => void;
  onDisclaimer:      (text: string) => void;
  onDone:            () => void;
  onError:           (message: string) => void;
}

// ─── SSE block parser ─────────────────────────────────────────────────────────

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = "";
  const dataLines: string[] = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event: "))     event = line.slice(7).trim();
    else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
    else if (line.startsWith("data:"))  dataLines.push(line.slice(5));
  }

  if (!event && dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError]            = useState<string | null>(null);
  const abortRef                     = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (
      userMessage:    string,
      conversationId: string | undefined,
      callbacks:      StreamCallbacks,
    ) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      setIsStreaming(true);
      setError(null);

      try {
        const response = await chatStream(
          userMessage,
          conversationId,
          abortRef.current.signal,
        );

        if (!response.ok) {
          if (response.status === 429) {
            callbacks.onError("__quota_exceeded__");
            setIsStreaming(false);
            return;
          }
          const body = await response.json().catch(() => ({}));
          throw new Error(
            typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`,
          );
        }

        if (!response.body) throw new Error("Empty response body");

        const reader  = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let   buffer  = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() ?? "";

          for (const block of blocks) {
            const parsed = parseSseBlock(block);
            if (!parsed) continue;
            const { event, data } = parsed;

            switch (event) {
              case "conversation_id": {
                const p = JSON.parse(data) as { conversation_id: string };
                callbacks.onConversationId?.(p.conversation_id);
                break;
              }
              case "intent": break; // reserved
              case "content":
                if (data) callbacks.onToken(data);
                break;
              case "citations": {
                const p = JSON.parse(data) as { citations: CitationItem[] };
                callbacks.onCitations(p.citations);
                break;
              }
              case "disclaimer":
                if (data) callbacks.onDisclaimer(data);
                break;
              case "follow_ups": {
                const p = JSON.parse(data) as { follow_ups: string[] };
                callbacks.onFollowUps(p.follow_ups);
                break;
              }
              case "done":
                callbacks.onDone();
                setIsStreaming(false);
                return;
              case "error":
                callbacks.onError(data || "未知錯誤，請稍後再試。");
                setIsStreaming(false);
                return;
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        const msg = (err as Error).message ?? "連線失敗，請稍後再試。";
        setError(msg);
        callbacks.onError(msg);
      } finally {
        setIsStreaming(false);
      }
    },
    [],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return { sendMessage, isStreaming, error, abort };
}
