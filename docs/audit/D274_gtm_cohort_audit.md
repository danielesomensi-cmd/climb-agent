# D274 — GTM Cohort Audit

**Type:** D (audit, read-only — zero writes to Supabase, Stripe or Clerk)
**Date:** 2026-08-10
**Scope:** every account that has ever existed in production (20 rows in `public.users`)
**Sources:** Supabase Postgres (SELECT only, via `SUPABASE_DB_URL`), Clerk BAPI (GET only),
Stripe API (list/retrieve only, including charges, refunds and balance transactions).
Baseline cross-checked against `scripts/admin_dashboard.py --json --days 90` and
`scripts/gtm_funnel.py --days 90`.

---

## 1. Executive summary

- **20 accounts ever. 11 are real external users**; the rest are the author (1), the author's own
  test accounts (3), named beta testers (4) and one orphan row (1).
- **1 external user out of 11 has ever completed a single session.** Zero have reached three.
  The last time any non-author completed a session was **2026-04-21** — 111 days ago.
- **Lifetime net revenue is −€0.47.** One person ever paid ($4.99, 2026-06-14) and requested a
  refund **four hours later**; Stripe kept the processing fee. Current MRR: **$0.00**.
- Both sprint targets missed badly: **9 external trials vs ≥30**, **0 paying vs ≥2**. The one
  person who did pay had completed **zero** sessions before paying.
- The drop-off is **not** acquisition and **not** the assessment. Everyone who creates an account
  completes all 12 wizard steps and gets a macrocycle (11/11). They then stop. **Verdict: pause
  marketing, keep it as a personal tool** — details in §6.

---

## 2. Funnel

### 2.1 A measurement caveat that has to come first

Since **A256 (2026-07-23)** the entire onboarding wizard is public and the account is only
requested at the final submit CTA. Consequence: **a visitor who drops before submitting leaves
no server-side trace at all** — their draft lives in `localStorage`, never in the DB. So the
brief's question "do users complete the assessment or drop before it?" **cannot be answered from
production data.** Every row in `users` is, by construction, someone who already finished the
wizard.

That signal *is* instrumented — `public_assessment_view`, `public_assessment_completed`,
`public_assessment_cta`, `demo_viewed`, `subscribe_viewed`, `checkout_clicked` all fire into
Vercel Analytics (`frontend/src/lib/analytics.ts`). **I could not read it**: the local Vercel CLI
token (`~/Library/Application Support/com.vercel.cli/auth.json`) returns
`{"error":{"code":"forbidden","invalidToken":true}}`. Numbers for the pre-signup funnel are
therefore **absent from this report, not zero** — they must be read manually from the Vercel
dashboard (Analytics → Events, project `climb-agent`).

**What this means for the verdict:** it does not change it. Even if the pre-signup funnel were
perfect, the measurable post-signup funnel below converts at 9%/0%.

### 2.2 External cohort funnel (11 users — author, author test accounts, betas and the orphan row excluded)

| Step | Count | % of signups | % step-over-step |
|---|---|---|---|
| Accounts created (signups) | 11 | 100% | — |
| Wizard completed (12 steps) | 11 | 100% | 100% |
| Assessment profile computed | 11 | 100% | 100% |
| Macrocycle generated | 11 | 100% | 100% |
| Opened the app on ≥1 day after onboarding | 7 | 64% | 64% |
| **≥1 session completed** | **1** | **9%** | **14%** |
| ≥3 sessions completed | 0 | 0% | 0% |
| Checkout started | 3 | 27% | — |
| Paid | 1 | 9% | 33% of checkouts |
| **Still paying today** | **0** | **0%** | **0%** |

**Biggest drop-off: macrocycle generated → first session completed. 11 → 1 (−91%).**

Two secondary observations that matter as much as the headline:

- The 27% who started checkout is **not** a positive signal. It is inflated by the pre-A250 flow:
  before 2026-07-21 there was no auto-trial, so reaching the paywall was mandatory to use the app
  at all. Two of the three (`pippin_91donkeys`, `odlan3`) abandoned and are now permanently
  walled — see §7.
- The single paying customer (`arnaud.naert`) had completed **zero** sessions when Stripe charged
  him at trial end, and asked for a refund within four hours. That is the cleanest possible
  statement of the value problem: the trial expired without the product ever being used.

### 2.3 Same funnel including beta testers (15 users)

| Step | External (11) | + betas (15) |
|---|---|---|
| Macrocycle generated | 11 | 15 |
| ≥1 session completed | 1 (9%) | 3 (20%) |
| ≥3 sessions completed | 0 (0%) | 1 (7%) |
| Paying today | 0 | 0 |

The betas only move the number because of **one** person (Christie Palmer, 20 sessions), who
stopped on **2026-04-07**.

---

## 3. Per-user detail

Signup date is `public.users.created_at`. **Do not use Clerk `created_at`** — the A249 production
migration (2026-07-21) rewrote it to 2026-07-21 for every pre-existing user, and reset
`last_active_at`, which is why so many long-standing users read as "never logged in". Same reason
`users.updated_at` is useless as a recency signal: the migration touched every row.

"App-days" = length of `state.quote_history`, one id appended per day the app is opened. It is a
ring buffer capped at 30, so `30` means "30 or more". `/api/quotes/daily` is **not**
subscription-gated, so this counts opens even for walled users.

### 3.1 External cohort (the actual trial cohort)

| # | User | Signup | Plan? | App-days | Sessions done | Last session | Checkout | Sub status today | Days silent |
|---|---|---|---|---|---|---|---|---|---|
| 1 | D.R. `2208` | 2026-03-24 | ✅ | 5 | **1** (free) | 2026-03-24 | — | trialing (expired 08-05) | 53 |
| 2 | T.M. `6cf9` | 2026-04-01 | ✅ | 2 | 0 | — | — | trialing (expired 08-05) | ~131 |
| 3 | A.P. `ce89` | 2026-04-09 | ✅ | 1 | 0 | — | — | trialing (expired 08-05) | ~123 |
| 4 | R.S. `611e` | 2026-05-05 | ✅ | 0 | 0 | — | — | trialing (expired 08-05) | ~97 |
| 5 | E.B. `3fc2` | 2026-05-06 | ✅ | 0 | 0 | — | — | trialing (expired 08-05) | ~96 |
| 6 | **A.N. `5268`** | 2026-05-28 | ✅ | 8 | **0** | — | ✅ **paid + refunded** | canceled (2026-07-13) | 28 |
| 7 | P. `7208` | 2026-05-31 | ✅ | 0 | 0 | — | ✅ abandoned | **pending_checkout — walled** | ~71 |
| 8 | **A.D. `5a98` (Donato)** | 2026-07-09 | ✅ | 6 | 0 | — | ✅ **abandoned ×2** | **pending_checkout — walled** | 13 |
| 9 | M. `bcab` | 2026-07-21 | ✅ | 0 | 0 | — | — | trialing (expired 08-05) | 19 |
| 10 | J. `e60d` (Reddit) | 2026-08-05 | ✅ | 1 | 0 | — | — | **trialing — live until 08-20** | 5 |
| 11 | S.P. `f8ff` | 2026-08-05 | ✅ | 1 | 0 | — | — | **trialing — live until 08-20** | 5 |

Median app-days across the external cohort: **1**. Median sessions: **0**.

"Days silent" is the gap to the last *provable* activity — a completed session, a `week_archive`
row written server-side, or a Clerk `last_active_at` that post-dates the A249 migration. Where
none of those exist the value is measured from signup and marked `~`; it is a lower bound on
inactivity, never an over-estimate.

### 3.2 Beta testers (labeled, excluded from the funnel above)

| User | Signup | App-days | Sessions | Last session | Status |
|---|---|---|---|---|---|
| Christie Palmer `79fa` | 2026-03-16 | 30+ | **20** (11 guided + 3 free + 6 outdoor) | **2026-04-07** | trialing (expired 08-05) |
| Cesar Meric `9e41` | 2026-04-01 | 1 | 2 | **2026-04-21** | trialing (expired 08-05) |
| Paolo Campli `d7f6` | 2026-04-01 | 1 | 0 | — | trialing (expired 08-05) |
| Agustin Toro `f496` | 2026-04-01 | 3 | 0 | — | trialing (expired 08-05) |

**2 of 4 betas ever trained. Both stopped in April.** No beta has opened a session in 111 days.

### 3.3 Author and author test accounts (excluded)

| Account | Signup | Sessions | Last session | Notes |
|---|---|---|---|---|
| `daniele.somensi@gmail.com` `7ea9` | 2026-03-16 | **132** | **2026-08-08** | The author. 90 coach messages (the only coach user ever), 33 outdoor logs, 25 archived weeks. |
| `daniele.somensi@ferrero.com` `98f7` | 2026-03-21 | 0 | — | Test account (display name `efffdasdf`). Stripe sub canceled 2026-05-01. |
| `dani.some@proton.me` `42c3` | 2026-04-21 | 0 | — | Test account (`Daniprova`). pending_checkout. |
| `daniele.somensi@icloud.com` `0ca9` | 2026-05-07 | 0 | — | Empty state — onboarding never completed. No subscription row. |

`daniele.somensi+nocard1@gmail.com` appears in Stripe checkout sessions (2026-07-13) as an A250
trial test; it has no `users` row.

### 3.4 Orphan row

`80ad598d…` — `users` row created 2026-06-20 17:23:01, last updated **1.7 seconds later**,
`clerk_id` NULL, state `{}`, no subscription row, no Clerk user. Not a person who churned; a row
that was created and abandoned in under two seconds. Excluded from all counts. See §7.

---

## 4. Cohort health and timing

### 4.1 Signups per week (all 20 accounts, `users.created_at`)

```
2026-03-16  ###   3      ← author + Christie + author test
2026-03-23  #     1
2026-03-30  ####  4      ← beta wave (Cesar, Paolo, Agustin, Tabitha)
2026-04-06  #     1
2026-04-13        0
2026-04-20  #     1
2026-04-27        0
2026-05-04  ###   3
2026-05-11        0
2026-05-18        0
2026-05-25  ##    2      ← Arnaud, pippin
2026-06-01        0
2026-06-08        0
2026-06-15  #     1      ← orphan row
2026-06-22        0
2026-06-29        0
2026-07-06  #     1      ← Donato
2026-07-13        0
2026-07-20  #     1      ← Mario
2026-07-27        0
2026-08-03  ##    2      ← Jason (Reddit referrer) + Selias
```

Since the beta wave ended (2026-04-13), the run rate is **11 signups in 17 weeks ≈ 0.65/week**,
and that includes the author's own test accounts and the orphan row. There **is** a faint organic
trickle: it is roughly **one real external signup every two weeks**, and it has never once
converted into a completed session.

### 4.2 What the Reddit post actually produced

The r/climbharder post went up in the first week of August, stayed up two days and ended in a ban
(GTM-05, 2026-08-08). Measured result: **2 signups on 2026-08-05**, of which **one** carries a
confirmed Reddit referrer (`android-app://com.reddit.frontpage/`, user `e60d7a0c`). Both completed
onboarding, generated a macrocycle, and **neither has returned since the day they signed up**.
Both trials are still live until 2026-08-20 and both users have been silent for 5 days.

Attribution data exists for only **4 of 20** accounts — `state.attribution` was added by A233 and
is only written at onboarding, so the entire pre-July cohort has none. No UTM parameter has ever
been recorded; the four records carry `landing_page` and `referrer` only.

### 4.3 Trajectory over the last 30 days (2026-07-11 → 2026-08-10)

| | |
|---|---|
| New external signups | 3 (Mario, Jason, Selias) |
| Sessions completed by anyone except the author | **0** |
| Coach messages by anyone except the author | **0** |
| Checkouts started | 1 (Donato, abandoned) |
| Revenue | **$0** |
| Refunds | 0 (the only one was 2026-06-14) |

**No non-author human has completed a training session in this app since 2026-04-21.**

---

## 5. Revenue reality check

| | |
|---|---|
| Active paid subscriptions | **0** |
| Current MRR | **$0.00** |
| Customers who ever paid | **1** (`arnaud.naert`, 2026-06-14) |
| Gross charged, lifetime | €4.31 ($4.99, Founding Climber price) |
| Refunded | €4.31 — **same day, 4 hours later**, `requested_by_customer` |
| Stripe fees retained | €0.40 + €0.03 + €0.04 |
| **Net lifetime revenue** | **−€0.47** (confirmed via Stripe balance: `available: −47 EUR`) |

Stripe subscription history is three objects, all `canceled`: the author's `@ferrero.com` test
(2026-04-16 → 2026-05-01), Arnaud (2026-05-30 → 2026-07-13), and the `+nocard1` A250 test
(2026-07-13, canceled after 6 minutes). Fifteen checkout sessions exist; **three** reached
`complete`, and two of those three are the author's own tests.

**Note for `scripts/gtm_funnel.py`:** it reports "Paganti attivi: 0 / Canceled: 3" and has never
surfaced that money actually moved and came back. The tool has no lifetime-revenue line, so the
−€0.47 was invisible until this audit queried `Charge`/`Refund`/`BalanceTransaction` directly.

---

## 6. Honest assessment

### 6.1 Did the sprint hit its targets?

The targets in the brief (≥30 trials, ≥2 paying) are **not recorded anywhere in the repo** — the
roadmap's own written target was GTM-07, *"3–5 paying by end of April 2026"*, already marked
expired and missed. Against the brief's numbers:

| Target | Actual | Miss |
|---|---|---|
| ≥30 trials | **9** external trials ever granted (13 counting betas) | **−70%** (−57% counting betas) |
| ≥2 paying | **1 ever, refunded within 4 hours. 0 today.** | **−100%** |

And the 9 is generous. **Five of them were granted retroactively** by the A251 win-back script on
2026-07-21 to users who had already been dormant for months (`romitodavid`, `tabithamann90`,
`arthur.pepin11`, `woween`, `edoardoborghini91`) — none of the five came back. Only **4** trials
correspond to a live signup: Mario, Jason and Selias via A250's auto-start, and Arnaud's Stripe
trial (2026-05-30). Meanwhile the two external users who *did* click checkout on their own
(`pippin`, `odlan3`) were never granted a trial at all — see §8.

There is no reading of the data under which the sprint succeeded.

### 6.2 Is there any signal of product-market fit?

**No — and the absence is unusually clean.** Going through the usual evidence one by one:

- **Repeat usage by a stranger:** none. Zero external users reached 3 sessions. Zero reached 2.
- **Repeat usage by anyone:** one beta tester (Christie, 20 sessions over three weeks in
  March–April) and the author. Both are people who know Daniele.
- **Completed assessments:** 11/11 — but this is *not* PMF evidence. It measures intent to try,
  and intent is the one thing that is demonstrably fine. People do 12 wizard steps and then quit.
- **Organic signups:** roughly 1 every two weeks, sustained across five months with essentially no
  marketing. That is a real, if tiny, signal that the *idea* attracts people.
- **Willingness to pay:** tested exactly once and failed in the strongest possible way — the
  customer paid, then reversed it within four hours, having completed zero sessions.
- **Unsolicited demand:** no inbound requests, no referrals, no word of mouth in the data.

The honest summary: **the pitch works and the product does not retain.** Interest converts to
signup and signup converts to plan; nothing converts to training.

### 6.3 What does the drop-off point tell us?

The drop is at **macrocycle generated → first session**, and it is **91%**. This rules out two of
the three candidate explanations:

- **Not an acquisition problem.** Acquisition is weak in volume, but the people who do arrive are
  maximally qualified: they finished twelve onboarding steps. Sending more of them into a funnel
  that converts 9% multiplies by roughly zero. This is exactly the conclusion D273 reached on
  2026-08-07, *before* the Reddit post — and the post then produced 2 signups and 0 sessions,
  confirming it empirically.
- **Not an onboarding-completion problem.** 11/11 finish the wizard.
- **It is a first-use value problem.** `docs/audit/D273_first_session_activation.md` measured the
  mechanism against real production state: the shortest catalog session with a wall is **70
  minutes** (and it is a deload); the rest are 85–100. For several profiles the first day serves
  **prehab**, not climbing — that is literally what Jason, the one Reddit signup, was shown 18
  seconds after onboarding. A person who just spent ten minutes describing their climbing is
  handed rotator-cuff work and an 85-minute gym block three days out.

There is a second, compounding structural fact: **there is no return channel at all.** No push
handler in the service worker, no transactional email; the only `notify()` in the codebase sends
Daniele a Telegram message. Every plan that puts the first session more than a few hours away is a
bet on the user's memory, and the data says that bet loses 10 times out of 11.

### 6.4 Cost/benefit of continuing active marketing

Against the three constraints given:

- **r/climbharder is burned** — permanently banned, not merely cooling off until mid-September.
  r/bouldering was already closed. Only r/indoorbouldering remains, at one post per month inside a
  *Simple Questions* thread. Any replacement channel is unproven, requires Daniele-written prose
  (the ban was for prose that read as AI-generated, not for the product), and would take weeks to
  test.
- **App Store is blocked** without IAP work — a multi-week project with Apple's 30% and a review
  cycle attached, for a product with no retained users to monetize.
- **Kalymnos, 2026-08-20 → mid-September** — roughly four weeks of no availability. Any channel
  opened before departure would deliver its traffic into a funnel nobody is watching, onto an
  activation defect that is documented but unfixed, with no email or push to recover the drop-offs.

The expected value of marketing work right now is **negative**: it consumes the scarce resource
(Daniele's writing time and pre-trip weeks), burns finite first-impressions in the few remaining
communities, and the measured conversion of traffic-to-training is 1-in-11 at best and 0-in-2 for
the only channel actually tested.

---

## 7. Recommendation

### **Path 2 — pause marketing; keep climb-agent as a personal tool for now.**

Not a soft version of pushing, and not "hybrid" as a way of avoiding the decision. The public
surfaces (`/assessment`, `/demo`, `/onboarding/welcome`, the apex domain) already exist, cost
nothing to keep online, and should simply be left standing — that is a non-decision, not a
strategy. The actual decision is where Daniele's hours go, and the data says: **not into
acquisition.**

The reasoning, in order of weight:

1. **There is nothing to acquire *into*.** 91% of qualified arrivals never train once. Every hour
   of marketing is multiplied by 0.09 at best, and by 0.00 for the only channel measured.
2. **The one monetization test failed at the product, not the price.** Arnaud paid and reversed it
   in four hours with zero sessions completed. No pricing, positioning or channel change addresses
   that.
3. **The timing is actively hostile.** Four weeks away starting 2026-08-20, no return channel to
   catch drop-offs, and the strongest channel permanently closed.
4. **The tool genuinely works for its one real user.** 132 sessions, 33 outdoor logs, 90 coach
   messages, still active 2026-08-08. That value is real and is not contingent on anyone else
   signing up.

**What this does *not* mean:** it is not a recommendation to stop building. ACT-01 (a short
climbing session available on day one) and ACT-03 (telling the user when they actually climb) are
already scoped from D273, are cheap, and are things Daniele would benefit from **as the user** —
"I'm at the gym with 30 minutes" is his problem too. Do them as personal-tool improvements, on
their own merits, not as GTM prerequisites. ACT-04 (push/email) is infrastructure that only pays
off if there is a cohort to notify; **defer it** until one exists.

### Minimal signal that would justify revisiting

Revisit acquisition when **one** of these becomes true — all three are measurable with what is
already instrumented, none requires new work:

1. **The activation signal (primary):** one non-author user completes **3 sessions within 14
   days** of signing up. This has never happened. It is the single fact whose absence makes every
   other number meaningless, and organic trickle alone (~2/month) will eventually test it for
   free.
2. **The demand signal:** **≥5 organic signups in a calendar month** with no post, no flyer and no
   outreach — roughly 2.5× the current unassisted rate. That would indicate something is pulling
   without being pushed.
3. **The inbound signal:** any unsolicited contact — someone asking for it, referring it, or
   asking to pay. Zero to date.

Check with `python scripts/gtm_funnel.py` once a month. It costs a minute and needs no decision
in between.

---

## 8. Open items surfaced

| # | Item | Severity | Detail |
|---|---|---|---|
| 1 | **Donato (`odlan3`, `5a98187c`) is locked out and it is our doing** | **P1** | Status verified: `pending_checkout`, `trial_start`/`trial_end` **NULL**, no Stripe customer, no Stripe subscription. He signed up **2026-07-09**, before A250 (2026-07-21) auto-started trials, so reaching the paywall was the only way in. He opened two checkout sessions (2026-07-09 23:04 and 2026-07-19 20:16), abandoned both, and `POST /api/subscription/checkout` wrote `status: pending_checkout` on his row. `deps.py:660` lists `pending_checkout` in `_NEVER_STARTED_STATUSES`, so the guard returns **402 "Subscribe to start training."** He is the most engaged external user of the last three months — 6 distinct app-days, 3 weeks planned, 2 weeks archived, returned on **2026-07-28** — and the **A251 win-back whitelist (9 users) did not include him**. He came back and hit a wall. Fix would be a one-off A251-style local trial; **not applied — this audit is read-only.** |
| 2 | `pippin_91donkeys` (`7208f92f`) same lock-out | P3 | Identical mechanism (checkout 2026-05-31, abandoned, `pending_checkout`, never trialed), also excluded from A251. Unlike Donato: **0 app-days, never returned.** Cold — fix only if fixing #1 is scripted anyway. |
| 3 | **`gtm_funnel.py` has never shown that money moved** | P2 | It reports `Paganti attivi: 0` / `Canceled: 3` and stops. The single real charge **and its same-day refund** are invisible; net lifetime revenue (−€0.47) required querying `Charge`/`Refund`/`BalanceTransaction` by hand. One extra line in the script would make this permanently visible. |
| 4 | **Pre-signup funnel is instrumented but unreadable** | P2 | `public_assessment_view` / `_completed` / `_cta` and `demo_*` fire into Vercel Analytics, but the local CLI token is expired (`invalidToken`). Since A256 the server sees **nothing** before submit, so Vercel is the *only* source for "assessment completed vs abandoned". Re-auth `vercel login` or read the dashboard manually. |
| 5 | Orphan `users` row `80ad598d` | P3 | `clerk_id` NULL, state `{}`, created 2026-06-20 17:23:01, updated 1.7s later, no subscription, no matching Clerk user. Either a deleted Clerk user whose row survived, or an aborted row creation. Harmless but it inflates "20 users" to a number that includes a non-person. |
| 6 | 10 `trialing` rows with `trial_end` in the past | P3 | Expiry is lazy (flips only when the user hits the guard), so the A251 win-back cohort still reads `trialing` with `trial_end = 2026-08-05`. Known and correctly handled by `gtm_funnel.py` since B326; noted so the raw DB is not misread. |
| 7 | Clerk timestamps are unusable before 2026-07-21 | P3 | The A249 production migration rewrote `created_at` to 2026-07-21 and cleared `last_active_at` for every pre-existing user. `admin_dashboard.py` shows many long-standing users as "never logged in" for this reason. `users.created_at` in Supabase is the only reliable signup date; `users.updated_at` was also touched by the migration and is not a recency signal. |
| 8 | Attribution coverage is 4/20 | P3 | `state.attribution` (A233) is written only at onboarding, so nothing before July has it, and no UTM parameter has ever been recorded — only `referrer` + `landing_page`. Any future channel test needs the UTM convention in `docs/attribution_utm_convention.md` actually applied to the links. |

---

## Data integrity note

Every number in this report comes from a live read performed on 2026-08-10. No row was written,
updated or deleted in Supabase, Stripe or Clerk; no planner, replanner or macrocycle endpoint was
called, so no past session could have been touched. Where a signal was missing or unreadable it is
labeled as such (§2.1, §8 items 4 and 7) rather than analyzed as a zero. The extraction script is
session scratch and depends on `.env`, so it is not committed.
