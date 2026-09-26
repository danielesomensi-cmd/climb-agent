// A286 — una sola palette di fase per i quattro player (guided timer, Core
// Circuit, Mobility flow, Tabata). Prima "work" era arancione, teal o viola e
// "rest" emerald, blu o giallo/rosso a seconda della schermata: stesso evento,
// tre colori. Qui la mappa è una sola ed è costruita sui token A214.
//
// Vive dentro components/session-play e non in src/lib perché il gruppo B di
// A286 poteva toccare solo i file dei player.
//
// Scelta cromatica: work = warning (ambra, il colore dello sforzo), rest =
// info (blu, il colore della calma), done = success. `prepare` resta neutro —
// non sta succedendo ancora niente, e serve che si distingua dal rest.
// I colori restano pieni e saturi: vanno letti a un metro di distanza.

export type PlayerPhase = "prepare" | "work" | "rest" | "done";

/** Etichetta di fase e cifre colorate. */
export const PHASE_TEXT: Record<PlayerPhase, string> = {
  prepare: "text-foreground",
  work: "text-warning",
  rest: "text-info",
  done: "text-success",
};

/** Arco di progresso SVG. */
export const PHASE_RING: Record<PlayerPhase, string> = {
  prepare: "stroke-muted-foreground",
  work: "stroke-warning",
  rest: "stroke-info",
  done: "stroke-success",
};

/**
 * Sfondo dei player fullscreen. Sono overlay translucidi sopra
 * `bg-background`, come lo erano prima: la tinta è una velatura, non un fondo
 * opaco.
 */
export const PHASE_BG: Record<PlayerPhase, string> = {
  prepare: "bg-muted/60",
  work: "bg-warning/15",
  rest: "bg-info/15",
  done: "bg-card",
};
