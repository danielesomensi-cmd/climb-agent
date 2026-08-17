# D279 — Outdoor experience audit, read-only, ahead of Kalymnos (2026-08-20 →)

**Type:** D (audit, read-only)
**Date:** 2026-08-17
**Scope:** the whole outdoor journey, walked against the code, with Kalymnos as the concrete test case.
**Method:** code read (file:line), engine re-execution against **Daniele's real production state**, prod outdoor log read (Supabase REST, read-only), web research for §3.

> **Path note.** The brief asked for `docs/audits/`. `CLAUDE.md` is explicit — *"All audit deliverables live in `docs/audit/<brief-id>_<topic>.md` (singular `audit/`, never `docs/audits/`)"* — and the directory already holds 20 audits. Filed under the repo convention.

> **Framing note (the brief invited disagreement).** The framing is right, with one correction. This is not "an audit of a feature nobody uses". Outdoor is, measurably, the **most used part of this app by its only real user**: 37 logged outdoor sessions in prod against a `session_logs` table that is empty for everybody. So the bar "will this make 10 days on Kalymnos better for one advanced climber" is not a lowered bar — it is the bar that matches where the usage actually is.

---

## 0. Executive summary

Six of the eight journey steps work. Two do not, and both fail *silently and confidently*, which is worse than failing loudly.

| # | Finding | Severity |
|---|---|---|
| F1 | The friction score **inverts above 26 °C**: 34 °C in full sun scores *higher* than 26 °C. `best_window` will actively point the athlete at the hottest hour of a Kalymnos day. | **Blocks** |
| F2 | The pre-trip deload filter runs in **planner pass 1 only**. Reproduced on Daniele's real state: a `high`-intensity **hangboard session lands on 2026-08-18**, a day the planner itself flags `pretrip_deload: True`, 48 h before the flight. | **Blocks** |
| F3 | A live outdoor session started with the timer has **no offline path**. Routes live in React state + server only; the finish call has no outbox. Offline day → the day's log is lost. | **Blocks** |
| F4 | Outdoor days are **invisible to every fatigue guard**: the ripple threshold (65) has never fired in 37 real sessions (max observed load **33**), outdoor never anchors the 48 h finger gap, never counts against the hard-day cap, never reaches progression. | Degrades |
| F5 | `outdoor_spot_name` is set to the **replanner intent name**. Daniele's trip currently reads *"projecting"*, *"volume"*, *"easy"* instead of crag names — and the coach's geocoder therefore cannot find them. | Degrades |
| F6 | The **pitch ladder is not on the outdoor day page** — the one screen you open at the base of the route. The API returns it there and the page drops it. | Degrades |
| F7 | No sector / aspect / shade concept anywhere. Confirmed: spots store `{id, name, discipline}` and nothing else. | Degrades |
| F8 | No trip concept beyond a 5-day pre-window. `trips[].end_date` is **read by nobody**. Post-trip recovery is designed (§7.2) and not implemented. | Degrades |

---

## 1. Journey walk

Setting: sport lead, ~2 on / 1 off, 30–35 °C, sea humidity, shade critical, 6c–8a, mixed project and onsight days.

### 1.1 Trip declaration

**Today.** There *is* a trip object. Daniele's prod state carries exactly one:

```json
{"name":"Kalymnos","start_date":"2026-08-20","end_date":"2026-09-06","discipline":"lead","priority":"high"}
```

Three consumers, and only three:

| Consumer | file:line | What it does |
|---|---|---|
| `_check_pretrip_overlap` | `backend/engine/macrocycle_v1.py:570-589` | annotates the *phase* with `pretrip_deload` at macrocycle-generation time |
| `compute_pretrip_dates` | `backend/engine/macrocycle_v1.py:862-890` | window = `[start_date − 5d, start_date]`, computed live per week |
| `_week_section` / `_day_extras` | `backend/coach/prompt_builder.py:298-303, 347-348` | the coach sees the trip and the pre-trip flag |

`end_date` is parsed by **nothing**. There is no `trips` entry in `_DAY_LEVEL_FIELDS`, no phase-clock pause, no post-trip block.

**Verified quirk:** the phase annotation is empty in prod (`pretrip_deload: []` on every phase) because the macrocycle was generated 2026-05-18 and the trip was entered later. It is cosmetic — `compute_pretrip_dates` runs live at week-generation time (`backend/api/routers/week.py:376-378`, passed at `:464`), so the *dates* still fire.

**How the trip is actually declared today:** 10+ separate acts. Daniele has already done it by hand — `weekly_overrides` for `2026-08-17` (Thu–Sun `available:false`), `2026-08-24` and `2026-08-31` (all seven days `available:false`), plus one `apply_override` per climbing day. That works: I re-ran `generate_phase_week` with his real merged availability and the trip weeks come back **empty**, correctly.

**Should do.** One declaration — `trips[]` already has `end_date` — that marks the span outdoor, suppresses gym scheduling, and releases the phase clock. Today `end_date` is decoration.

**Gap.** Real but *already worked around*, at the cost of ~20 taps. Not worth fixing before departure.

**The macrocycle side.** Deload pre-trip: the machinery fires, the *filter* does not — see F2 below. Phase clock: not paused; the macrocycle runs to `2026-09-06`, exactly the trip end, so the last three phases (`performance` w14, w15-16) elapse entirely during the trip with no sessions in them. Progression / closed loop: `progression_v1.py` and `closed_loop_v1.py` contain **zero** occurrences of "outdoor" (verified by grep). Ten days of no gym feedback is, to the engine, ten days of nothing happening.

---

### 1.2 Morning of a climbing day

**What `/today` shows.** For a day with `outdoor_spot_name` set, `day-card.tsx:449-634` renders: crag name + discipline badge, an **Open outdoor day** CTA (`:531`), a **Log routes** button, and the A265 `PitchLadderCard` (`:617-634`). For a bare planner `outdoor_slot` with no spot, `:639-647` renders a dashed placeholder — *"Tap 'Add session' to set your spot"*. Nothing else.

**Weather.** `WeatherCard` renders only on today and only from **browser GPS** (`today/page.tsx:1274`, `components/training/weather-card.tsx`). It is not attached to the outdoor day, does not know the crag, and is not shown for tomorrow. Forecast-by-date exists but is reachable only from inside `/outdoor/[date]`, which passes `date` + GPS to `/api/outdoor/strategy` (`outdoor/[date]/page.tsx:173-179`).

**Morning vs afternoon.** `_normalize_forecast` picks *the 3-hour step closest to 12:00 local* as "representative of the climbing day" (`backend/api/routers/weather.py:128-143`). On Kalymnos in August, midday is the one hour of the day nobody climbs. `best_window` (`:217-278`) is the intended remedy — and it is where F1 bites.

#### F1 — the friction score inverts above 26 °C **(blocks)**

`TEMP_HOT_ZERO_C = 26.0` (`backend/engine/weather_v1.py:47`). Above 26 °C the temperature component is pinned at 0 and stops discriminating; its 30 % weight is simply gone. Meanwhile heating the air **raises** the dew spread and **lowers** relative humidity — the two components the score rewards most (30 % + 25 %). I ran the real function over a plausible Kalymnos day:

| Local time | T | RH | Wind | Dew spread | **Score** | **Band** | Headline emitted |
|---|---|---|---|---|---|---|---|
| 07:00 | 26 °C | 65 % | 8 | 7.1 ° | **43** | ok | "Workable conditions — manage expectations." |
| 09:00 | 29 °C | 60 % | 10 | 8.5 ° | **53** | ok | |
| 12:00 | 33 °C | 50 % | 12 | 11.8 ° | **66** | **good** | |
| 15:00 | 34 °C | 45 % | 15 | 13.6 ° | **70** | **good** | "Good conditions — solid day to try hard." |
| 18:00 | 31 °C | 55 % | 14 | 10.1 ° | **63** | good | |

The hottest hour scores **27 points higher** than the coolest. And because `best_window` only looks *forward* and fires when the peak beats now by ≥10 (`:249`), a 07:00 check produces exactly the wrong answer: peak 70 at 15:00 vs current 43 → window emitted, reason string `"humidity drops to 45%"` (the largest weighted component gain). The card would say:

> **Best window today 15:00–18:00 · good · humidity drops to 45%**

at 34 °C, in the Aegean sun. The one saving grace is the limiter suffix, which correctly appends *"Heat is the limiter — seek shade"* to every band — including "good". The headline and the suffix contradict each other.

Note the model is not wrong about *friction physics* — dry air at 34 °C does give grip. It is wrong about **climbing**, where above ~28 °C the athlete, not the rock, is the limiter. The catalog already knows this: `strategy.json` `poor_hot_humid` says *"consider downgrading to Volume/Scout or rest; precool; seek shade"*. It never gets selected, because `catalog_condition_band` maps `good → ok` (`weather_v1.py:297`) and the score says "good" all afternoon.

**Should do.** Above ~26 °C, heat must dominate rather than abstain — a hard band ceiling on air temperature, and `best_window` must never propose a window whose temperature is materially higher than now.

#### The pitch ladder for this athlete

`performance.current_level.sport` in prod: onsight **7a+**, worked **8a+**. Re-running `build_pitch_ladder`:

| day_type | Ladder (grade × attempts) | Est. |
|---|---|---|
| `onsight_flash` | 6a+ ×1 → 6c ×1 → 7a ×1 → **7a+ ×1** → 7b ×2 → 7a ×1 (short rest, on purpose) → 6b+ ×1 | ~3.3 h |
| `project` | 6a+ ×1 → 6c ×1 → 7a ×1 → **8a+ ×3** → 6b+ ×1 | ~2.7 h |

These are sane and genuinely useful. Two problems: **day_type is chosen by the user by hand**, never inferred (`day-card.tsx` → `getPitchLadder({day_type})`, `today/page.tsx:966`); and the ladder is **not shown on the outdoor day page** (F6). Also `build_pitch_ladder` returns `None` for anything but lead (`outdoor_pitch_ladder.py:131`) — correct and honest, irrelevant here.

#### F6 — the ladder is missing from the screen you use at the crag **(degrades)**

`/api/outdoor/strategy` explicitly attaches `pitch_ladder` to its response (`backend/api/routers/outdoor.py:431-441`) so the strategy screen "names actual grades instead of an example ramp". `frontend/src/app/(main)/outdoor/[date]/page.tsx` renders `StrategyView` and never reads `strategy.pitch_ladder` — grep for `pitch_ladder` in that file and in `strategy-view.tsx` returns nothing. The ladder exists only back on `/today` / `/week`, i.e. before you left the apartment. This is the A265 pattern again: built, wired, unreachable from the natural path.

---

### 1.3 Where to climb — F7

There is **no** notion of sector, orientation, sun or shade. `OutdoorSpotCreate` is `{id, name, discipline, typical_days?, notes?}` (`backend/api/models.py:209-215`); the persisted spot drops even those to `{id, name, discipline}` plus optionals (`backend/api/routers/outdoor.py:184-193`). **No coordinates.** The coach's `get_weather` therefore geocodes the spot *by name* (`backend/coach/weather_tool.py:99-114`), which resolves to a village centroid at best. `weather_v1.py:24-25` states the position outright: *"Sun-aspect is intentionally out — it is not auto-fetchable."*

That was true when written and is the single highest-leverage gap for this trip. See §3 for the build/don't-build call.

---

### 1.4 On the rock

**The flow.** `/week` or `/today` → *Open outdoor day* → `/outdoor/[date]` → pick day type → strategy resolves → **Start session** → live logging → *Close & log* → finish.

**What is good.** `LiveRouteLogger` (`components/outdoor/live-route-logger.tsx`) is the best-designed surface in the outdoor stack for a sweaty-hands phone: big Sent/Fell, one-tap extra attempts on the same route without retyping, automatic onsight/flash tagging, a live rest counter against the strategy's suggested rest, and **B279 project mode** — after a fall the panel keeps targeting the same route. That is exactly the Kalymnos redpoint loop.

**What is not.**

#### F3 — no offline path for a timed outdoor session **(blocks)**

Three failures compound:

1. **You cannot start.** `disabled={!gatePassed || (!isBoulder && !strategy)}` (`outdoor/[date]/page.tsx:372`). `strategy` requires a live call to `/api/outdoor/strategy`. No signal → no strategy → the Start button stays greyed out.
2. **Logged climbs are not persisted locally.** `syncRoutes` (`:140-166`) sets React state optimistically then PUTs the whole array; on failure it only calls `setError`. There is no localStorage. Restore-after-crash reads the **server** (`:125-136`). Phone dies mid-session while offline → every route logged that day is gone.
3. **The finish has no outbox.** The outbox covers three kinds — `feedback | outdoor_log | free_climb` (`frontend/src/lib/outbox.ts:34`) — and `OutdoorLogForm` routes to it only when `onSubmit` is absent (`components/training/OutdoorLogForm.tsx:196-214`). Started with the timer ⇒ `onSubmit` is set ⇒ **the outbox is bypassed exactly when a session was started**, with the comment *"needs a live server id"*. Offline at the end of the day → `setError`, and the only escape is to remember the whole day and retype it into the untimed form later.

The fallback path (*Log without timer* → `postOutdoorLog` → outbox) is fully offline-safe. The recommended path is not. That is backwards.

**Relevance to Kalymnos:** Masouri-side sectors have coverage; Sikati Cave is a 100 m sinkhole reached by abseil, Telendos needs a boat. Those are precisely the days worth logging.

---

### 1.5 End of day

**Finish → immutable log.** `POST /session/{id}/finish` (`outdoor.py:595-670`) derives duration from the timer with a 10 h cap and manual override (`outdoor_log.py:149-190`), writes the `outdoor.v2` JSONL, deletes the active session, then closes the loop on the plan best-effort via `_sync_plan_after_outdoor_log` (`outdoor.py:42-160`). That function is careful and correct: subscription-gated at the choke point (B334), paused-plan aware, past-week aware, idempotent bookkeeping (B277).

**Load score (B327).** `avg_intensity × volume_factor`, both over *attempts* (`outdoor_log.py:94-134`). Duration removed, correctly.

#### F4 — the engine cannot feel a day on the rock **(degrades)**

37 real logged sessions from prod, scored with the current formula:

| | |
|---|---|
| Sessions | 37 (2026-03-15 → 2026-08-15) |
| Load range | **0 – 33** |
| Max ever | **33** (2026-08-08, 6 routes / 8 attempts) |
| Three consecutive 8-hour multi-pitch days (12–14 Aug) | **23, 23, 23** |
| `OUTDOOR_RIPPLE_THRESHOLD` | **65** (`replanner_v1.py:130`, applied at `:1184`) |

**The ripple has never fired, and cannot.** Synthetic worst cases: 4 burns on an 8a → **35**; the same day plus three warm-up routes → **36**; a ten-route mixed day → **39**; twelve onsight attempts *all at 8a* → **53**. To reach 65 you need sustained 8b volume. Meanwhile an indoor session sums `fatigue_cost × 1.5` toward the same 85 cap and routinely clears 65 — so the D151/B327 claim that the two scales are "comparable" does not hold in the range this athlete lives in. The arithmetic reason is structural: `avg_intensity` is a **mean**, so warming up correctly *dilutes* your own day.

And the ripple is only one of four blind spots:

| Guard | file:line | Sees outdoor? |
|---|---|---|
| Next-day ripple | `replanner_v1.py:1184` | Yes, but the threshold is unreachable |
| 48 h finger gap | `replanner_v1.py:900-960` | **No** — scans `day["sessions"]` with `tags.finger`; an outdoor day has no sessions |
| Hard-day cap | `_enforce_caps`, `replanner_v1.py:963-975` | **No** |
| `fatigue_proxy` | `closed_loop_v1.py:52-58, 117-139` | **No** — and it is `{}` in prod after five months (written only from `feedback.py:221`, i.e. gym sessions) |
| `progression_v1` | — | **No** — zero occurrences of "outdoor" |

**What the app tells you about tomorrow: nothing.** The ripple would be the mechanism, and it never triggers.

---

### 1.6 Rest day on the trip

The app cannot tell a trip rest day from a training rest day. `day-card.tsx:775` renders the generic empty state for any day with no sessions, no outdoor and no free session.

**Can it suggest something harmful?** Yes, and specifically the thing you must not do. Quick-add on day 4 of the trip: `_enforce_no_consecutive_finger` seeds from `day["sessions"]` only, so **three consecutive tufa days do not anchor the finger gap** and a hangboard quick-add sails through unchallenged (F4). The engine has no basis to object, because it does not know you have been climbing.

---

### 1.7 Coach during the trip

This is the strongest part of the stack. After B328 the coach sees, per outdoor day: date, discipline, crag, `day_type`, **per-route sends and falls with repeat counts**, total attempts over total routes, an explicit `(+N more routes not shown)` marker at 12, free-text notes, and duration labelled *self-reported, not a density signal* (`backend/coach/prompt_builder.py:453-530`). It sees the current week plan with outdoor days and `pretrip_deload` markers (`:327-349`), the trip itself (`:298-303`), an explicit *"this outdoor day IS today's main session — never tell the user today is a rest day"* (`:421-425`), and can call `get_weather` on demand (A244).

So *"should I try the 8a again today or go onsight?"* is answerable from real data — attempts, falls, the last three days.

Three real gaps:

- **It cannot find the crag.** `get_weather("projecting")` → `geocode_place` returns `None` → *"couldn't find a location matching 'projecting'"* (`weather_tool.py:110-114`). Consequence of F5.
- **It never sees `day.outdoor_plan`.** The pitch ladder is not in `_day_extras`, so the coach cannot reason about the plan the athlete is following.
- **Its weather answers inherit F1.** The tool formats `best_window` verbatim (`weather_tool.py:81-87`), so the coach will repeat "best window 15:00–18:00" in its own voice.

Rate limit 30 msg/day — ample for a trip.

---

### 1.8 Return home

- **Recovery days after the trip:** not implemented. `docs/DESIGN_GOAL_MACROCICLO_v1.1.md:261` promises *"Trip lungo (3+ giorni): deload pre-trip + recovery post-trip"*. Grep for `post_trip` / `posttrip` in `backend/`: **nothing**. Code/design divergence, explicit.
- **Macrocycle resumption:** the cycle simply ends on 2026-09-06 (its `end_date` coincides with the trip's). Next step is a manual `start-new-cycle`.
- **Pollution or enrichment:** neither. Outdoor data does not reach `assessment_v1` or `progression_v1`. Sends do not update `performance.current_level` — that field was last touched by hand on 2026-08-01.
- **Where outdoor sends *are* visible:** `/outdoor` (history, stats, per-spot, grade histogram), the weekly and monthly reports (`report_engine.py:196-206, 281, 484-537`), the rest-positive heatmap (`:1180-1196`), and milestones — `first_outdoor_session`, `first_onsight_outdoor`, 3/5-spot unlocks and **per-discipline PB sent / PB onsight** (`milestones_v1.py:325-341`). A Kalymnos PB will be celebrated. It will not change a single prescription.

---

## 2. Invariants

### 2.1 Past sessions immutable — **holds**

| Guarantee | file:line |
|---|---|
| Past weeks are served read-only from the archive; `force` is ignored | `backend/api/routers/week.py:325-336` |
| Days before `preserve_before` copied wholesale, exact-date only (B287/R-4 forbids the weekday fallback) | `replanner_v1.py:618-640` |
| Today with a completed session **or** `outdoor_session_status == "done"` copied wholesale | `replanner_v1.py:654-663`, `:765-773` |
| An outdoor override refuses to clear done/skipped sessions | `replanner_v1.py:1738-1747` |
| `set_outdoor_plan` refuses to touch a completed outdoor day | `replanner_v1.py:1247-1248` |
| `remove_outdoor` refuses a completed outdoor session | `replanner_v1.py:1262-1263` |
| `_sync_plan_after_outdoor_log` bails on a past week | `outdoor.py:89-91` |
| Ladder card is read-only once done | `day-card.tsx:620` |
| B277 bookkeeping dedupe — one entry per date, re-logs idempotent | `outdoor.py:146-155` |

No outdoor operation rewrites a completed session or a persisted `load_score`.

### 2.2 Equipment-based filtering, not location — **holds**

`location_type` does not exist in `backend/` (grep: zero hits outside tests). The vocabulary is `location_allowed` on exercises and `required_equipment` on sessions (`resolve_session.py:468-512`). Outdoor days are excluded from session assignment by *availability* (`planner_v2.py:830-841`), which is a different axis and legitimate — the planner is deciding whether a slot is occupied, not filtering a session.

### 2.3 Day-level fields surviving regeneration — **one gap, latent**

`_DAY_LEVEL_FIELDS` (`replanner_v1.py:706-721`) carries `outdoor_spot_name`, `outdoor_spot_id`, `outdoor_discipline`, `outdoor_session_status`, `outdoor_plan` — but **not `outdoor_load_score`**, which `complete_outdoor` writes at `:1183` and the heatmap reads at `report_engine.py:1184`.

Reproduced:

```
past day  (wholesale copy) → outdoor_load_score: 72   ✓
future-side (field merge)  → outdoor_load_score: None ✗  (status still "done")
```

**Currently unreachable in production**, because every path that carries a *done* outdoor day goes through a wholesale copy: past weeks are archive-read-only, and today-with-outdoor-done is copied whole. It is one wholesale-copy guard away from becoming the B276/D263 failure mode again. One line, no behaviour change today, worth taking.

---

## 3. Kalymnos: is a sector catalog worth building?

### 3.1 What the research says

August on Kalymnos: highs ~31–32 °C, lows ~22–24 °C, humidity ~59 %, **zero rain days**, 11 h of sun ([climate-data.org](https://en.climate-data.org/europe/greece/kalymnos/kalymnos-717906/), [holiday-weather](https://www.holiday-weather.com/kalymnos/averages/august/), [climatestotravel](https://www.climatestotravel.com/climate/greece/kalymnos)).

Two consequences, and they decide the whole section:

1. **Weather has almost no information content on this trip.** It will not rain. Temperature and humidity vary within a narrow band day to day. A forecast that says "hot and dry" ten mornings running is not a decision input.
2. **The entire decision is aspect and clock.** The local strategy is well documented and universal: climb in the shade before ~11:00, long lunch and a swim, climb again in shade after ~16:00 ([Unlevel Edge](https://unlevel-edge.com/blogs/climbing-blog/kalymnos-climbing-the-ultimate-sport-climbing-trip-planner-seasons-sectors-logistics-gear), [UKC](https://www.ukclimbing.com/forums/destinations/kalymnos_-_any_point_in_august-435794)).

And "when does the sun arrive" is **published, per sector, as a single number**. Extract, sources cited:

| Sector | Sun arrives / shade | Grades | Routes | Source |
|---|---|---|---|---|
| **Sikati Cave** | shade **all day** (N-facing hole, 45 min approach + abseil) | 7a–8c | 30 | [climbapedia](https://climbapedia.org/content/kalymnos-sikati-cave) |
| **Secret Garden** | shade **all day** | 6b–8a | 50 | [climbapedia](https://climbapedia.org/region/greece-kalymnos?type=All&page=1) |
| **Local Freezer** | shade **all day** | 6b+–8b | 20 | climbapedia |
| **Griffig** | "almost never" sunny | 5a–8c | 40 | climbapedia |
| **E.T.** | shaded most of day | 6a–8b | 30 | climbapedia |
| **Summertime** | shade from ~11:00 into the evening | 4c–8a+ | ~20 | [Climb Kalymnos](https://climbkalymnos.com/new-routes-at-sector-summertime/) |
| **Black Buddha** | shade 10:00–16:00, N-facing, 25 min | ~6a | — | [Climb Kalymnos](https://climbkalymnos.com/arginonta-valley-and-black-buddha-two-new-sectors-for-climbing-on-hot-days/) |
| **Arginonta Valley** | shade from 11:30–12:30 to end of day, N-facing, 5 min | 5b–7a+ | 60 | same |
| **Spartan Wall / Afternoon** | sun after **16:00** | 4c–8c | 30 | climbapedia, [PlanetMountain](https://www.planetmountain.com/en/crags/kalymnos-grande-grotta.html) |
| **Spartacus** | sun **late afternoon (~18:00)**, +15 min from Grande Grotta | 6a–8a | 50 | climbapedia, PlanetMountain |
| **Iannis** | sun 13:00 (slabs) / 15:00 (cave) | to 8b+ | 30 | climbapedia |
| **Ghost Kitchen** | sun after 13:00 (left), ~14:00–16:00 (west part) | varied | 30 | climbapedia |
| **Odyssey** | sun after **~14:00** | 4b–9a | 50 | climbapedia |
| **Panorama** | sun after 13:30 | 6b–8c | 50 | climbapedia |
| **Poets** | sun after 13:00 | all grades | 100 | climbapedia |
| **Stankill / Ivory Tower** | sun 13:00–15:30 | 5a–8a | 50 | climbapedia |
| **Kalydna** | sun after 14:00 | — | 50 | climbapedia |
| **Olympic Wall** | sun after 13:30 | — | 40 | climbapedia |
| **Jurassic Park** | shade until 11:00 or 15:00 depending on side | 6b–8b+ | 30 | [theCrag](https://www.thecrag.com/en/climbing/greece/kalymnos/armeos/area/14190529) via search |
| **Grande Grotta** | sun early afternoon (spring/autumn), later in summer | 7a–8b+ | 50 | [climbapedia](https://climbapedia.org/content/kalymnos-grande-grotta) |
| **Arhi** | sun after ~10:00 | 5a–9a | 50 | climbapedia |
| **Arginonta** | sun after midday | 4c–7c | 70 | climbapedia |

Caveats to carry into any catalog: these are **published hours, not measured** — some are stated by the source, some are the source's own inference from orientation, and climbapedia's column mixes "sun from" with "shade all day". Every row must carry `source` and `inferred: true|false`. GPS is *not* on these pages; coordinates would have to come from the guidebook or be dropped.

### 3.2 Is friction + orientation enough?

**Yes for the decision that matters, no via the current friction score.** Orientation + local clock alone answers *"Odyssey now, Spartacus after 16:00"* with no network at all. Adding the friction score as currently implemented makes it **worse**, not better, because of F1 — it will rank the sunny afternoon above the shady morning. Rock temperature would be the honest physical input and is not obtainable from a free API; wind exposure is real on Kalymnos (the meltemi) but is a per-sector qualitative note, not a metric.

So the right coupling is: **sector shade window as the primary signal; weather demoted to a secondary sanity check, and only after F1 is fixed.**

### 3.3 What the existing apps do — and what not to copy

27crags, theCrag, Vertical-Life and Rockfax are all fundamentally **route databases with community tick-lists**: topos, route-level comments, grade voting, ascent feeds, sends. Rockfax adds curated aspect/season icons per crag; 27crags and theCrag carry a crag-level orientation field, sparsely populated by users. None of them do anything with it — it is a display attribute, not an input to a decision.

**Do not replicate**: route databases (thousands of rows, permanently stale, and a licensing problem against published guidebooks), topos (image rights), community logs and ascent feeds (a social product for an app with one user), or grade-voting. climb-agent has no advantage there and every one of those is a maintenance liability.

**Worth borrowing, conceptually**: exactly one field the incumbents already collect and *waste* — crag aspect / shade window — turned into an actual decision. That is a genuine differentiator, and it is small.

### 3.4 Recommendation — **BUILD MINIMAL, after the trip**

A ~20-row static JSON, no coordinates, no routes, no topos. Not before departure: the pre-departure hours are better spent on F1, and the field data from the trip will tell us whether the published hours are right — which is the whole point of §4.3.

**Location.** `backend/catalog/outdoor/v1/sectors.json`, beside `strategy.json` and `nutrition.json`. Arguments: it is catalog data, not user data (`CLAUDE.md`: *"Sessions, exercises, and templates are JSON catalogs — logic is separate from data"*); `outdoor_resolver.py:29-31` already loads that directory; and it must **not** live in `user_state` — user spots are per-user and mutable, sectors are shared, versioned facts. The user's spot links to it by `sector_id`, one optional field.

**Schema.**

```jsonc
{
  "catalog_version": "outdoor_sectors.v1",
  "areas": {
    "kalymnos": {
      "name": "Kalymnos / Telendos",
      "timezone": "Europe/Athens",
      "lat": 36.95, "lon": 26.98,          // area centroid, for weather only
      "season_note": "August: shade before 11:00 and after 16:00. No rain.",
      "sectors": [
        {
          "id": "kalymnos_spartacus",
          "name": "Spartacus",
          "aspect": "W",                    // 8-point compass, null when unknown
          "sun_from": "18:00",              // local; null = shaded all day
          "sun_to": null,                   // sunset when null
          "shade_all_day": false,
          "approach_min": 35,
          "style": ["tufa", "overhang"],
          "grade_min": "6a", "grade_max": "8a",   // French, always
          "route_count": 50,
          "notes": "15 min further than Grande Grotta. Big cave, steep.",
          "source": "climbapedia.org/region/greece-kalymnos; planetmountain.com",
          "inferred": false                 // true = derived from aspect, not stated
        }
      ]
    }
  }
}
```

**How it plugs in, without touching a single high-risk module.**

1. **Read-only endpoint** `GET /api/outdoor/sectors?area=kalymnos&at=HH:MM` → sectors sorted by "in shade now / in shade in N hours", each with its window. Pure function over the catalog + a clock. No planner, no replanner, no resolver, no `resolve_session`.
2. **`condition_band` gains one honest input.** If the chosen sector is in shade, do not let the day be classified `poor_hot_humid` on air temperature alone — a shaded north-facing cave at 32 °C is not the same day as a sunny west wall at 32 °C. This is a **strategy-layer** change (`outdoor_resolver.py` dimensions), not a weather-engine one.
3. **Coach.** One extra line in `_day_extras` and one optional `sector` argument on `get_weather`, so *"where should I go this afternoon?"* is answered from the catalog rather than guessed.
4. **Growth / cleanup.** Catalog file, versioned in git, ~15 KB. Nothing persisted per user except an optional `sector_id` string on an existing spot — no growth, nothing to clean up.

**Explicitly out of v1:** coordinates per sector, route lists, topos, crowd data, any second area. Kalymnos only, because Kalymnos is the trip.

---

## 4. Findings and proposals

### 4.1 Friction points, ranked by pain per day on the trip

| # | Severity | Finding | Evidence | The Kalymnos morning, with vs without |
|---|---|---|---|---|
| **1** | **Blocks** | Friction score inverts above 26 °C; `best_window` recommends the hottest hour | `weather_v1.py:47, 89-144`; `weather.py:217-278` | **With:** 07:00, card says "ok, 43" and "best window 15:00–18:00, good". You either follow it into 34 °C sun or stop trusting the card on day 1. **Without:** the card agrees with what your skin already knows and the strategy nudge flips to `poor_hot_humid` → "downgrade, seek shade". |
| **2** | **Blocks** | Pre-trip deload filter only in planner pass 1 | `planner_v2.py:940-942` vs `:1577`; reproduced on real state → `finger_strength_home` (hard, `high`) on 2026-08-18 flagged `pretrip_deload` | **With:** hard hangboard 48 h before the flight, or (today's actual state) a stale plan that quietly becomes that the moment anything regenerates the week. **Without:** the departure week tapers as designed. |
| **3** | **Blocks** | Timed outdoor session has no offline path; live routes are never persisted locally | `outdoor/[date]/page.tsx:140-166, 372`; `OutdoorLogForm.tsx:196-214`; `outbox.ts:34` | **With:** Sikati Cave, no signal — you cannot start the session; if the phone dies mid-day the log is gone; at 19:00 "Finish & save" fails with no queue. **Without:** the day survives in localStorage and syncs at the taverna. |
| **4** | Degrades | Outdoor is invisible to every fatigue guard (ripple unreachable, no finger anchor, no cap, no proxy) | `replanner_v1.py:130, 900-975, 1184`; `closed_loop_v1.py:52-58`; prod max load 33/37 sessions | **With:** day 4, three tufa days in the legs, the app happily quick-adds a hangboard and says nothing about tomorrow. **Without:** the plan bends around the rock. |
| **5** | Degrades | `outdoor_spot_name` = replanner intent name | `replanner_v1.py:1749`; prod plan shows `"projecting"`, `"volume"`, `"easy"` | **With:** ten days of a card reading "projecting", and the coach answering "couldn't find a location matching 'projecting'". **Without:** "Grande Grotta", and weather that resolves. |
| **6** | Degrades | Pitch ladder absent from `/outdoor/[date]` although the API returns it there | `outdoor.py:431-441` vs `outdoor/[date]/page.tsx` (no `pitch_ladder`) | **With:** at the base of the route you have prose, not grades; the ladder is on a screen you left behind. **Without:** the day's grades and rests are on the screen you are already holding. |
| **7** | Degrades | No sector / aspect / shade data at all | `models.py:209-215`; `outdoor.py:184-193`; `weather_v1.py:24-25` | **With:** the app has no opinion on the one question you ask every morning. **Without:** "Odyssey now, Spartacus after 16:00." |
| **8** | Degrades | No trip concept beyond a 5-day pre-window; `end_date` unread; post-trip recovery designed, not implemented | `macrocycle_v1.py:570-589, 862-890`; `DESIGN_GOAL_MACROCICLO_v1.1.md:261` | **With:** ~20 taps of weekly overrides before leaving (already paid) and nothing on return. **Without:** one declaration; a recovery block on 07 Sep. |
| **9** | Cosmetic | `outdoor_load_score` missing from `_DAY_LEVEL_FIELDS` | `replanner_v1.py:706-721`; reproduced | Latent. Today masked by the wholesale-copy guards; one guard change from a silent heatmap regression. |
| **10** | Cosmetic | Forecast represents the day by its **midday** step | `weather.py:128-143` | The single worst hour stands in for a day nobody climbs at noon. |

### 4.2 Proposed briefs

#### Before departure — by 2026-08-19 evening

| ID | Type | Title | Scope | Modules | STOP gate | Size |
|---|---|---|---|---|---|---|
| **B335** | B | Friction score must not reward heat above 26 °C | Cap the band by air temperature (≥28 °C → at most `ok`; ≥32 °C → `poor`), so `catalog_condition_band` selects `poor_hot_humid` and the strategy nudge fires. Forbid `best_window` from proposing a window materially hotter than now. Reconcile headline and limiter suffix. Tests: the Kalymnos table in §1.2 becomes monotonic in temperature. | `backend/engine/weather_v1.py`, `backend/api/routers/weather.py` | **No** | **S** |
| **B335** | B | Never persist live outdoor routes only in memory | Mirror `liveRoutes` to localStorage on every change (key scoped like the outbox); restore from local **and** server on mount, newest wins; on a failed `finish`, fall back to the `outdoor_log` outbox kind instead of erroring. Also: allow **Start session** when the strategy call fails (strategy is advice, not a precondition). | `frontend/src/app/(main)/outdoor/[date]/page.tsx`, `components/training/OutdoorLogForm.tsx`, `lib/outbox.ts` | No (frontend → **branch + Vercel preview + explicit OK**) | **S/M** |

Both are S-sized and Sonnet-implementable. **B335 is backend-only** — direct push to main, live on Railway in two minutes, no preview cycle. **B335 touches `frontend/`** and therefore needs the branch + preview + approval loop; it fits one evening only if that loop starts on the 18th.

Deliberately **not** before departure: anything touching `planner_v2` or `replanner_v1`. Those need the Phase-1 → STOP → Phase-2 protocol, and rushing a STOP-gate module 48 h before the athlete's plan matters most is the wrong trade. For B335 there is a zero-code mitigation: **do not force-regenerate the week of 2026-08-17.** The cached plan is already trip-shaped and carries no hard session on the 18th.

#### After the trip, in order

| ID | Type | Title | Scope | Modules | STOP gate | Size |
|---|---|---|---|---|---|---|
| **B335** | B | Pre-trip deload must apply to every planner pass | `pretrip_set` is consulted in pass 1 only; passes 2, 2.6 and 3 place hard/finger sessions on deload days. Lift the check into the shared placement gate. Regression: Daniele's 2026-08-17 state must produce no `hard` session on 08-18. | `planner_v2.py` | **YES** | S |
| **A275** | A | Outdoor days feed the fatigue guards | Recalibrate `OUTDOOR_RIPPLE_THRESHOLD` against the real distribution (37 sessions, 0–33) — or replace the absolute grade weight with one relative to the athlete's max (the open `B-OUTDOOR-RELATIVE-LOAD`). Make a completed outdoor day anchor the 48 h finger gap and count toward the hard-day cap. | `replanner_v1.py`, `outdoor_log.py` | **YES** | M |
| **B335** | B | Outdoor override must carry a real crag name | `apply_day_override` writes the intent as the spot name. Take an optional `spot_id`/`spot_name`, fall back to the intent only when nothing is supplied, and keep the intent as the day_type seed for the ladder. Backfill nothing — past days are immutable. | `replanner_v1.py` (+ replan dialog) | **YES** | S |
| **A275** | A | Pitch ladder on the outdoor day page | Render `strategy.pitch_ladder` in `/outdoor/[date]`, and tick pitches off against the live logger so the ladder is a checklist, not a printout. | frontend only | No | S |
| **C269** | C | `sectors.json` v1 — Kalymnos, ~20 sectors | The catalog of §3.4, seeded from the table above, every row sourced and `inferred`-flagged, revised with the trip's field notes. | new catalog file | No | S |
| **A275** | A | "Where to climb now" from the sector catalog | Read-only `GET /api/outdoor/sectors`, sorted by shade at the current local time; surfaced on the outdoor day page. Feeds `condition_band` at the strategy layer only. | new router + `outdoor_resolver.py` | No | M |
| **A275** | A | A trip is one declaration | `trips[].end_date` marks the span outdoor, suppresses gym scheduling without 20 weekly-override taps, and schedules a post-trip recovery block per design §7.2. | `macrocycle_v1.py`, `week.py`, weekly-override | **YES** | L |
| **B335** | B | `outdoor_load_score` into `_DAY_LEVEL_FIELDS` | One line + a regression test for the field-merge path. | `replanner_v1.py` | **YES** (trivial change, gate is the module) | XS |
| **B335** | B | Forecast should not represent the day by its midday step | Return the day's shade-relevant windows, not the 12:00 sample. | `weather.py` | No | S |

#### Explicitly not worth doing

| Not doing | Why |
|---|---|
| **A sector catalog for anywhere but Kalymnos** | 20 rows is a weekend for one area; 500 rows is a data product with no maintainer. Build one, use it for ten days, then decide. |
| **Route database / topos / community ticks** | 27crags and theCrag do this properly and legally. Copying it is a licensing problem, a permanent staleness problem, and a social feature for a single-user app. |
| **Rock-temperature modelling** | The honest input, and unobtainable: it needs solar irradiance, albedo, thermal mass and shading geometry per sector. Sector aspect + clock captures ~90 % of the decision for ~1 % of the effort. |
| **A boulder pitch ladder** | `build_pitch_ladder` returns `None` for boulder on purpose — the strategy catalog has no boulder entry. Kalymnos is lead. Leave the honest `None`. |
| **Feeding outdoor sends into `progression_v1` / `assessment_v1`** | Tempting and premature. Outdoor grades are not comparable to gym loads; wiring them into working-load progression risks corrupting the one closed loop that works. Make the *fatigue* guards see outdoor (A275) first; leave *progression* alone. |
| **Pausing the phase clock during the trip** | A223 pause/resume already exists and is idempotent. It is a user action, not something to infer from `trips[]`. If the athlete wants the clock stopped, he taps pause. |
| **A "trip mode" UI** | The value is in the engine seeing the trip, not in a new screen. Ship A275's behaviour before any chrome. |

### 4.3 Field-test protocol

**Every climbing morning (2 min, before leaving):**
1. Open `/today`. Read the weather card: note **band, score, and whether a best_window is offered**.
2. Open the outdoor day → note the strategy `condition_band` nudge and whether it matches reality.
3. If the ladder is set, glance at it. If not, generate it (day type: `project` / `onsight_flash` / `volume` / `scout_easy`).

**At the crag:** start the session with the timer. Log every burn, including falls — the falls are what make `sent`/`fell` worth anything downstream.

**Every evening (1 min):** finish the session. Note the load score the app returns.

**Note format** — one line, in the outdoor session `notes` field (it reaches the coach verbatim, capped at 200 chars) or in a phone note:

```
D<n> | <sector> | <shade: yes/no, hh:mm> | app said <band>/<score> | felt <prime|ok|poor> | <one clause>
```

e.g. `D3 | Spartacus | shade until 18:00 | app said good/70 | felt poor | 34C, skin gone by 11`

**Five hypotheses this trip should confirm or kill:**

| # | Hypothesis | Kill criterion |
|---|---|---|
| H1 | The friction score is not merely noisy above 28 °C — it is **anti-correlated** with how the day actually feels. | On ≥7 days, the app's band shows no relationship (or an inverted one) to the "felt" column. |
| H2 | `best_window` never proposes a *usable* window, because on Kalymnos conditions only worsen after breakfast. | 10 days of morning checks: count how often a window is offered and how often it is one you would act on. Expect 0. |
| H3 | The pitch ladder's **attempt counts are wrong for project days** — 3 burns on an 8a+ is what the catalog says, not what the day gives. | Log the actual burn count on every project day. If it is consistently 4–6, the template is under-prescribing. |
| H4 | The load score is **flat across effort**: a maximal project day and an easy volume day land within ~10 points. | If max-day and easy-day loads differ by <10 across the trip, the formula does not discriminate and A275 is confirmed. |
| H5 | Sector shade window, not weather, is the decision — the app could have chosen the crag from a static table plus the clock. | Record every morning which sector you picked **and why**. If the reason is "shade" ≥8 times out of 10, C269 + A275 are justified and the weather work is secondary. |

Also worth capturing, cheaply: whether the timed session ever fails offline (F3) and at which sectors, and whether the "projecting"/"volume" card names ever cause a wrong tap.

### 4.4 Open questions for the author

1. **Trip length.** The brief says ~10 days from 2026-08-20. Production says `end_date: 2026-09-06` — 18 days — and outdoor days are already laid out through 09-06. Which is real? It changes nothing in §4.2 but everything about how much the post-trip recovery gap (F8) costs.
2. **The macrocycle ends on the last day of the trip** (`end_date: 2026-09-06`, goal deadline 2026-10-24). Deliberate, or a coincidence that will hand you an expired plan on the flight home? If deliberate, the return-home brief is "start new cycle", not "recovery block".
3. **Is `performance.current_level.sport` (onsight 7a+, worked 8a+) current?** It was last written 2026-08-01 by hand. The whole pitch ladder is derived from it; if the onsight is really 7b, every ladder is one grade low for ten days.
4. **B335 before departure: yes or no?** It needs a frontend branch, a Vercel preview and your explicit OK on an installed iPhone PWA. Worth an evening on the 18th, or do you accept the offline risk and log on paper at Sikati?
5. **How much of the trip do you want to log at all?** The whole audit assumes the app is the daily companion. If the honest answer is "I log in the evening from the taverna", F3 drops from *blocks* to *cosmetic* and B335 leaves the pre-departure list.

---

## Appendix — verification runs

All figures above were produced by executing the real modules against the real production state, not by reading them:

- `compute_friction_score` / `friction_components` / `band_headline` over the §1.2 Kalymnos table.
- `compute_outdoor_load_score` over all **37** production outdoor logs (`outdoor_logs` table, read-only) and over synthetic 8a project / 10-route / 12-attempt days.
- `merge_prev_week_sessions` with a done outdoor day, both branches, for §2.3.
- `generate_phase_week` with Daniele's real `availability` merged with his real `weekly_overrides` for 2026-08-17 / 08-24 / 08-31, plus live `compute_pretrip_dates` — which is how F2 was found (`explain: ["phase=performance","slot=evening","day=tue","pass2.6:pulling_maintenance"]` on a `pretrip_deload: True` day).
- `build_pitch_ladder` with onsight 7a+ / worked 8a+.

Prod reads were `SELECT`-only via the Supabase REST API. Nothing was written.
