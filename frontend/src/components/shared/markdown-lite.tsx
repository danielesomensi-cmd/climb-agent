"use client";

// A286 — renderer markdown minimale per le risposte del Coach.
// Il modello scrive in markdown (##, **, liste): prima veniva stampato grezzo
// dentro un whitespace-pre-wrap. Qui lo trasformiamo in nodi React.
//
// Vincoli: zero dipendenze npm e MAI dangerouslySetInnerHTML — l'input arriva
// da un LLM, quindi eventuale HTML nel testo deve restare testo. I link sono
// resi come semplice etichetta, non come <a>: il coach non deve poter far
// navigare l'utente altrove.

import { type ReactNode } from "react";

/** Un token inline per volta: `code`, **bold**, __bold__, *italic*, _italic_, [testo](url). */
const INLINE_RE =
  /(`[^`\n]+`)|(\*\*[^\n]+?\*\*)|(__[^\n]+?__)|(\*[^*\n]+?\*)|(_[^_\n]+?_)|(\[[^\]\n]+\]\([^)\s]*\))/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let n = 0;
  INLINE_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = INLINE_RE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    const key = `${keyPrefix}-i${n++}`;
    if (tok.startsWith("`")) {
      out.push(
        <code
          key={key}
          className="rounded-xs bg-background/60 px-1 py-0.5 font-mono text-[0.85em]"
        >
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (tok.startsWith("**") || tok.startsWith("__")) {
      out.push(
        <strong key={key} className="font-semibold text-foreground">
          {tok.slice(2, -2)}
        </strong>,
      );
    } else if (tok.startsWith("[")) {
      out.push(
        <span key={key} className="font-medium text-foreground">
          {tok.slice(1, tok.indexOf("]("))}
        </span>,
      );
    } else {
      // Delimitatore singolo (*…* / _…_): è corsivo solo se sta fra confini di
      // parola. Senza questa guardia `finger_strength_endurance` diventerebbe
      // "finger<em>strength</em>endurance" e "3*5*2" andrebbe in corsivo.
      const prev = text[m.index - 1];
      const next = text[m.index + tok.length];
      if ((prev && /\w/.test(prev)) || (next && /\w/.test(next))) {
        out.push(tok);
      } else {
        out.push(
          <em key={key} className="italic">
            {tok.slice(1, -1)}
          </em>,
        );
      }
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

type Block =
  | { kind: "h"; level: number; text: string }
  | { kind: "p"; lines: string[] }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "hr" };

const H_RE = /^(#{1,6})\s+(.*)$/;
const UL_RE = /^\s{0,3}(?:[-*+]|•)\s+(.*)$/;
const OL_RE = /^\s{0,3}(\d{1,3})[.)]\s+(.*)$/;
const HR_RE = /^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$/;

export function parseMarkdownLite(src: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] | null = null;
  const flush = () => {
    if (para && para.length) blocks.push({ kind: "p", lines: para });
    para = null;
  };

  for (const rawLine of src.split("\n")) {
    const line = rawLine.replace(/\s+$/, "");
    if (!line.trim()) {
      flush();
      continue;
    }
    if (HR_RE.test(line)) {
      flush();
      blocks.push({ kind: "hr" });
      continue;
    }
    const h = H_RE.exec(line);
    if (h) {
      flush();
      blocks.push({ kind: "h", level: h[1].length, text: h[2] });
      continue;
    }
    const ul = UL_RE.exec(line);
    if (ul) {
      flush();
      const prev = blocks[blocks.length - 1];
      if (prev && prev.kind === "ul") prev.items.push(ul[1]);
      else blocks.push({ kind: "ul", items: [ul[1]] });
      continue;
    }
    const ol = OL_RE.exec(line);
    if (ol) {
      flush();
      const prev = blocks[blocks.length - 1];
      if (prev && prev.kind === "ol") prev.items.push(ol[2]);
      else blocks.push({ kind: "ol", items: [ol[2]] });
      continue;
    }
    if (para) para.push(line);
    else para = [line];
  }
  flush();
  return blocks;
}

export function MarkdownLite({ text, className }: { text: string; className?: string }) {
  const blocks = parseMarkdownLite(text ?? "");
  return (
    <div className={`space-y-2 ${className ?? ""}`}>
      {blocks.map((b, i) => {
        const k = `b${i}`;
        if (b.kind === "hr") return <hr key={k} className="border-border/60" />;
        if (b.kind === "h") {
          // Dentro una bolla di chat anche un h1 resta discreto: cambia il peso,
          // non la dimensione, così il ritmo verticale non esplode.
          const size = b.level <= 2 ? "text-[0.95rem]" : "text-sm";
          return (
            <p key={k} className={`${size} font-semibold text-foreground`}>
              {renderInline(b.text, k)}
            </p>
          );
        }
        if (b.kind === "ul") {
          return (
            <ul key={k} className="ml-4 list-disc space-y-1 marker:text-muted-foreground">
              {b.items.map((it, j) => (
                <li key={`${k}-${j}`} className="pl-0.5">
                  {renderInline(it, `${k}-${j}`)}
                </li>
              ))}
            </ul>
          );
        }
        if (b.kind === "ol") {
          return (
            <ol key={k} className="ml-4 list-decimal space-y-1 marker:text-muted-foreground">
              {b.items.map((it, j) => (
                <li key={`${k}-${j}`} className="pl-0.5">
                  {renderInline(it, `${k}-${j}`)}
                </li>
              ))}
            </ol>
          );
        }
        return (
          <p key={k} className="whitespace-pre-wrap">
            {renderInline(b.lines.join("\n"), k)}
          </p>
        );
      })}
    </div>
  );
}
