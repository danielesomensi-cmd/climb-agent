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

## Convenzione UTM per i canali

Ogni link/QR pubblicato DEVE avere almeno `utm_source`. Schema:

| Canale | Link |
|--------|------|
| Volantino QR (palestra X) | `https://climbagent.app/demo?utm_source=flyer&utm_campaign=<palestra>` |
| Reddit r/SideProject | `https://climbagent.app/?utm_source=reddit&utm_campaign=sideproject` |
| Reddit r/ClaudeAI | `https://climbagent.app/?utm_source=reddit&utm_campaign=claudeai` |
| Instagram bio/post | `?utm_source=instagram&utm_campaign=<post>` |
| Email win-back | `?utm_source=email&utm_campaign=winback-<data>` |
| Passaparola con link personale | `?utm_source=referral&utm_campaign=<nome>` |

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
