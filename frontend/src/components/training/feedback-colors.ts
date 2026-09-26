/**
 * A286 — unica mappa colori per la scala di difficoltà (feedback esercizio).
 *
 * Prima esisteva in tre copie divergenti (session-card, exercise-card,
 * day-card/exercise badge) e due di quelle usavano testo bianco su un fondo
 * saturo 500: ~2,3:1 su dark, sotto AA anche per testo large.
 * Qui il colore sta nel TESTO, su un fondo tenue dello stesso colore.
 *
 * Token funzionali dove esistono (success/warning/danger). "hard" resta
 * l'unico gradino senza token: serve un quinto passo distinguibile fra
 * "ok" (ambra) e "very_hard" (rosso).
 */

export type FeedbackLevel =
  | "very_easy"
  | "easy"
  | "ok"
  | "hard"
  | "very_hard";

/** Ordine crescente di difficoltà percepita. */
export const FEEDBACK_LEVELS: FeedbackLevel[] = [
  "very_easy",
  "easy",
  "ok",
  "hard",
  "very_hard",
];

export const FEEDBACK_LABEL: Record<string, string> = {
  very_easy: "Very easy",
  easy: "Easy",
  ok: "OK",
  hard: "Hard",
  very_hard: "Very hard",
};

/** Chip/badge: testo colorato su fondo tenue dello stesso colore + bordo. */
export const FEEDBACK_CHIP: Record<string, string> = {
  very_easy: "text-success bg-success/20 border-success/40",
  easy: "text-success bg-success/10 border-success/25",
  ok: "text-warning bg-warning/15 border-warning/30",
  hard: "text-orange-300 bg-orange-500/15 border-orange-500/30",
  very_hard: "text-danger bg-danger/15 border-danger/35",
};

/** Pallino pieno (nessun testo sopra: la saturazione qui è legittima). */
export const FEEDBACK_DOT: Record<string, string> = {
  very_easy: "bg-success",
  easy: "bg-success/70",
  ok: "bg-warning",
  hard: "bg-orange-500",
  very_hard: "bg-danger",
};
