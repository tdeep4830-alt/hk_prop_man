"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore, selectIsAuthenticated, selectIsHydrated } from "@/stores/authStore";
import { adminApi, type QueryLogEntry } from "@/lib/api";
import {
  ChevronDown,
  ChevronRight,
  Clock,
  Database,
  User,
  Layers,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";

// ─── Badge helpers ─────────────────────────────────────────────────────────

const INTENT_COLOR: Record<string, string> = {
  legal_definition: "bg-blue-100 text-blue-700",
  procedure:        "bg-purple-100 text-purple-700",
  dispute:          "bg-red-100 text-red-700",
};

const COMPLEXITY_COLOR: Record<string, string> = {
  simple: "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  hard:   "bg-red-100 text-red-700",
};

function Badge({ label, colorClass }: { label: string; colorClass: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${colorClass}`}>
      {label}
    </span>
  );
}

// ─── Score bar ─────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.7 ? "bg-green-500" : score >= 0.4 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] tabular-nums text-zinc-500 w-7 text-right">{pct}%</span>
    </div>
  );
}

// ─── Chunk detail panel ────────────────────────────────────────────────────

function ChunkPanel({ entry }: { entry: QueryLogEntry }) {
  if (entry.chunk_count === 0) {
    return (
      <p className="text-xs text-zinc-400 italic mt-2">
        No chunks retrieved (SIMPLE path or no context found)
      </p>
    );
  }
  return (
    <div className="mt-3 space-y-2">
      {entry.chunks.map((c, i) => (
        <div key={i} className="flex items-start gap-3 bg-zinc-50 rounded-lg px-3 py-2 border border-zinc-100">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-mono text-zinc-400 truncate max-w-[200px]">
                {c.parent_id ?? "—"}
              </span>
              <Badge
                label={c.doc_type || "unknown"}
                colorClass="bg-zinc-100 text-zinc-600"
              />
            </div>
          </div>
          <ScoreBar score={c.combined_score} />
        </div>
      ))}
    </div>
  );
}

// ─── Log row ───────────────────────────────────────────────────────────────

function LogRow({ entry }: { entry: QueryLogEntry }) {
  const [open, setOpen] = useState(false);

  const ts = new Date(entry.created_at).toLocaleString("zh-HK", {
    month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });

  return (
    <div className="border border-zinc-200 rounded-xl overflow-hidden">
      {/* Header row */}
      <button
        className="w-full text-left px-4 py-3 bg-white hover:bg-zinc-50 transition-colors flex items-start gap-3"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="mt-0.5 text-zinc-400 shrink-0">
          {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        </span>

        <div className="flex-1 min-w-0 space-y-1.5">
          {/* Query text */}
          <p className="text-sm text-zinc-800 font-medium leading-snug line-clamp-2">
            {entry.masked_query ?? entry.original_query ?? "—"}
          </p>

          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-400">
            <span className="flex items-center gap-1">
              <Clock size={11} /> {ts}
            </span>
            {entry.user_email && (
              <span className="flex items-center gap-1">
                <User size={11} /> {entry.user_email}
              </span>
            )}
            {entry.latency_ms != null && (
              <span className="flex items-center gap-1">
                <Database size={11} /> {entry.latency_ms} ms
              </span>
            )}
            {entry.chunk_count > 0 && (
              <span className="flex items-center gap-1">
                <Layers size={11} /> {entry.chunk_count} chunks
              </span>
            )}
            {entry.pii_types.length > 0 && (
              <span className="flex items-center gap-1 text-amber-500">
                <AlertTriangle size={11} /> PII: {entry.pii_types.join(", ")}
              </span>
            )}
          </div>

          {/* Badges */}
          <div className="flex flex-wrap gap-1.5">
            {entry.intent && (
              <Badge
                label={entry.intent}
                colorClass={INTENT_COLOR[entry.intent] ?? "bg-zinc-100 text-zinc-600"}
              />
            )}
            {entry.complexity && (
              <Badge
                label={entry.complexity}
                colorClass={COMPLEXITY_COLOR[entry.complexity] ?? "bg-zinc-100 text-zinc-600"}
              />
            )}
            {entry.category && (
              <Badge label={entry.category} colorClass="bg-indigo-50 text-indigo-600" />
            )}
            {entry.llm_model && (
              <Badge label={entry.llm_model} colorClass="bg-zinc-100 text-zinc-500" />
            )}
          </div>
        </div>
      </button>

      {/* Expanded chunk detail */}
      {open && (
        <div className="border-t border-zinc-100 bg-zinc-50/60 px-4 py-3">
          {entry.original_query && entry.original_query !== entry.masked_query && (
            <div className="mb-3 text-xs text-amber-600 bg-amber-50 rounded px-3 py-2 border border-amber-100">
              <span className="font-semibold">Original (PII present):</span>{" "}
              {entry.original_query}
            </div>
          )}
          <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-400 mb-1">
            Retrieved Chunks
          </p>
          <ChunkPanel entry={entry} />
        </div>
      )}
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────

const INTENT_OPTIONS = ["", "legal_definition", "procedure", "dispute"];

export default function AdminPage() {
  const router        = useRouter();
  const isHydrated    = useAuthStore(selectIsHydrated);
  const isAuth        = useAuthStore(selectIsAuthenticated);
  const user          = useAuthStore((s) => s.user);

  const [entries,   setEntries]   = useState<QueryLogEntry[]>([]);
  const [total,     setTotal]     = useState(0);
  const [page,      setPage]      = useState(1);
  const [intent,    setIntent]    = useState("");
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState<string | null>(null);

  const LIMIT = 20;

  // Auth guard — enterprise only
  useEffect(() => {
    if (!isHydrated) return;
    if (!isAuth) { router.replace("/login"); return; }
    if (user?.membership_tier !== "enterprise") {
      router.replace("/chat");
    }
  }, [isHydrated, isAuth, user, router]);

  const load = useCallback(async (p: number, intentFilter: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.getQueryLogs(p, LIMIT, intentFilter || undefined);
      setEntries(data.entries);
      setTotal(data.total);
    } catch {
      setError("Failed to load logs. Make sure you have enterprise access.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isHydrated && isAuth && user?.membership_tier === "enterprise") {
      load(page, intent);
    }
  }, [isHydrated, isAuth, user, page, intent, load]);

  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  if (!isHydrated) return null;

  return (
    <div className="min-h-screen bg-zinc-50">
      {/* Top bar */}
      <div className="bg-white border-b border-zinc-200 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-zinc-900">RAG Query Log</h1>
          <p className="text-xs text-zinc-400 mt-0.5">Admin · {total} total entries</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Intent filter */}
          <select
            value={intent}
            onChange={(e) => { setIntent(e.target.value); setPage(1); }}
            className="text-xs border border-zinc-200 rounded-lg px-3 py-1.5 bg-white text-zinc-700 focus:outline-none focus:ring-2 focus:ring-zinc-300"
          >
            {INTENT_OPTIONS.map((o) => (
              <option key={o} value={o}>{o || "All intents"}</option>
            ))}
          </select>

          {/* Refresh */}
          <button
            onClick={() => load(page, intent)}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs text-zinc-600 border border-zinc-200 rounded-lg px-3 py-1.5 bg-white hover:bg-zinc-50 disabled:opacity-40"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>

          {/* Back to chat */}
          <button
            onClick={() => router.push("/chat")}
            className="text-xs text-zinc-500 hover:text-zinc-800 border border-zinc-200 rounded-lg px-3 py-1.5 bg-white"
          >
            ← Back to Chat
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-3">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
            {error}
          </div>
        )}

        {loading && entries.length === 0 && (
          <div className="text-center py-16 text-zinc-400 text-sm">Loading...</div>
        )}

        {!loading && entries.length === 0 && !error && (
          <div className="text-center py-16 text-zinc-400 text-sm">
            No query logs found. Ask a question in the chat to generate logs.
          </div>
        )}

        {entries.map((entry) => (
          <LogRow key={entry.id} entry={entry} />
        ))}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 pt-4">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="text-xs px-4 py-1.5 rounded-lg border border-zinc-200 bg-white disabled:opacity-40 hover:bg-zinc-50"
            >
              Previous
            </button>
            <span className="text-xs text-zinc-500">
              Page {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="text-xs px-4 py-1.5 rounded-lg border border-zinc-200 bg-white disabled:opacity-40 hover:bg-zinc-50"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
