<!--
MAINTENANCE: This guide must stay in sync with the app.
After any feature or bugfix that changes user-facing behavior,
update the relevant section in the same commit.
Last verified: 2026-03-24 at 1335 tests.
-->

# climb-agent — User Guide

> Your personal climbing training engine. No guesswork, no bro-science — just a structured, evidence-based plan that adapts to you.

---

## Table of Contents

1. [How the Plan Works](#1-how-the-plan-works)
2. [The Macrocycle: What to Expect in Each Phase](#2-the-macrocycle-what-to-expect-in-each-phase)
3. [Your Weekly Routine](#3-your-weekly-routine)
4. [The Guided Session](#4-the-guided-session)
5. [Giving Feedback](#5-giving-feedback)
6. [Test Sessions](#6-test-sessions)
7. [Regenerating Your Plan](#7-regenerating-your-plan)
8. [Modifying a Session](#8-modifying-a-session)
9. [Adding Extra Sessions (Quick-Add & Supplementary)](#9-adding-extra-sessions)
10. [Replanning Your Week](#10-replanning-your-week)
11. [Free Sessions](#11-free-sessions)
12. [Confirming Next Week's Availability](#12-confirming-next-weeks-availability)
13. [Locations & Equipment](#13-locations--equipment)
14. [Outdoor Sessions](#14-outdoor-sessions)
15. [Weekly Report](#15-weekly-report)
16. [Tabata Timer](#16-tabata-timer)
16b. [The Coach (AI Chat)](#16b-the-coach-ai-chat)
17. [Don't Overtrain — Trust the Process](#17-dont-overtrain--trust-the-process)
18. [Backup & Recovery](#18-backup--recovery)
19. [Need Help?](#19-need-help)

---

## 1. How the Plan Works

climb-agent builds your training plan through a pipeline:

**Assessment → Goal → Macrocycle → Weekly Plan → Session → Exercises**

1. **Assessment**: During onboarding, you provide your climbing experience, grades, test results, and self-reported weaknesses. This generates a 5-axis profile (finger strength, pulling strength, power endurance, technique, endurance) scored 0–100.

2. **Goal**: You set a target grade (Fontainebleau) and a deadline. The engine calculates how many weeks you have and what needs to improve.

3. **Macrocycle**: A periodized plan (typically 10–13 weeks, minimum 9) is generated, divided into phases. Each phase has a specific physiological purpose. The plan is tailored to your weaknesses — if your finger strength is low relative to your goal, the plan allocates more time and intensity to finger training.

4. **Weekly Plan**: Each week, the planner selects sessions based on your current phase, available days, locations, and equipment. It runs a 3-pass algorithm: primary sessions first, then complementary work, then tests when due.

5. **Session Resolution**: Each session is resolved into concrete exercises with sets, reps, load, rest times, and tempo — all calculated from your current working loads and progression state.

6. **Feedback Loop**: After each session, your feedback drives the closed-loop adaptation system. Loads adjust up or down based on how the session felt. Every ~6 weeks, test sessions re-assess your profile and the plan recalibrates.

**This is fully deterministic.** Same inputs always produce the same outputs. No randomness, no AI guessing — just rules, catalogs, and your data.

---

## 2. The Macrocycle: What to Expect in Each Phase

Your macrocycle follows the Hörst 4-3-2-1 periodization model. Each phase builds on the previous one. **Trust the progression** — it's designed this way for a reason.

### Base / Endurance (4–6 weeks)

**What you'll do**: ARC (Aerobic Restoration and Capillarity) training, easy sustained climbing, repeaters, technique drills, general conditioning.

**What it feels like**: Easy. You'll think "this is too easy, I should be projecting." That's normal. This phase builds the aerobic base that everything else depends on. Capillary growth in your forearms takes a minimum of 6 weeks of sustained low-intensity work.

**Don't**: Push hard, add extra bouldering at your limit, or skip sessions because they feel easy.

### Strength & Power (2–3 weeks)

**What you'll do**: Max hangs, weighted pull-ups, limit bouldering, campus work (if qualified), power exercises.

**What it feels like**: Hard. Low reps, long rests, high intensity. Sessions are shorter but more demanding neurally. You should feel strong on the wall but not pumped.

**Don't**: Add volume. Long rest periods are not wasted time — your nervous system needs them.

### Power Endurance (2–3 weeks)

**What you'll do**: 4×4 intervals, linked boulders, route intervals, PE circuits. The pump is back.

**What it feels like**: The hardest phase. High intensity AND high volume. You'll feel tired. That's the point — this phase teaches your body to perform while fatigued.

**Don't**: Skip rest days. Recovery between sessions is critical in this phase.

### Performance (2 weeks)

**What you'll do**: Reduced volume, maintained intensity. Projecting, route practice, quality climbing.

**What it feels like**: You're tapering. Volume drops 40–60%, but intensity stays high. Your body is consolidating all the gains from previous phases. This is where you send.

**Don't**: Panic about the reduced volume. Less is more in this phase.

### Deload (1 week)

**What you'll do**: Easy climbing, stretching, light movement. Active recovery.

**What it feels like**: A break. Enjoy it. Your body is recovering and supercompensating.

**Don't**: "Just do a quick session" at full intensity. Deload means deload.

---

## 3. Your Weekly Routine

Every week runs **Monday to Sunday**. The planner assigns sessions to the days you're available, respecting your locations and equipment.

**The Today page** shows what's planned for today. **The Week page** shows the full 7-day grid with all sessions. You can navigate to other weeks with the **Previous / Next** buttons.

Past weeks are **locked**: they stay exactly as you trained them and are never regenerated. If you navigate back to a week you never opened (so it has no saved plan), the app shows "This week is in the past" rather than inventing a plan after the fact. When your macrocycle has ended, Today shows "Your training plan has ended" with a prompt to **Plan your next cycle**.

At the top of **Today** you'll see a **Today's focus** banner — a short coaching cue for one of the day's sessions (e.g., "Squeeze every rep with maximal intent"). It's there to read before you start training; once all of the day's sessions are done or skipped, the banner disappears.

Your daily workflow:

1. Open the app → **Today** shows your session(s)
2. Tap a session to see the full exercise list with loads
3. Start the **Guided Session** for step-by-step coaching, or train independently
4. When done, tap **Done** and give feedback
5. If you can't train, tap **Skip** — the system adapts

**Done** and **Skip** are always reversible — tap **Undo completion** (to reverse Done) or **Undo skip** (to reverse Skip) — don't worry about misclicks.

---

## 4. The Guided Session

The guided session is your in-gym companion. It walks you through every exercise step by step.

**How it works:**

- Each exercise is displayed one at a time with its full prescription: sets, reps, load, rest, grip type, tempo
- **Timers** count down rest periods, hang times, and work intervals automatically
- **Beeps** alert you at 3-2-1 before each work phase starts
- **Voice cues** provide encouragement and phase transitions
- A **process cue** banner reminds you what to focus on today (e.g., "Place every foot so silently that no sound is audible")
- On the **Plan** page, each phase has an expandable "About this phase" section explaining *why* you're in this phase and what to expect

**iOS Safari note**: The timer uses a wall-clock engine specifically designed to survive Safari background suspension. If you switch apps briefly, the timer stays accurate. Audio cues require one initial tap to activate (iOS requirement).

**You can always**:
- Skip an exercise within the guided session
- Adjust the weight/load if the prescribed load isn't available
- Exit the guided session and mark the session manually

---

## 5. Giving Feedback

After completing a session, you're asked for feedback on each exercise:

- **Very Easy** — Could do much more
- **Easy** — Comfortable, could add load
- **OK** — Appropriate challenge
- **Hard** — Struggled but completed
- **Very Hard** — Barely completed or had to reduce

**This feedback directly drives your progression.** The closed-loop system uses it to adjust loads for next time:

- "Very Easy" or "Easy" → loads increase next session
- "OK" → loads stay the same
- "Hard" → loads stay or decrease slightly
- "Very Hard" → loads decrease

**Be honest.** The system only works if your feedback is accurate. There's no benefit to saying "OK" when it was "Very Hard" — you'll just get a harder session next time that's too much.

---

## 6. Test Sessions

Every **~6 weeks**, the system schedules test sessions. These are critical — they re-measure your baseline numbers and update your 5-axis profile.

**The tests:**

- **Max Hang (7s)**: Maximum weight you can hang for 7 seconds on a 20mm edge. Measures finger max strength.
- **Repeater (7:3 to failure)**: How many reps you can sustain at 60% of your max hang. Measures finger endurance.
- **Weighted Pull-Up (2RM)**: Maximum added weight for 2 reps. The system estimates your 1RM from this. Measures pulling strength.
- **Bodyweight Pull-Up Gate**: If you've never done the weighted test, the system first checks if you can do 15+ bodyweight pull-ups. If yes, you progress to the weighted test.
- **Hip Flexibility**: Straddle measurement in cm. Informs mobility prescription.

If you use a **loading pin** instead of a hangboard, the system automatically substitutes the finger tests with loading pin variants (LP Max 5s and LP Repeater).

**Why they matter**: Without fresh test data, the system keeps using your old baselines. Your loads won't progress accurately, and your plan won't adapt to your real improvements. Tests are not optional extras — they're the system recalibrating itself.

**After a test session**: Your profile radar updates, working loads recalculate, and the remaining macrocycle adjusts its emphasis based on your new strengths and weaknesses.

---

## 7. Regenerating Your Plan

You can regenerate your plan from **Settings**:

- **Edit Profile or Goal**: When you save changes to your profile or goal, the system automatically recomputes your 5-axis assessment and offers to regenerate the macrocycle.
- **Plan Next Cycle**: When your macrocycle is ending or finished, use this to start a fresh cycle. You'll review your goal and deadline, and week 1 will include test sessions to recalibrate. Your training history is preserved — all past sessions, feedback, working loads, and outdoor logs stay intact. The previous macrocycle is archived (visible to support, used for analytics).
- **Restart Macrocycle** (Danger Zone): Creates a new macrocycle from week 1 keeping the existing goal. Use this only if you want to discard the current plan without re-reviewing your goal.

**When to regenerate:**

- After completing all tests and the plan feels misaligned
- After a long break (2+ weeks off)
- When changing your primary goal (new target grade or new deadline)
- When you make significant equipment or location changes

**When NOT to regenerate:**

- After a bad week — the closed-loop adapts automatically
- Mid-phase because you're impatient — give the phase time to work
- Because one session was too easy or too hard — feedback handles this

**Important**: Regenerating creates a new plan. Past sessions are **never modified** — they're immutable history. Only future weeks are affected.

---

## 7b. Pausing & Resuming Your Plan

Going away — travel, illness, a busy stretch? Instead of regenerating, you can **pause** your plan from **Settings**:

- **Pause plan**: Freezes your plan exactly where you are. While paused, Today shows a "Plan paused" card instead of sessions, and Week/Plan show a small "Paused" banner. No new sessions are scheduled.
- **Resume plan**: Picks up exactly where you left off and shifts the remaining weeks forward by however long you were away. Your end date moves out by the same amount.

**How the shift works:**

- The shift is measured in **whole weeks** (Monday to Monday). A short break of **less than a week** resumes in place and does **not** shift the plan.
- You can pause and resume as many times as you need — the shifts add up.
- Your start date never changes, so all your completed history stays exactly where it happened.

**While paused:**

- Replanning, regenerating, adding sessions, and changing weekly availability are turned off until you resume.
- **Free Sessions still work** — log any climbing you do while paused.
- Your subscription and trial are **not** affected by pausing.

**Paused, not missed**: Sessions that fall inside a pause window are counted as *paused* (neutral), never as *missed* — your adherence stats aren't penalised for time you deliberately took off.

---

## 8. Modifying a Session

You can modify a resolved session in several ways:

### Adding an Exercise

From the **Today** or **Week** page, tap a session card's menu to add exercises. The system shows compatible exercises filtered by your equipment and the session's focus. The added exercise gets a prescription calculated from your current working loads.

### Removing an Exercise

Expand a planned session card and tap the trash icon (🗑) next to any exercise to remove it. A confirmation dialog will appear. You cannot remove the last exercise — a session must always have at least one. Completed or skipped sessions cannot be modified.

### Reordering Exercises

Exercises are ordered by the engine for safety and performance (e.g., warmup → main → cooldown). If you want a different order, grab the drag handle (≡) on the left of any exercise and drag it to the desired position. A one-time warning reminds you that the default order is optimized.

### Skipping an Exercise

Within the guided session, you can skip any exercise. If you consistently skip an exercise, your feedback will signal the system to adjust.

### Changing Load

If the prescribed load isn't available (e.g., you don't have the exact weight plate), adjust within the guided session. The system will adapt based on your feedback at the end.

### Session-Level Changes

For bigger changes (wrong session type, wrong day), use the **Replan** feature instead of modifying the session — see [Section 10](#10-replanning-your-week).

---

## 9. Adding Extra Sessions

### Quick-Add (Climbing Sessions)

From the **Today** or **Week** view, tap the **+** button to open the Quick-Add dialog. The system suggests sessions compatible with your current phase and today's location/equipment.

These are full engine sessions — they get resolved with exercises, loads, and prescriptions just like planned sessions. Their load counts toward your weekly total.

### Supplementary Training

The Quick-Add dialog also offers supplementary sessions — non-climbing work you can add any time:

- **Upper Body** — Push/antagonist work (home)
- **Legs (Home)** — Squat/hinge/unilateral
- **Legs (Gym)** — Full leg session with equipment
- **Heavy Conditioning** — Full-body conditioning (gym)
- **Pulling** — Dedicated pulling session (gym)

Supplementary sessions count as an active training day for adherence and their load counts toward your weekly total. They do not trigger replanning or macrocycle adaptation.

### Free Session

You can also add a free session from Quick-Add. See [Section 11](#11-free-sessions).

---

## 10. Replanning Your Week

The **Replan Dialog** lets you make changes to your weekly plan without regenerating everything. Access it from the **Week** view by tapping a day.

**What you can do:**

- **Change location**: Switch a day from home to gym, gym to outdoor, etc.
- **Change intent**: Override what kind of session you want (e.g., strength, endurance, technique, projecting, rest, recovery, power endurance, or "hard" for auto-select)
- **Go outdoor**: Switch to an outdoor intent (easy outdoor, projecting, volume routes, boulder outdoor)
- **Rest**: Set the intent to "Rest" to turn a training day into a rest day

The replanner handles **ripple effects** — when you change a day's intent, it adjusts surrounding days to maintain proper recovery spacing. It uses 8 indoor intents and 4 outdoor intents to handle all scenarios.

**Skipping a session** is always OK. The system is designed for real life. Skipping doesn't break anything — the plan adapts. Don't add make-up sessions to "compensate" — that leads to overtraining.

---

## 11. Free Sessions

Free Sessions let you log unstructured climbing — bouldering, board sessions, or route climbing outside the planned training.

### Surfaces

Six surfaces available: Gym Boulder, Kilter Board, MoonBoard, Other Board, Gym Routes (Lead/Top-rope), and Core Circuit. All surfaces are always shown.

### Two Modes

**Template Mode**: Choose a preset and get structure.
- **Volume** — Many problems at moderate grade, moderate rest
- **Projecting** — Few attempts at your limit, long rest
- **Endurance** — Many easy problems, short rest
- **Technique** — Easy problems, focus on movement quality

Each preset shows a **phase compatibility badge** (recommended / caution / not recommended) so you know what fits your current phase. The system computes a target grade based on your max.

**Free Mode**: Just climb and log. You get a phase-appropriate tip and nothing else.

### Logging Climbs

For each climb, you log: grade (Fontainebleau), status (Flash / Sent / Attempted), and number of attempts. For lead routes, additionally: style (Onsight / Flash / Redpoint / Project) and whether you topped out.

### Context

When you start a Free Session, the system is context-aware:
- **Planned session not done yet**: It asks if you want to replace it (planned session becomes skipped) or add the free session on top
- **Planned session already done**: Automatically tagged as add-on
- **Rest day / no session**: Standalone

### Load

Free sessions generate a load score based on number of climbs, difficulty relative to your max, and send rate. This load feeds into your weekly total — the planner considers it when planning subsequent days.

### Body Part Training

When you need a strength workout instead of climbing, the **Body Part Training** card in Free Sessions lets you build a quick session in three steps:

1. **Equipment** — Bodyweight, Home (uses your configured gear), a specific Gym, or Show All.
2. **Body parts** — Tap the parts you want to train: fingers, forearms, biceps, triceps, shoulders, back, chest, core, legs, glutes, hips. Parts with no matching exercises for your equipment are greyed out. The live counter updates the estimated duration as you select.
3. **Preview & Start** — Review the generated exercises grouped by body part (two exercises per part, with warmup and optional mobility cooldown). "Start now" inserts the session into today's plan and opens the guided runner.

The session uses resolver-light prescriptions (sets, reps, rest, loads from your working loads / hangboard baseline when available). Completion updates your working loads but doesn't drive closed-loop progression — this keeps ad-hoc strength days from skewing the long-term plan.

### Stretching & Mobility

The **Stretching & Mobility** card in Free Sessions works like the Core Circuit: you set the parameters, the app builds and runs the session for you. It draws from a pool of 35 stretches and self-massage releases across 11 body regions, and is designed for post-session and rest-day use — not as a warm-up.

- **Setup** — tap the body regions you want to work on (as many as you like), set the total duration (5–45 min), the pace (Quick / Standard / Deep — how long each hold lasts) and the rest between steps. A live counter shows how many stretches fit your time.
- **Guided flow** — the app picks the stretches (releases first — roll first, stretch second — then holds by priority, balanced across your selected regions) and runs them in a fullscreen auto-advancing timer with sound cues and voice prompts, exactly like the Core Circuit. Per-side stretches sequence left → switch → right automatically. Use the arrows to skip or redo a step, tap anywhere to pause.
- **Forearm protection** — if you still have a climbing session planned today, forearm-flexor stretches are automatically left out of the flow (static finger-flexor stretching can reduce grip strength for up to an hour). The setup screen tells you what was skipped and why.
- **No training load** — mobility sessions are logged in your history but always count as zero load: stretching is recovery, and it will never inflate your weekly load numbers.

---

## 12. Confirming Next Week's Availability

Your default availability (days, locations, time slots) is set in **Settings**. But real life changes week to week.

**Weekly Override**: From the **Week** view, you can override availability for any upcoming week. Tap the availability section to:

- Toggle days on/off
- Change location for specific days (gym, home, outdoor)
- Select which gym for each day

Overrides are temporary — they only apply to that specific week. Your default settings remain unchanged. The planner merges the override into your availability before generating that week's plan.

**Plan your week banner (Today page)**: a shortcut appears on Sundays and Mondays only.
- **Sunday** → adjusts the **upcoming** week (Mon–Sun starting tomorrow).
- **Monday** → adjusts the **current** week (the Monday you're on), as long as no session has been logged yet.
- Once any session is marked done in the current week, the banner is hidden — partial-week edits go through the per-day **Replan** dialog instead.
- Tue–Sat: the banner is hidden; use Replan for individual days.

---

## 13. Locations & Equipment

The plan is built around **what equipment you have**, not where you are. Each location (gym, home) has a set of equipment, and each session requires specific equipment. The planner only assigns sessions you can actually do.

### Setting Up

In **Settings → Locations**, configure:

- Your gym(s): name + available equipment (hangboard, campus board, pull-up bar, weights, kettlebell, bench, etc.)
- Your home setup: what equipment you have at home (hangboard, pull-up bar, weights, etc.)
- Homewall: if you have a homewall at home, boulder sessions become available for home days

### How It Works

When the planner builds your week, it checks each day's location and available equipment, then selects only sessions whose `required_equipment` is a subset of what you have. If your home gym only has a hangboard and pull-up bar, you won't get sessions that require a campus board or weight bench at home.

### Non-Standard Equipment

If you have equipment that's not in the standard list (e.g., a specific training board, a crack machine, custom setup), contact us at **[your email]** and we'll evaluate adding it to the catalog so the engine can prescribe exercises for it.

---

## 14. Outdoor Sessions

Outdoor climbing is tracked separately from indoor training.

### Setting Up Spots

In **Settings → Outdoor Spots**, add your regular crags with:
- Name
- Discipline (lead, boulder, or both)
- Typical days you visit

### Logging

Start an **Outdoor Session** for a live, timed day (or use **Quick log** for a no-timer entry). As you climb, log each route with one tap:
- **Sent** / **Fell / try** are the two primary buttons. On a clean **first-try send** you can tag it **Onsight** (no beta) or **Flash** (with beta). A send after more than one attempt is a **Redpoint** automatically.
- A **rest timer** runs between burns (with the suggested rest beside it). Each logged route shows the **rest** you took before it.
- Optionally tap **Start climb timer** before a burn to time the climb itself — the route then also shows your **climb time**. This is optional; skip it and nothing changes.

A live **weather widget** shows conditions for the day — tap to expand for feels-like temperature, wind speed + direction, humidity, dew point, cloud cover and precipitation chance.

Outdoor sessions appear in your weekly timeline. The planner knows about your outdoor days (if you've set them in availability) and plans around them — no indoor sessions are scheduled on outdoor days.

### Stats

The Outdoor page shows: per-spot breakdown, grade histogram, and session history. Tap any session to expand the routes you climbed that day. The **Routes** list can be sorted by hardest grade or most recent, and collapses to the top 10 with a "Show all" toggle. Two charts track your **grade progression** (hardest send per month) and **monthly volume**.

---

## 15. Weekly Report

The **Weekly Report** (Reports tab) gives you a snapshot of your training week:

- **Adherence**: How many planned sessions you completed vs. skipped
- **Load**: Total training load for the week (engine sessions + free sessions + supplementary)
- **Difficulty Distribution**: How exercises felt across the week (histogram of feedback)
- **Progression Table**: Which exercises progressed, regressed, or stayed flat
- **Free Climbing Summary**: If you had free sessions — number of climbs, max grade, send rate, duration

**How to read it**:
- Adherence > 80% is great. Below 60% consistently means the plan might not match your real schedule — adjust your availability.
- Load should trend gradually upward within a phase, with drops during deload. Spikes > 10% week-over-week are a yellow flag.
- If most feedback is "Hard" or "Very Hard", loads will auto-decrease. If most is "Easy", they'll increase. A healthy distribution clusters around "OK".

---

## 16. Tabata Timer

The **Tabata** timer (in the More menu) is a standalone configurable interval timer — use it for any timed protocol, not just Tabata.

**Parameters** (all editable):
- Prepare time (default 10s)
- Work time (default 40s)
- Rest time (default 10s)
- Cycles per set (default 8)
- Sets (default 1)
- Rest between sets (default 60s)
- Cool down (default 0s)

The timer shows total time and intervals computed in real-time. During execution: animated progress ring, phase-colored backgrounds (teal for work, blue for rest), 3-2-1 countdown beeps, and voice encouragement. Expand mode gives you a fullscreen display with large font.

---

## 16b. The Coach (AI Chat)

The **Coach** (in the More menu, or from the card on Today) is a conversational training assistant that knows your plan and your history: your current phase and week, your assessment profile, your test baselines and current working loads, your recent sessions and outdoor logs, and your planned outdoor days and trips. It replies in the language you write in.

It also sees **real weather** (OpenWeatherMap): current conditions at your location (if you allow location access on the Coach page) and the midday forecast for your planned outdoor days in the next 5 days — so "what conditions will I find at the crag on Sunday?" gets a real answer, with friction advice.

Two ways to make it more personal:

- **Notes for your Coach** (Settings): anything it should always keep in mind — fears, schedule constraints, personal goals. It factors them into every answer.
- **Suggested questions**: tap a chip above the message box — they adapt to your week (outdoor day coming up, today's session, current phase).

**What it's good at:**

- "Where am I in my plan? How is it going?"
- "What did I do this week?"
- "I'm climbing outdoors today and it's hot — how should I adapt?"
- "I'm traveling without equipment — what can I do?"
- Training-science questions (grounded in the same literature the engine is built on)

**What it will NOT do:**

- **Modify your plan.** The Coach is suggest-only — it can recommend, but every change to your plan goes through the normal app flows (replan, feedback, session edit). The deterministic engine stays in charge.
- **Diagnose injuries.** If you report pain, it will tell you to stop and see a climbing-savvy physiotherapist — by design.
- **Give weight-loss or medical advice.** It redirects you to qualified professionals.

**Limits:** 30 messages per day, subscription required. Conversation history is preserved between visits.

---

## 17. Don't Overtrain — Trust the Process

The biggest risk for motivated climbers isn't under-training — it's doing too much.

**Key principles:**

- **Rest days are training days.** Adaptation happens during recovery, not during the session. The plan includes rest days for a reason.
- **Don't add sessions to "make up" for missed days.** The system already adapts. Adding volume on top of that creates load spikes — the primary injury risk factor.
- **Deload is not optional.** Your body needs a full deload week to consolidate gains. Skipping deload leads to plateau or injury.
- **Follow the phase.** If you're in Base phase and the climbing feels easy, that's correct. Adding limit bouldering because you're bored defeats the purpose of the phase.
- **Weekly volume increases should stay under 10%.** Keep an eye on your weekly report — if you're adding free sessions and supplementary work on top of the plan, you can exceed safe thresholds.
- **If you feel consistently beaten up**, check your feedback — are you being honest? Honest "Very Hard" feedback will trigger the system to reduce loads.

**Signs you might be overreaching:**
- Performance declining over 2+ weeks
- Sessions feeling consistently harder than expected
- Completing fewer sessions than usual
- General fatigue that doesn't resolve with a rest day

If this happens, give honest feedback ("Hard" / "Very Hard") and the closed-loop system will reduce your loads automatically. Consider taking an extra rest day or moving your deload forward.

---

## 18. Backup & Recovery

### Recovery Code

Your account has a recovery code (format: `CLIMB-XXXX-XXXX`). Find it in **Settings**. **Save it somewhere safe** — if you lose access to the app (e.g., iOS PWA reinstall clears data), this code is how you get your data back.

To recover: open the app → on the onboarding screen, tap "Recover existing account" → enter your code.

### Export / Import

In **Settings**, you can:
- **Export**: Download your full training state as a JSON file. Use this as a backup.
- **Import**: Upload a previously exported state to restore your data.

---

## 19. Need Help?

- **Equipment requests**: If you have non-standard equipment you'd like integrated into your plan, email **[your email]** with details.
- **Bug reports**: Use the **What's Next** page to submit feedback, or email directly.
- **Feature requests**: Vote and comment on the **What's Next** page — your input shapes what gets built next.

---

*climb-agent is built on peer-reviewed climbing training science: Hörst, Lattice Training, Eva López, Tyler Nelson, and more. No bro-science. No guessing. Train better, not more.*
