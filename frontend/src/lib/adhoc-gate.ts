// B282/B306 — client-side gate: which coach turns route to the adhoc composer.
//
// Stem-based, message-level co-occurrence — NOT a list of conjugations.
// Italian polite questions conjugate in -i ("mi prepari…?", "mi crei…?",
// "manda tu…") and a fixed verb list loses whack-a-mole against morphology
// (B280/B281 field failures). A session-noun anywhere + a build-verb STEM
// anywhere routes to the composer; clitic forms ("crearla", "mandamela") carry
// the noun inside the verb and count alone. Heavily biased toward routing: a
// false positive costs one cheap extraction returning {adhoc:false} → chat
// fallback; a false negative gives a wrong "I can't build sessions" reply.
const ADHOC_NOUN_RE =
  /\b(sessione|allenament\w*|workout|seduta|scheda|circuito|session|routine)\b/i;
const ADHOC_STEM_RE =
  /\b(cre\w*|prepar\w*|costruis\w*|componi\w*|comporre|gener\w*|fammi|farmi|faresti|fai|d[aà]mmi|darmi|dai|proponi\w*|propor\w*|organizz\w*|mont\w*|mett\w*|aggiung\w*|mand\w*|invi\w*|salv\w*|vorrei|voglio|serve|servirebbe|build\w*|creat\w*|make|compose|design|plan|give|need|want|put together|add)\b/i;
const ADHOC_STANDALONE_RE = new RegExp(
  [
    // clitic object forms — the session-noun lives inside the verb
    "\\b(crearl[ao]|creal[ao]|prepararl[ao]|preparal[ao]|mandarl[ao]|mandal[ao]|salvarl[ao]|salval[ao]|aggiungerl[ao]|aggiungil[ao]|inviarl[ao]|invial[ao]|creamel[ao]|preparamel[ao]|mandamel[ao]|rifall[ao]|rifarl[ao])\\b",
    // being at a gym is a strong signal on its own (EN + IT)
    "\\bat the (regular |commercial )?gym\\b",
    "\\b(in|alla|dalla|nella|della) palestra\\b",
    "sono in palestra",
    "\\bal gym\\b",
    // short "quick X" / "sessione veloce"
    "\\bquick (core|session|workout|pull|push|leg|finger)\\b",
    "\\b(sessione|allenamento) (veloce|rapid[oa])\\b",
  ].join("|"),
  "i",
);

export function looksLikeAdhoc(text: string): boolean {
  return (
    ADHOC_STANDALONE_RE.test(text) ||
    (ADHOC_NOUN_RE.test(text) && ADHOC_STEM_RE.test(text))
  );
}

// B306 — the 2026-07-28 field failure: after the coach offered to build a
// session, the user answered "Si" / "Crea!" — neither passes the noun+stem
// gate, so the turn fell to /chat where the LLM improvised a fake build
// confirmation. The backend extractor already reads the conversation history
// (B281) and is the authority on is_adhoc_request, so the client gate only
// needs to be generous: route any SHORT message to the composer when the
// recent conversation is adhoc-flavored. A false positive costs one cheap
// extraction returning {adhoc:false} → chat fallback.
const FOLLOWUP_MAX_CHARS = 40;
const FOLLOWUP_CONTEXT_WINDOW = 6;

export interface AdhocContextMessage {
  content: string;
  hasAdhocCard?: boolean;
}

export function isAdhocFollowUp(
  text: string,
  recentMessages: AdhocContextMessage[],
): boolean {
  if (text.length > FOLLOWUP_MAX_CHARS) return false;
  return recentMessages
    .slice(-FOLLOWUP_CONTEXT_WINDOW)
    .some((m) => m.hasAdhocCard || looksLikeAdhoc(m.content));
}

export function shouldRouteToAdhoc(
  text: string,
  recentMessages: AdhocContextMessage[],
): boolean {
  return looksLikeAdhoc(text) || isAdhocFollowUp(text, recentMessages);
}
