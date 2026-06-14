# D245 — Arnaud unexpected payment: investigation + refund remediation

**Status:** COMPLETO (Phase 1 + Phase 2). Unico residuo: rimozione dal bypass (richiede Railway CLI auth) — vedi §Phase 2.
**Date:** 2026-06-14
**Brief number:** D245 (nel brief originale era "D-XXX"; D244 risultava già assegnato al Partner Mode audit).
**Decisioni Daniele:** refund SÌ · opzione A (coupon 100%-off) · webhook fix in brief separato **B259**.

---

## TL;DR — cosa è successo davvero

Arnaud **ha ricevuto il trial standard di 15 giorni** (30 mag → 14 giu), non un addebito immediato. Il "periodo gratuito" lato Stripe = i 15 giorni di trial standard. Oggi (14 giu) il trial è scaduto, la subscription si è rinnovata e Stripe lo ha **addebitato US$4.99** (charge `ch_3TiDA4Dyam3CcHNQ0nPQA1QA`, succeeded, NON ancora rimborsato).

`BYPASS_USER_IDS` gli dava accesso all'app ma **non tocca il billing Stripe** → non poteva e non ha impedito l'addebito alla scadenza del trial.

**Scoperta più grave (oltre ad Arnaud):** la pipeline webhook Stripe→backend è **rotta**. Tutti e 5 gli eventi sottoscritti risultano `pending_webhooks=1` (mai confermati con 2xx), inclusi eventi di 15 giorni fa. Per questo la riga DB di Arnaud è ferma a `pending_checkout` nonostante su Stripe abbia una sub attiva e pagata.

---

## 1a. Identity map

| Campo | Valore |
|-------|--------|
| Email | `arnaud.naert@gmail.com` |
| Nome (Clerk) | Arnaud Naert |
| Clerk ID | `user_3EMxW57a2gfKwAibvOTO5epvcEK` |
| **Internal user_id (UUID)** | `52681ef7-1690-46d9-8b6c-2692020b0aa7` |
| Stripe customer | `cus_Ubz0qNFUk7Wxx0` (email Stripe = `arnaud.naert@gmail.com` ✅ confermato) |
| Timezone | Europe/Brussels |

---

## 1b. Stripe state (LIVE)

**Subscription** `sub_1Tcl3PDyam3CcHNQErLlCvk4`
- status: **active**, created 2026-05-30T11:26:53Z
- **trial: 2026-05-30 → 2026-06-14** (15 giorni standard)
- price `price_1TMq2ADyam3CcHNQ43EHaHi4` = **$4.99 USD "Founding Climber"**
- cancel_at_period_end: false → **continuerà a rinnovare mensilmente se non interveniamo**
- metadata.user_id = `52681ef7-…` ✅ (presente e corretto)

**Invoices**
- `in_1Tcl2X…` — $0.00, `subscription_create`, 2026-05-30 (apertura trial, gratis)
- `in_1TiCDh…` — **$4.99, `subscription_cycle`, status=paid, 2026-06-14T11:28:53Z** (conversione trial → addebito)

**Charge / PaymentIntent (l'addebito da rimborsare)**
- charge `ch_3TiDA4Dyam3CcHNQ0nPQA1QA` — **$4.99 USD, succeeded, refunded=False**, 2026-06-14T12:29:14Z
- payment_intent `pi_3TiDA4Dyam3CcHNQ04tSfCWa` — succeeded

**Checkout session** `cs_live_b1IvHcF…` — status=complete, payment_status=paid, `client_reference_id` + `metadata.user_id` = `52681ef7-…` ✅

**Risposta alla domanda chiave:** NON addebito immediato — c'era un trial standard di 15 giorni, regolarmente applicato. L'addebito è la conversione automatica del trial scaduto oggi.

---

## 1c. Supabase subscription row (DRIFT)

```json
{
  "user_id": "52681ef7-1690-46d9-8b6c-2692020b0aa7",
  "stripe_customer_id": null,
  "stripe_subscription_id": null,
  "status": "pending_checkout",
  "trial_end": null,
  "created_at": "2026-05-30T11:24:42Z",
  "updated_at": "2026-05-30T11:24:42Z"
}
```
Ferma a `pending_checkout`, mai aggiornata, nessun link a Stripe. **Drift totale** rispetto a Stripe (active, pagata). Causa: webhook non processato (§Webhook).

---

## 1d. App activity

- Onboarding/assessment ✅ (radar: finger 50, pulling 44, power_end 75, technique 80, endurance 70)
- Goal: all_round, both, 7a+→7b+ (boulder 6C+), deadline 2026-09-19
- Macrocycle ✅ 16 settimane / 5 fasi, start 2026-05-25; 2 week_plans generati
- **Sessioni completate: 0** — `session_logs`=0, `outdoor_logs`=0, `event_logs`=0, `recent_sessions`=0

**Invariante past-sessions-immutability:** banalmente intatta (nessun dato storico esiste). Nessuno step di Phase 2 tocca dati storici.

---

## 1e. Bypass state

`/api/subscription/status` per `52681ef7-…` → `{"status":"active","is_active":true,"trial_days_remaining":null,"can_interact":true}` = firma `_ALLOW_ALL`. Dato che la riga reale è `pending_checkout`, l'unico modo per ottenere `active` in prod è il branch bypass.
→ **Confermato: è in `BYPASS_USER_IDS` su Railway.**

⚠️ Conseguenza per Phase 2: la sua riga DB dice `pending_checkout` → senza bypass il guard B202 lo **negherebbe**. L'opzione "A" del brief (coupon → guard passa legittimamente) **non funziona oggi** perché il webhook non sincronizza la sua riga: servirebbe prima fixare il webhook o aggiornare la riga a mano.

---

## Webhook — root cause sistemico (P0)

Endpoint configurato e **abilitato**: `we_1TMq7RDyam3CcHNQ0Hq2Nou2` → `https://web-production-fb1e9.up.railway.app/api/stripe/webhook` (creato 2026-04-16, eventi corretti).

Ma gli eventi sottoscritti risultano **mai consegnati con successo** (`pending_webhooks=1`):

| Evento | Data | pending_webhooks |
|--------|------|------------------|
| checkout.session.completed | 2026-05-30 | **1** ❌ |
| invoice.payment_succeeded | 2026-05-30 | **1** ❌ |
| customer.subscription.updated | 2026-06-14 | **1** ❌ |
| invoice.payment_succeeded (addebito) | 2026-06-14 | **1** ❌ |

Eventi vecchi di 15 giorni ancora a `pending_webhooks=1` = Stripe ha esaurito i retry senza mai ricevere 2xx. **Il backend rifiuta/fallisce ogni delivery.** Ipotesi più probabile: `STRIPE_WEBHOOK_SECRET` su Railway non combacia con il signing secret dell'endpoint → `construct_event` solleva `SignatureVerificationError` → 400 → evento mai processato. (Alternative: handler 500, o env mancante.) Da verificare leggendo i Railway logs (riga DIAG `stripe_webhook recv … webhook_secret=…`) o ritestando la firma.

### Blast radius (LIVE)
Solo **2 subscription Stripe in totale** dall'inizio:
1. Arnaud `sub_1Tcl3P` — active, **addebitato $4.99 oggi**, riga DB `pending_checkout` (drift).
2. `sub_1TMrt9` (user `98f77487-5f4d-4d74-bd24-90661bbfa3da`) — **canceled** (trial 16 apr→1 mag, mai pagato); riga DB ancora `trialing` (drift).

Le altre 3 righe `pending_checkout` (20 apr, 21 apr, 31 mag) **non hanno sub Stripe** → checkout abbandonati, legittimi.

→ Impatto finanziario reale: **solo Arnaud**. Ma il webhook va riparato prima che arrivino utenti paganti veri.

---

## Cosa sistemare per il futuro

1. **[P0] Webhook Stripe→backend rotto** — brief B separato. Verificare `STRIPE_WEBHOOK_SECRET` su Railway vs signing secret dell'endpoint `we_1TMq7R`; controllare Railway logs DIAG; ritestare delivery. Senza questo, ogni futura subscription resterà desincronizzata.
2. **[Lesson] `BYPASS_USER_IDS` ≠ esenzione pagamento.** Il bypass apre solo il guard di accesso (B202), non blocca il checkout/billing Stripe. Friends & family devono o (a) NON inserire la carta, o (b) ricevere un coupon 100%-off al checkout.
3. **[Cleanup] Righe DB desincronizzate** (Arnaud + 98f77487) — riconciliare una tantum dopo il fix webhook.

---

## Phase 2 — Remediation ESEGUITA (2026-06-14)

Decisioni Daniele: refund SÌ · **opzione A** (coupon 100%-off) · webhook fix → brief **B259**.

| # | Azione | Esito |
|---|--------|-------|
| 1 | **Refund $4.99** charge `ch_3TiDA4Dyam3CcHNQ0nPQA1QA` | ✅ refund **`re_3TiDA4Dyam3CcHNQ0HsD67I6`**, $4.99 usd, status=succeeded |
| 2 | **Coupon 100%-off forever** creato + applicato a `sub_1Tcl3P` | ✅ coupon **`bPfe4kTR`** ("Friends & Family — 100% off") → discount **`di_1TiFt9Dyam3CcHNQDSwf42xv`**. Preview prossima fattura (14 lug): subtotal $4.99 → **total $0** |
| 3 | **Sync manuale riga Supabase** (replica webhook) | ✅ riga `6cdc5e1f-…` → `status=active`, `stripe_customer_id=cus_Ubz0qNFUk7Wxx0`, `stripe_subscription_id=sub_1Tcl3P`, trial/period popolati. Solo tabella `subscriptions`, solo riga di Arnaud |
| 4 | **Rimozione da `BYPASS_USER_IDS`** | ⏸️ **RINVIATO per scelta di Daniele** (non bloccante). Funzionalmente **non serve più** (riga reale `active` → guard passa legittimamente); il bypass resta come copertura ridondante innocua. Quando si vorrà ripulire: `railway login` → togliere `52681ef7-…` da `BYPASS_USER_IDS` → redeploy |

### Verifica (2c)
- **Accesso:** `/api/subscription/status` → `{"status":"active","is_active":true,...}` ✅
- **Immutabilità:** `session_logs`/`outdoor_logs`/`event_logs` = 0/0/0 (invariati; mai toccato `user_state`) ✅
- **Rinnovi futuri:** azzerati dal coupon (preview $0) ✅
- Nota: la verifica del path "guard sulla riga reale senza bypass" sarà completa solo dopo lo step 4 (oggi il bypass intercetta prima del lookup riga). La logica è deterministica: `status=active ∈ _ACTIVE_STATUSES` → accesso garantito.

### Follow-up aperti
- **B259** — fix pipeline webhook Stripe→backend rotta (P0). Vedi §Webhook.
- **Step 4** — rimozione bypass (Railway), quando disponibile auth.
