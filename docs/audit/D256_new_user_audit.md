# D256 — New User Activity Audit + Email Segmentation

**Data:** 2026-07-21 · **Tipo:** D (audit, read-only — solo SELECT, zero scritture)
**Fonti:** `scripts/admin_dashboard.py` (--days 130), Supabase (users, subscriptions, outdoor_logs), Clerk prod, backup mappatura A249.

## ⚠️ Caveat qualità dati (post-migrazione A249)

La migrazione Clerk dev→prod di oggi ha ricreato TUTTI gli utenti sull'istanza
prod: le date "Iscritto" e "Ultimo login" lette da Clerk sono quindi **tutte
21/07/26 / "mai"** — artefatti, non realtà. In questo report le date di
iscrizione vengono da **Supabase `users.created_at`** (attendibili) e
l'attività dal contenuto dello state (dashboard). Anche `users.updated_at` è
inservibile come proxy di attività: il remap di oggi l'ha toccato per tutti.

---

## Sezione 1 — Ultimo iscritto: `xbox.live.marionumber0001@gmail.com`

**È un signup organico di OGGI, arrivato ore prima del cutover Clerk.**

| Check | Risposta |
|---|---|
| Data signup | **2026-07-21, 12:08 UTC** (first touch 12:08:58Z; riga Supabase 12:10) |
| Auth provider | Clerk, **email + password** (no Google) |
| Attribution | landing `/onboarding/welcome`, **nessun UTM** → direct (link diretto o referrer perso) |
| Onboarding completato | ✅ **Sì, alle 12:23 UTC — 14 minuti dal primo touch.** Goal: all_round, entrambe le discipline, 7b attuale → target 7c redpoint + 7B boulder, deadline 10/11/2026 |
| Assessment | ✅ Completato (con l'onboarding). Profilo 5 assi: finger 59 · pulling 55 · power-endurance 53 · technique 50 · endurance 43 |
| Macrocycle | ✅ Generato: 16 settimane, start 2026-07-20 (lunedì corrente) → **settimana 1/16, fase base** |
| Sessioni | 0 done / 0 skipped — iscritto oggi, nessuna sessione ancora affrontata |
| Ultima attività | 13:12 UTC di oggi (stava ancora navigando ~1h dopo l'onboarding) |
| Stripe | ❌ **Nessuna riga subscription** → trial MAI avviato, nessuna carta. Non è mai passato dal checkout (nemmeno `pending_checkout`) |
| Equipment | ✅ Configurato: palestra "Radium" (`gym_boulder`) + home (foam_roller) |

**Due implicazioni per la welcome email:**
1. È un utente **password** iscritto ore prima della migrazione Clerk → al
   prossimo accesso il login non funzionerà: la mail DEVE dirgli di usare
   **"Forgot password"** (una riga, tono "abbiamo migliorato la sicurezza").
2. Non ha mai avviato il trial → CTA della mail = inizia il trial / fai la
   prima sessione.

---

## Sezione 2 — Segmentazione completa (18 righe DB)

Attività (colonna "done") dal dashboard (fonte autorevole per l'archivio
settimane); free/outdoor conteggiati a parte dove rilevanti.

| Utente | Signup | Stripe | Onb. | Assess. | Done | Ultima attività | Email suggerita |
|---|---|---|---|---|---|---|---|
| xbox.live.marionumber0001@ | 21/07 | — (mai checkout) | ✅ | ✅ | 0 | oggi (onboarding) | **welcome** (+ nota reset password) |
| odlan3@ (Andrea Donato) | 09/07 | pending_checkout | ✅ | ✅ | 0 | — | **activation nudge** (già ricontattato 13/07 — follow-up, non doppione) |
| *(riga legacy `80ad598d`)* | 20/06 | — | ❌ | ❌ | 0 | — | **none** (orfano senza clerk_id, vedi anomalie) |
| pippin_91donkeys@ | 31/05 | pending_checkout | ✅ | ✅ | 0 | — | **win-back** (già in lista) |
| arnaud.naert@ | 28/05 | canceled (trial finito 14/06) | ✅ | ✅ | 0 | — | **win-back** (già in lista; item coupon futuro) |
| daniele.somensi@icloud | 07/05 | — | ❌ | ❌ | 0 | — | **none** (account test founder, onboarding incompleto) |
| edoardoborghini91@ | 06/05 | — | ✅ | ✅ | 0 | — | **win-back** |
| woween@ (Rowene) | 05/05 | — | ✅ | ✅ | 0 | — | **win-back** |
| dani.some@proton.me | 21/04 | pending_checkout | ✅ | ✅ | 0 | — | **none** (account test founder) |
| arthur.pepin11@ | 09/04 | — | ✅ | ✅ | 0 | — | **win-back** |
| pewen.outdoors@ (Agustin) | 01/04 | — | ✅ | ✅ | 0 | — | **win-back** (beta tester, piano scaduto) |
| cesar.e.meric@ | 01/04 | pending_checkout | ✅ | ✅ | 2 | 21/04 | **win-back** (+ nota reset password: utente password) |
| paul.cample@ (Paolo) | 01/04 | — | ✅ | ✅ | 0 | — | **win-back** (beta tester) |
| tabithamann90@ | 01/04 | — | ✅ | ✅ | 0 | — | **win-back** |
| romitodavid@ (David R) | 24/03 | — | ✅ | ✅ | 0 (1 free 24/03) | 24/03 | **win-back** |
| daniele.somensi@ferrero | 21/03 | canceled | ✅ | ✅ | 0 | — | **none** (account test founder) |
| daniele.somensi@gmail | 16/03 | pending_checkout (bypass attivo) | ✅ | ✅ | **71** | 20/07 | **none** (founder) |
| ckb.palmer@ (Christie) | 16/03 | — | ✅ | ✅ | **9** (+3 free, 6 outdoor) | 07/04 | **win-back** (la più ingaggiata dopo il founder: personalizzare) |

**Sintesi operativa per Gmail:**
- **welcome** (1): xbox.live.marionumber0001@gmail.com — oggi/domani, con nota "Forgot password"
- **activation nudge** (1): odlan3@gmail.com — follow-up del contatto del 13/07
- **win-back** (9 + 2 già coperti): ckb.palmer, cesar.e.meric, romitodavid, tabithamann90, paul.cample, pewen.outdoors, arthur.pepin11, woween, edoardoborghini91 (+ arnaud, pippin già in lista). Contenuti comuni: nuovo dominio `climbagent.app`, reinstallare la PWA, re-login (Google = un click; **password** = Forgot password → riguarda cesar, arthur, pippin)
- **retention** (0): nessun utente attualmente in trial attivo — il segmento è vuoto
- **none** (5): founder ×4 (gmail, icloud, ferrero, proton) + riga legacy

**Nota di quadro:** ad oggi nessun utente ha un trial attivo o paga — l'unica
attività reale delle ultime settimane è del founder. La win-back non è una
mail di cortesia: è di fatto il **re-lancio** del prodotto sul nuovo dominio.

---

## Sezione 3 — Anomalie rilevate (solo report, fix = brief separati)

1. **Date Clerk inservibili post-A249** — `created_at`/`last_sign_in` su Clerk
   prod riflettono la migrazione, non i signup reali. `admin_dashboard.py`
   mostra "Iscritto 21/07" per tutti e "Ultimo login: mai". *Candidato fix:*
   il dashboard dovrebbe preferire `users.created_at` (Supabase) per la data
   iscrizione.
2. **Ultimo iscritto senza riga subscription** — onboarding completo ma mai
   passato dal checkout: da verificare cosa vede in app (guard B202
   fail-closed → probabile paywall subito dopo l'onboarding). Se è così, il
   funnel "onboarding finito → paywall" merita un occhio (conversione).
3. **Riga orfana `80ad598d`** (creata 20/06, `clerk_id NULL`, state vuoto) —
   residuo pre-migrazione di un flusso legacy/anonimo. Candidata a cleanup
   manuale (admin delete), nessuna urgenza.
4. **`daniele.somensi@icloud.com` onboarding incompleto** — stato presente ma
   senza assessment/macrocycle. È un account di test del founder: nessuna
   azione, ma spiega il 🔴 del dashboard.
5. **Tabelle `session_logs` ed `event_logs` VUOTE** — tutta l'attività vive
   nello state JSONB (week archive). Se è by design (D-storage), il naming
   delle tabelle inganna; se non lo è, c'è un log mai scritto. Da chiarire in
   un brief D dedicato.
6. **`pending_checkout` per 5 utenti** (founder, cesar, dani.some, odlan3,
   pippin) — checkout aperto e mai completato; coerente con l'epoca pre-B202.
   Nessuna azione: si risolve da sé al prossimo checkout completato.
7. **"Piano scaduto" per 5 utenti** (macrocycle oltre le settimane totali) —
   atteso per utenti fermi da mesi; la win-back dovrebbe suggerire "Start new
   cycle" come primo passo al rientro.

---
*Vincolo rispettato: nessuna scrittura (solo SELECT / API read-only). Nessun
invio email da questo brief — invii manuali da Gmail a cura di Daniele.*
