# Attribution & UTM convention (A233)

Dal 2026-07-13 ogni nuovo utente porta con sé la **first-touch attribution**:
al primo accesso il frontend salva in localStorage `utm_*`, referrer esterno,
landing page e timestamp (TTL 30 giorni); al completamento dell'onboarding il
record viene inviato a `POST /api/onboarding/complete`, sanitizzato
server-side (whitelist chiavi + cap 200 char) e persistito in
`user_state.attribution` con timestamp server `onboarded_at`.

Lettura: `scripts/admin_dashboard.py` mostra la colonna **Origine** nella
sezione "Nuovi iscritti" (`utm_source/utm_campaign` → hostname referrer →
`direct`; `—` = utente pre-A233).

## Landing page: quale path usare

⚠️ **MAI linkare la root `/` in un canale di acquisizione**: per un visitatore
anonimo la root fa redirect client-side a `/sign-in` (Clerk) — un curl
restituisce 200 e sembra ok, ma nel browser l'utente atterra sul form di
login e rimbalza. Verificato su prod il 2026-07-21 (A249-pre).
La root va bene SOLO per utenti esistenti (es. email win-back).

Regola (decisione Daniele, 2026-07-21):

- **Link SENZA contesto** (QR volantino: scan a freddo in palestra, il link
  deve vendere da solo) → **`/demo`**: mostra una sessione reale, poi CTA
  verso l'onboarding.
- **Link CON contesto** (post Reddit/Instagram, messaggio personale: chi
  clicca ha già visto screenshot e descrizione) → **`/onboarding/welcome`**:
  un hop in meno verso il sign-up.

Entrambe le pagine sono pubbliche e catturano gli UTM (`AttributionCapture`
è nel root layout → first-touch su qualsiasi pagina di atterraggio).

## Convenzione UTM per i canali

Ogni link/QR pubblicato DEVE avere almeno `utm_source`. Schema (link completi,
copia-incollabili):

| Canale | Pubblico | Link |
|--------|----------|------|
| Volantino QR (palestra X) | freddo, zero contesto | `https://climbagent.app/demo?utm_source=flyer&utm_campaign=<palestra>` |
| Reddit r/SideProject | freddo, con contesto | `https://climbagent.app/onboarding/welcome?utm_source=reddit&utm_campaign=sideproject` |
| Reddit r/ClaudeAI | freddo, con contesto | `https://climbagent.app/onboarding/welcome?utm_source=reddit&utm_campaign=claudeai` |
| Instagram bio/post | freddo, con contesto | `https://climbagent.app/onboarding/welcome?utm_source=instagram&utm_campaign=<post>` |
| Email win-back (utenti esistenti) | esistente | `https://climbagent.app/?utm_source=email&utm_campaign=winback-<data>` |
| Passaparola con link personale | freddo, con contesto | `https://climbagent.app/onboarding/welcome?utm_source=referral&utm_campaign=<nome>` |

Regole:
- `utm_source` minuscolo, un solo valore per canale (niente varianti tipo
  `Reddit`/`reddit.com`).
- `utm_campaign` identifica la singola iniziativa (palestra, subreddit, data).
- Traffico senza UTM resta comunque attribuibile via referrer (es.
  `www.reddit.com`) — ma il referrer si perde spesso su mobile/app in-app
  browser, quindi gli UTM restano obbligatori sui link che controlliamo.
- I QR già stampati senza UTM continuano a funzionare: appariranno come
  `direct` con landing `/demo` (che di fatto identifica il volantino).
- **Dominio canonico da A248 (2026-07-21): `https://climbagent.app`.** I link
  già pubblicati col vecchio `climb-agent.vercel.app` restano validi: il 308
  redirect di Vercel preserva path e query string, quindi gli UTM
  sopravvivono (verificato). I nuovi link vanno pubblicati SOLO col dominio
  nuovo.
