"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm     from "remark-gfm";
import type { Message } from "@/stores/chatStore";
import { CitationCard }    from "./CitationCard";
import { FollowUpButtons } from "./FollowUpButtons";

/**
 * Parse data rows from raw afterSep text using pipe-counting with peek-ahead.
 *
 * LLMs output tables as a single line. Rows are separated by either:
 *   Case 1 (no trailing |): col4content | **NextRow** → 5th pipe = leading | of next row
 *   Case 2 (trailing | then ||): col4content || **NextRow** → trailing | then leading |
 *
 * We count numCols pipes per row, then peek at the next char to disambiguate.
 */
function parseTableRows(text: string, numCols: number): string[] {
  const rows: string[] = [];
  let row = "";
  let pipes = 0;
  let started = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];

    if (!started) {
      if (ch === "|") { started = true; row = "|"; pipes = 1; }
      continue; // skip whitespace/newlines between rows
    }

    if (ch === "|") {
      pipes++;
      if (pipes > numCols) {
        const next = i + 1 < text.length ? text[i + 1] : "";
        if (next === "|" || next === "\n") {
          // Case 2: this | is the trailing | of current row (|| boundary)
          row += "|";
          rows.push(row.trimEnd());
          row = ""; pipes = 0; started = false;
        } else {
          // Case 1: this | is the leading | of the NEXT row (no trailing |)
          rows.push(row.trimEnd() + " |");
          row = "|"; pipes = 1;
        }
        continue;
      }
    }

    row += ch === "\n" ? " " : ch; // flatten in-cell newlines to space
  }

  if (started && row.trim()) {
    rows.push(row.trimEnd().endsWith("|") ? row.trimEnd() : row.trimEnd() + " |");
  }
  return rows;
}

/**
 * Reconstruct a GFM table that the LLM emitted as a single long line.
 * Finds the separator row (|---|---|), counts columns, splits header and data rows.
 */
function reconstructTable(text: string): string {
  const sepRe = /\|([ \t]*:?-{2,}:?[ \t]*\|)+/;
  const m = text.match(sepRe);
  if (!m) return text;

  const sep = m[0];
  const numCols = (sep.match(/-+/g) || []).length;
  if (numCols < 2) return text;

  const sepIdx = text.indexOf(sep);
  const beforeSep = text.slice(0, sepIdx);
  const afterSep  = text.slice(sepIdx + sep.length);

  // BUG FIX 1: the entire text is one line — no \n exists before the separator.
  // Find the FIRST | in beforeSep — everything before it is preamble text,
  // everything from the first | onward is the header row.
  const firstPipe = beforeSep.indexOf("|");
  const preamble  = firstPipe > 0 ? beforeSep.slice(0, firstPipe).trimEnd() : "";
  let header      = (firstPipe >= 0 ? beforeSep.slice(firstPipe) : beforeSep).trim();

  if (!header.startsWith("|")) header = "| " + header;
  if (!header.endsWith("|"))   header = header + " |";

  const fixedSep = sep.trimEnd().endsWith("|") ? sep.trimEnd() : sep.trimEnd() + "|";

  const allRows = parseTableRows(afterSep, numCols);

  // BUG FIX 2: the last "row" may be post-table prose that has fewer pipes than numCols.
  // Split into valid table rows vs trailing prose.
  const validRows: string[] = [];
  let postTable = "";
  for (let i = 0; i < allRows.length; i++) {
    const row = allRows[i];
    const pipeCount = (row.match(/\|/g) || []).length;
    if (pipeCount >= numCols) {
      validRows.push(row);
    } else {
      // Strip leading/trailing | and collect as plain text
      postTable = [row, ...allRows.slice(i + 1)]
        .map(r => r.replace(/^\s*\|/, "").replace(/\|\s*$/, "").trim())
        .filter(Boolean)
        .join(" ");
      break;
    }
  }

  const table = [header, fixedSep, ...validRows].join("\n");
  return (preamble ? preamble + "\n\n" : "") +
         table +
         (postTable ? "\n\n" + postTable : "");
}

/**
 * Normalize LLM markdown output that lacks proper newlines.
 * - Reconstructs single-line tables using pipe counting
 * - Applies heading/list fixes only to non-table segments
 */
function normalizeMarkdown(text: string, debug = false): string {
  if (!text) return "";
  if (debug) console.log("[RAW LLM OUTPUT]\n" + text);

  // Step 1: global cleanups
  text = text.replace(/<br\s*\/?>/gi, " ");
  text = text.replace(/\u00a0/g, " ");

  // Step 1b: strip bare --- separators (render as unwanted <hr>)
  text = text.replace(/(?:^|\n)[ \t]*---[ \t]*(?=\n|$)/g, "");

  // Step 1c: fix unbalanced ** — e.g. "免責聲明**" missing opening **
  // Matches a word boundary followed by text** that has no opening **
  text = text.replace(/(^|\n)([ \t]*)([^*\n][^\n]*)\*\*[ \t]*(\n|$)/g, (_, pre, indent, inner, post) => {
    // Only fix if inner doesn't already contain an opening **
    if (inner.includes("**")) return _ ;
    return `${pre}${indent}**${inner}**${post}`;
  });

  // Step 2: reconstruct table rows (single-line LLM table → proper multiline GFM)
  text = reconstructTable(text);

  // Step 3: insert blank lines at table ↔ non-table boundaries
  const lines = text.split("\n");
  const out: string[] = [];
  for (const line of lines) {
    const isTable   = line.trimStart().startsWith("|");
    const prev      = out.length ? out[out.length - 1] : "";
    const prevTable = prev.trimStart().startsWith("|");
    const prevBlank = prev.trim() === "";
    if ( isTable && !prevTable && !prevBlank) out.push("");
    if (!isTable &&  prevTable && line.trim() !== "") out.push("");
    out.push(line);
  }
  text = out.join("\n");

  // Step 4: heading/list fixes — applied only to non-table segments
  const segs = text.split(/((?:^|\n)[ \t]*\|[^\n]*(?:\n[ \t]*\|[^\n]*)*)/m);
  text = segs.map((seg, i) => {
    if (i % 2 === 1) return seg; // table block — leave untouched
    return seg
      .replace(/([^\n])(#{1,6} )/g, "$1\n\n$2")       // blank line before headings
      // blank line before Chinese numbered bold headings (**一、 **二、 …) if not already blank
      .replace(/([^\n])(\n)([ \t]*\*\*[一二三四五六七八九十]+、)/g, "$1\n\n$3")
      .replace(/([^\n*])((?<!\*)\* )/g, "$1\n$2")      // newline before * list items (not **)
      .replace(/([^\n])(- (?=[^\s-]))/g, "$1\n$2")     // newline before - list items
      .replace(/([^\n])(> )/g, "$1\n\n$2")             // blank line before blockquotes
      // blank line after citation [來源: ...] when followed by more content on same line
      .replace(/(\[來源:[^\]]+\])[ \t]+(?=\S)/g, "$1\n\n")
      // blank line before standalone bold sub-headings: **關鍵因素一：** or ***題目***
      .replace(/([^\n])(\n[ \t]*\*{2,3}[^*\n]+\*{2,3}[ \t]*\n)/g, "$1\n\n$2");
  }).join("");

  // Step 5: ensure content lines separated by single \n become paragraphs (\n\n)
  // ReactMarkdown treats single \n as a space — any non-empty line following
  // another non-empty line that isn't already blank-line-separated needs \n\n
  text = text.replace(/([^\n])(\n)([ \t]*[^-*>#|\s\n][^\n]*)/g, "$1\n\n$3");

  const result = text.replace(/\n{3,}/g, "\n\n").trim();
  if (debug) console.log("[NORMALIZED OUTPUT]\n" + result);
  return result;
}

interface ChatBubbleProps {
  message:          Message;
  onFollowUpSelect: (text: string) => void;
  isLastMessage:    boolean;
  streamingActive:  boolean;
}

export function ChatBubble({
  message,
  onFollowUpSelect,
  isLastMessage,
  streamingActive,
}: ChatBubbleProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[72%] bg-zinc-100 text-zinc-900 rounded-2xl rounded-tr-sm
                        px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className={`prose prose-zinc prose-sm max-w-none
                       prose-headings:font-semibold prose-headings:text-zinc-900
                       prose-headings:mt-5 prose-headings:mb-2
                       prose-h3:text-base prose-h4:text-sm
                       prose-p:my-3 prose-p:leading-relaxed
                       prose-ul:my-3 prose-ol:my-3
                       prose-li:my-1 prose-li:leading-relaxed
                       prose-a:text-zinc-700 prose-a:underline
                       prose-code:bg-zinc-100 prose-code:rounded prose-code:px-1
                       prose-code:before:content-none prose-code:after:content-none
                       prose-blockquote:border-l-4 prose-blockquote:border-zinc-300
                       prose-blockquote:bg-zinc-50 prose-blockquote:rounded-r
                       prose-blockquote:px-4 prose-blockquote:py-1
                       prose-blockquote:text-zinc-600 prose-blockquote:not-italic
                       prose-hr:my-4 prose-hr:border-zinc-200
                       prose-strong:text-zinc-800 prose-strong:font-semibold
                       ${message.isStreaming ? "typing-cursor" : ""}`.trim()}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            table: ({ children }) => (
              <div className="overflow-x-auto my-4 rounded-lg border border-zinc-200 shadow-sm">
                <table className="min-w-full border-collapse text-sm">{children}</table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-zinc-100 text-zinc-700">{children}</thead>
            ),
            tbody: ({ children }) => (
              <tbody className="divide-y divide-zinc-100">{children}</tbody>
            ),
            tr: ({ children }) => (
              <tr className="even:bg-zinc-50 hover:bg-blue-50 transition-colors">{children}</tr>
            ),
            th: ({ children }) => (
              <th className="px-4 py-2.5 text-left text-xs font-semibold tracking-wide border-b border-zinc-200 whitespace-nowrap">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-4 py-2.5 text-xs text-zinc-700 align-top leading-relaxed">
                {children}
              </td>
            ),
          }}
        >
          {normalizeMarkdown(message.content || (message.isStreaming ? " " : ""), !message.isStreaming)}
        </ReactMarkdown>
      </div>

      {message.disclaimer && (
        <p className="text-[11px] text-zinc-400 leading-relaxed border-t border-zinc-100 pt-2">
          ⚠️ {message.disclaimer}
        </p>
      )}

      {message.citations && message.citations.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-2">
            引用來源
          </p>
          <div className="flex flex-col gap-2">
            {message.citations.map((c, i) => (
              <CitationCard key={i} citation={c} index={i} />
            ))}
          </div>
        </div>
      )}

      {isLastMessage && message.followUps && (
        <FollowUpButtons
          suggestions={message.followUps}
          onSelect={onFollowUpSelect}
          disabled={streamingActive}
        />
      )}
    </div>
  );
}
