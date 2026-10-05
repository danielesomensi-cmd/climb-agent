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
18b. [Subscription & Free Trial](#18b-subscription--free-trial)
19. [Need Help?](#19-need-help)

---

## 1. How the Plan Works

climb-agent builds your training plan through a pipeline:

**Assessment → Goal → Macrocycle → Weekly Plan → Session → Exercises**

1. **Assessment**: During onboarding, you provide your climbing experience, grades, test results, and self-reported weaknesses. This generates a 5-axis profile (finger strength, pulling strength, power endurance, technique, endurance) scored 0–100.

   Only your **redpoint** grade is required — onsight and your secondary weakness are optional, and leaving them blank costs you nothing (the engine uses a neutral value). What you *do* need is at least one place with a climbing wall or board and at least one slot you can actually train in; without those there is no climbing to schedule, and the wizard will say so rather than letting you through.

   Your answers are saved on this device as you go, so closing the app mid-wizard doesn't lose them. From the final summary you can jump back to any step and return with one tap.

2. **Goal**: You set a target grade (Fontainebleau) and a deadline. The engine calculates how many weeks you have and what needs to improve.

3. **Macrocycle**: A periodized plan (typically 10–13 weeks, minimum 9) is generated, divided into phases. Each phase has a specific physiological purpose. The plan is tailored to your weaknesses — if your finger strength is low relative to your goal, the plan allocates more time and intensity to finger training.

4. **Weekly Plan**: Each week, the planner selects sessions based on your current phase, available days, locations, and equipment. It runs a 3-pass algorithm: primary sessions first, then complementary work, then tests when due.

5. **Session Resolution**: Each session is resolved into concrete exercises with sets, reps, load, rest times, and tempo — all calculated from your current working loads and progression state.

6. **Feedback Loop**: After each session, your feedback drives the closed-loop adaptation system. Loads adjust up or down based on how the session felt. Every ~6 weeks, test sessions re-assess your profile and the plan recalibrates.

**This is fully deterministic.** Same inputs always produce the same outputs. No randomness, no AI guessing — just rules, catalogs, and your data.

---

## 2. The Macrocycle: What to Expect in Each Phase

Your macrocycle follows the Hörst 4-3-2-1 periodization model. Each phase builds on the previous one. **Trust the progression** — it's designed this way for a reason.

The **Plan** page shows your position in the cycle: completed phases get a green ✓ on the timeline, and a progress line tells you how much of the cycle is behind you. When you enter a new phase, the app celebrates the one you just completed and tells you what to expect next.

The Plan page also has a **Milestones** gallery — one-time achievements you unlock as you train: your first guided session, your first outdoor day, a new hardest grade sent, a "Perfect Week" (every planned session done, rest days included). They're all "firsts" — there are no streaks to lose and nothing ever locks back up. Unlocked ones light up; the rest stay dimmed so you can see what's ahead.

### Reading the radar

The five-axis radar at the top of the Plan page is **scored against your goal grade**, not against
some absolute maximum. The subtitle says so: *Readiness for 8a+*. A score of 100 means "you already
meet the strength benchmark that grade typically demands" — it is a finish line for *your* goal, not
a perfect score, so an axis that hits it shows **✓ At target** instead of a bare number. Two climbers
with identical strength but different goals will see different radars, and that is intended.

Tap the ⓘ next to any axis to see what it measures, what it is scored against, and — when the score
is low — what kind of training moves it.

**Technique & Tactics is your own read on yourself.** No test exists for it, so it is built from the
weakness you selected during onboarding and nothing else. It informs the coach and it is shown on the
radar, but it **never changes your plan** — a training plan should not be reshaped by a dropdown. It
used to be derived partly from the gap between your redpoint and your onsight; that gap turned out to
describe your *style* rather than your technique (a redpoint specialist runs a wide gap on purpose),
so it is now a tactical note for the coach instead of a score. Power Endurance works the same way
until you have done a repeater test: until then it sits at a neutral 50 rather than pretending.

**Goal vs Elite.** If you have entered a max hang or a weighted pull-up, a `[ Goal | Elite ]` toggle
appears above the radar. Goal is the default and is the scale everything else in the app uses. Elite
re-draws the same axes against fixed benchmarks for climbers operating around 8b–9a, so you can see
how far the top of the sport is rather than how close your own goal is. **It changes nothing but the
picture** — your plan, your weights and your progression are always computed from the Goal scale.

Only **Finger Strength** and **Pulling Strength** have an elite benchmark today; Endurance, Power
Endurance and Technique are shown greyed with an em dash, because there is no benchmark for them we
would stand behind. A greyed axis means "we have no ruler", never "you score zero".

The same radar and the same toggle appear on the public **/assessment** page, where anyone can get a
profile without an account — nothing entered there is stored.

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

At the bottom of **Today**, below the daily quote, a small **"Did you know?"** card surfaces one app feature per day — things like the weekly availability override, the Session Builder, or the Coach's personal notes. Tap the link to jump straight to the feature, or the ✕ to dismiss it for the day.

Your daily workflow:

1. Open the app → **Today** shows your session(s)
2. Tap a session to see the full exercise list with loads
3. Start the **Guided Session** for step-by-step coaching, or train independently
4. When done, tap **Done** and give feedback
5. If you can't train, tap **Skip** — the system adapts

**Done** and **Skip** are always reversible — tap **Undo completion** (to reverse Done) or **Undo skip** (to reverse Skip) — don't worry about misclicks. Undoing a skip brings back the exact session you skipped, your own custom sessions included, and the usual recovery rules still apply to it.

### Same main exercise for the whole phase (once you have tested)

Once you have a recent strength test (max hang or weighted pull-up, within the last 90 days), the main exercises stay **fixed for the whole phase**, so you can see your progress week on week:

- **Finger strength** — max hangs on the 20 mm edge (half crimp) if your tested level is high enough, otherwise a submaximal variant. In Power Endurance the finger session becomes a short maintenance dose (3 sets).
- **Weighted pull-ups** — in the first **two** pulling-strength sessions of the week during Strength & Power (one in the other phases). The other sessions, and the pulling block after a limit or power day, use pull-up variations without added weight.
- **Limit bouldering** on the wall and on the board also stays the same for the phase, and so does the campus exercise during Strength & Power. If your finger test is below the strength threshold (or you have not tested your fingers), you get the gentler campus drills and wall limit bouldering instead of the hardest board and campus variants.
- **Core and shoulder accessories** alternate between two exercises (A one week, B the next), so they change but stay recognisable. If your tested level is high, the easiest core exercises (plank, dead bug, plank shoulder taps) are left out when there is an alternative.

To protect you from stacking fatigue, the heavy version steps down for that day if you did weighted pull-ups in the last 48 hours or have a limit/strength day tomorrow (a pulling session that steps down does not use up one of the two weekly heavy slots). If you did max hangs (or a finger test) in the last 72 hours, the finger block switches to sub-maximal hangs (long, light hangs with no max effort). It never gives you another max hang. Without a recent test nothing changes: exercises keep rotating as before.


### Climbing in the evening, extras at lunch (complementary slots)

If you train twice on some days — say climbing in the evening and a short gym session at lunch — you can mark a time slot as **complementary** and give it a time limit (for example 45 minutes for a lunch break). The planner then keeps the climbing sessions of your phase on your other slots and fills each complementary slot itself with a short session from a rotation you choose: **legs**, **HIIT**, **easy cardio (Zone 2)** and **push + arms** (chest, triceps, biceps). Sessions longer than the slot's limit are never put there.

Which extra goes on which day is decided **every week from your actual climbing days**, not fixed in advance:

- HIIT never on the day of, or the day before, a max / limit / test session or a day climbing outdoors — and at most one HIIT a week (it does not count as one of your hard days). In a deload week HIIT becomes easy cardio.
- Biceps work not in the 24 hours before a heavy pulling session.
- Legs not in the 48 hours before a limit session, an outdoor day or a trip departure (also when the trip starts early next week).
- No HIIT and no legs in the last days before a trip.
- Easy cardio can go anywhere.

Your own sessions count: a custom session you put on a lunch, a session you moved, an outdoor day you planned — the planner works around them and never refills a lunch you filled or emptied yourself. When you change the plan by hand (move a session next to the HIIT, for example) nothing is changed for you: the week just shows the new alert.

These are preferences, never locks: if a week cannot satisfy all of them, the planner picks the least bad option and **tells you** which rule it had to bend; if a slot cannot be filled (for example the gym lacks the equipment), or one of the rotation's sessions has no slot left this week, it says so instead of leaving it out without a word. Complementary sessions do not change how many climbing days you get. *(Setting slot roles from the Settings screen is coming in a following update.)*

### Key sessions

Each phase has a few **key stimuli** that matter more than everything else — the sessions that make the phase work:

| Phase | Key sessions each week |
|---|---|
| Strength & Power | Finger max (a heavy hang session: home finger strength *or* the long strength session) · Limit (limit boulders / board / campus) · Max pulling (weighted pull-ups) |
| Power Endurance | Power-endurance intervals · Finger maintenance · Limit at least every 12 days |
| Performance | Project |
| Every phase | Technique (feet and body positioning near your limit) |
| Strength & Power, Power Endurance, Performance | Try-hard (falls practice / full commitment — it rides on the limit session, on the project session in Performance) |

On **This Week** the grid shows a ★ on the days with a key session (red when it was skipped or turned into recovery), and each session card carries a badge: **Key · Finger max**, **Key ✓** once done, **Supporting** / **Optional** for the other sessions of the same stimulus (Optional in a re-entry week, when you have had fewer than two limit or finger sessions in the last three weeks), **Skipped key** or **Downgraded from …**.

The **Key sessions this week** card lists every key stimulus with its status. A key session counts when it is done **at the dose of the phase**: a weighted pull-up or max hang well below your tested max shows as *only a partial dose* — it still helps, but the stimulus is not ticked. Outdoor days count too (a route near your redpoint is a finger-hard day and a try-hard day), and a free boulder session with at least two problems at your limit target (or marked *It was a limit session*) counts as limit and try-hard. An outdoor day does **not** tick the technique key: the app cannot tell whether you worked on your feet and positioning, so technique counts only for the technique session or at least two feet / positioning drills (pacing, breathing and route-reading drills do not count). The try-hard counts when a session holds a **fall-practice block** — the limit session being on the plan is not enough; the card tells you which session to add it to. In Power Endurance the limit stimulus can be proposed even though the phase's own plan has no limit session.

When a key session is missed, the card tells you what to do:

- **Re-schedule** — the app found a safe day this week (finger recovery gap, hard-day cap, upcoming tests, next week's key sessions and the heavy-pulling rules — no weighted pull-ups the day before a limit or long strength session, at most two heavy pulling sessions in 7 days — all checked). Tap **Add to my week**. When the card shows more than one proposal, each was checked with the earlier ones already in your week, so they never take the same slot. A proposal never needs another session to change: a day where the catch-up would sit inside the recovery gap of another finger session (even an easy finger maintenance) or push the week over its hard-day cap is not proposed.
- **Next key session on …** — catching up would sit too close to next week's key session: skip the catch-up, the plan already has the next one.
- **No catch-up** — you logged a very hard session in the last 3 days: recovery comes first.
- **Let it go** — no safe day left this week. A stimulus missed in a past week is gone, not a debt.

At most one finger catch-up is proposed per week. On **Today** the card appears only when something is owed. You can hide a row for the week with ✕.

**Adding a custom session** (from This Week, Today, the Coach or the body-part picker) first checks the key sessions: if it would land within 72 hours of a max test, or put finger-hard work inside the recovery gap of another finger-hard day (a key session you already did included), you get a warning with **Add anyway** / **Pick another day**. It never blocks you, and adding it never changes the key session or any other session of the week: the two stay as they are and the week carries the alert.

**Coach.** When you ask the coach for a session close to a finger key session — one you already did, one still to come, or one later the same day — (or within 72 hours of a max test), it leaves out the finger-hard exercises (and heavy pulls before a pull-up test) and tells you why on the session card. The coach's answers also know which sessions are key this week.

**Coach and recovery days.** The coach now reads the same recovery rules the plan uses for the day you ask a session for. On a day that sits next to a finger-hard day (a limit session, max hangs, a hard outdoor day, a max test) it leaves out max hangs, limit boulders and campus; on a day when heavy pulling is off (the evening before a limit or long strength session, or a week that already holds two heavy pulling sessions) it leaves out front-lever work, max-effort pulls such as the assisted one-arm pull-up, and any weighted pull-up that would land at 85% of your max or more — moderate pulling stays. A pain flag you reported (score 2 or 3) works the same way for as long as it lasts: finger pain keeps max hangs, campus and limit boulders out of any session the coach builds, pulling pain keeps heavy pulling out. Once you have a tested max, a single session never stacks more than two finger-hard or campus exercises (one when you say you are low on energy). What was left out, and why, is listed with the session, and the effort cue on the card says which work stays submaximal. It also prefers exercises you have not done in the last three weeks over the ones you keep repeating (it no longer simply hides everything recent), and it knows your tested maxima, today's anchored loads, any pain flag, your key sessions and your recent limit sessions — so its chat answers quote the same numbers the plan uses.
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

**When a rest runs out**: what happens depends on what comes next.

- **Timed work** (a plank, a hang, an interval): the next set starts on its own the moment the rest ends. On these the clock *is* the exercise, so tapping to restart every set would defeat the timer.
- **Rep-based work** (bouldering, a set of pull-ups): the timer stops and waits for you. It keeps counting *up* (`+2:14`) and shows a **Next set** button — the set counter does not move until you tap it. Only you know whether you're actually back on the wall, so the app never counts a set on your behalf.

One exception overrides both: a rest that ran out **while the app was in the background** always waits for your tap, whatever comes next. Nobody watched that clock, so the app will not count work you may not have done.

**iOS Safari note**: The timer uses a wall-clock engine specifically designed to survive Safari background suspension, and the screen is kept awake for the whole session. If you switch apps or the phone locks, the clock stays accurate — and anything that ran out while you were away waits for your tap rather than advancing the counter.

Audio cues require one initial tap to activate (iOS requirement).

**You can always**:
- Skip an exercise within the guided session
- Adjust the weight/load if the prescribed load isn't available
- Exit the guided session and mark the session manually

---

## 5. Giving Feedback

After completing a session, you can rate each exercise:

- **Very Easy** — Could do much more
- **Easy** — Comfortable, could add load
- **OK** — Appropriate challenge
- **Hard** — Struggled but completed
- **Very Hard** — Barely completed or had to reduce

**Nothing is pre-selected, and every answer is optional.** An exercise you don't
touch is saved as **not rated** (shown as "—"): its load stays exactly at what you
used, and the weekly report and the Coach don't pretend it felt "OK". Tap a
selected rating again to clear it. Exercises you mark done from the summary
("Mark remaining as done") are not rated either.

**A rating drives your progression.** The closed-loop system uses it to adjust loads for next time:

- "Very Easy" or "Easy" → loads increase next session
- "OK" → loads stay the same
- "Hard" → loads stay or decrease slightly
- "Very Hard" → loads decrease

**Be honest.** The system only works if your feedback is accurate. There's no benefit to saying "OK" when it was "Very Hard" — you'll just get a harder session next time that's too much.

The session's overall difficulty (used by the weekly report and by the automatic
"take it easier tomorrow" rule) is computed only when the exercises you rated
cover at least half of the session's effort: one "Very Hard" tapped on a warm-up
does not make the whole session very hard.

### Measuring instead of guessing (optional, one tap)

Some exercises ask for a number as well — always optional:

- **Weighted pull-ups / chin-ups — "Reps on your last set".** Do the prescribed
  sets, and on the **last set only** do as many clean reps as you can, stopping one
  short of failure. Enter that number. With 4 reps on a 4×3 at +30 kg the next
  session goes to about +32.5 kg (never more than +5 kg in one session); with fewer
  reps than prescribed it comes down. Doing fewer sets than prescribed never raises
  the load. When your last set shows you are stronger than your tested max, twice,
  the app notes it — the retest itself is still scheduled by the plan.
- **Max hangs — "How much longer could you have held the last hang?"** Failed /
  0–2 s / 3–5 s / >5 s. More margin raises the training load a little (within the
  weekly limit), "Failed" lowers it.
- **Overhold (guided player only, opt-in).** Tick **Overhold last rep** before a
  max hang: on the very last rep of the last set the timer keeps running past the
  target (at most +6 s) — tap it when you let go. One second is taken off for the
  time it takes you to reach the phone, and if the +6 s run out without a tap
  nothing is recorded (the set still counts). Only a timed hold of more than
  5 s past the target at ≥ 90% of your max counts as evidence for an earlier
  retest; the chip alone never does.
- **Max hangs outside the four tested exercises** (10 s hangs, Hörst 7-53) never
  go above the same ceiling as your 7 s max hang once you have a tested max.
- **Accessories (bench, squats, curls, dips…) — "Reps on your last set (target N)".**
  Double progression: when your last set reaches the target with all sets done,
  the target goes up by one rep; at the top of the range (e.g. 4 → 6 reps) the
  load goes up 2.5% and the target goes back to the bottom. Without a number,
  "Easy" adds 5% and "Very Easy" 10%.

### Any pain?

At the end of a session there is one **"Any pain?"** row: 0 None · 1 Niggle · 2 Pain ·
3 Had to stop. From 2 you pick where (fingers, elbow, shoulder, other).

- **2** — for 7 days the loads on that zone drop by 10% (loading-pin lifts too, per
  hand) and max hangs stay at or below 85% of your max; nothing on that zone goes
  up meanwhile.
- **3** — the same for 14 days, max hangs capped at 80%, and a message right after
  you save suggests marking the zone as a limitation (**Review** opens Settings →
  Injuries & Limitations; nothing changes until you decide).
- **1** is only recorded. Your plan is never rearranged and past sessions are never
  changed; the affected exercises show "Pain reported recently — keep it sub-max".
- The reduction is applied **once**: lifting the lighter load during the block does
  not lower your working load, and when the block ends you are back where you were
  (a "Hard" during the block still brings it down a little).
- A **test** of that zone is not scheduled while the pain is recent (7 days, or
  until the block ends); a test already in your plan shows the warning instead.
- **Tapped the wrong number?** Reopen the session with the pencil and set the
  right pain (0 clears it): the block that session wrote is recomputed. Saving
  without touching the pain row leaves it as it was.

### The load you actually used

For every exercise with a weight, the feedback form shows a **kg field pre-filled
with the load the app proposed**. Change it whenever you used something else —
that number, not the proposed one, is what the app remembers for next time.

This works the same way whether you run the session in the guided player or mark
it done from **Today** / **Week**: both ask for the load, and leaving the
pre-filled value confirms it.

Two things worth knowing:

- Your remembered load does **not** expire. An exercise you only train every few
  months comes back with the weight you last used, not with the beginner default.
- A remembered load only moves when your feedback says so ("Easy" or a measured
  set raises it, "Hard" lowers it). "OK" — or no rating at all — keeps it exactly
  where you put it.

### Max hangs and weighted pull-ups: your max vs your training load

For **max hangs (5" and 7") and weighted pull-ups / chin-ups** the app keeps two
separate numbers once you have a **recent test** (less than 90 days old):

- **Your max** — the number from your last test. It changes **only when you test
  again**. Feedback never moves it, and saying "Hard" never schedules a test.
- **Your training load** — the weight you actually train with. It moves in small
  steps from the load you used: pull-ups "Easy" +2.5 kg, "Very Easy" +5 kg, "Hard"
  −2.5%, "Very Hard" −7.5%; max hangs ±2 kg ("Easy"/"Hard") or ±4 kg ("Very
  Easy"/"Very Hard"). "OK" keeps it. Pull-ups never rise more than 5 kg in one
  session, max hangs not more than 5% of your max in a week.

The load you're given always stays **below your max**, with room to spare:

- a 4×3 of weighted pull-ups never goes above about 85% of your estimated 1RM — to
  train heavier, the scheme changes (e.g. 4×2), the 4×3 does not get heavier;
- a max hang always leaves about three seconds in the tank (in Strength & Power at
  most ~95% of your max).

**Coming back after a break.** If you haven't done that kind of work for two weeks
or more, the first session back is capped at 90% of the usual ceiling and the
second at 95%; from the third session the full ceiling applies. Your test counts as
a session.

**Three hard sessions in two weeks** on the same exercise family bring the load
down to the bottom of the phase range — the app does not lower your max for it.

When you rate a session "Easy" but you are already at the ceiling of your tested
max, the load stays where it is: the next scheduled retest is what raises it.

These notes — fatigue, ceiling, a reported pain, the comeback cap — are shown
under the suggested load, in the exercise details and in the guided session.

**Custom sessions follow the same numbers.** In a session you built (or one the
Coach composed), these exercises are on **Auto** by default: they are
recalculated **on the day you play it**, from your max and your training load —
the same weight a planned session would give you that day (the session view
shows today's numbers). Choose **Fixed kg** in the builder when you want your own
weight every time; on Auto, the kg you type is used only if you have no recent
test. During a comeback, max hangs are also capped at 5 sets.

If you haven't tested yet (or your test is older than 90 days), nothing changes
for you: loads are worked out exactly as before. A max you typed in during
onboarding counts as a starting point, not as a test.

### Limit bouldering grades

Limit bouldering remembers your grade **per surface** — the Kilter, the MoonBoard,
the spray wall and the gym wall each keep their own, because a Kilter 7A is not a
gym 7A. It does not matter which limit exercise the session picked: a grade from
"board limit boulders" on the Kilter counts for "limit bouldering" on the Kilter too.

- The grade is remembered for **6 months**.
- **Coming back after two weeks or more** on a surface, the first **2 sessions** are
  half a grade easier (e.g. 7A+ instead of 7B). After that you are back on your
  grade — the easier sessions never lower it for good.
- On a board you have never logged, the first target is one letter below your
  outdoor boulder redpoint (7C outdoors → 7B on the Kilter).
- One bad session does not drop the target far below the best you climbed on that
  surface in the last 6 months. Several bad sessions in a row do bring it down, half
  a grade at a time.
- Away from a surface for more than 6 months, the comeback starts from the lower of
  your last grade there and your outdoor-based anchor — never harder than a shorter
  break would give you.
- Your feedback moves the target by **half a grade** at a time: *easy* +½ (7A → 7A+),
  *very easy* +1, *ok* keeps it, *hard* −½, *very hard* −1. The `+` is never lost:
  an *ok* at 7A+ stays 7A+.

**Logging problem by problem (recommended).** In the guided session, in the custom
session player and in the **post-session feedback dialog** (when you mark a session done
from Today or This Week without running the guided player), a limit exercise shows
**Problems climbed** instead of a single grade field — the same logger everywhere, so a
limit closed from the dialog moves your target exactly like one logged in the player.
Other exercises with a grade target get an **Actual grade used** field in the dialog,
pre-filled with the target, as in the guided player. Add a row for each problem you tried: grade (pre-filled with your target),
number of tries (1–10) and the outcome — **Sent**, **High point** (you got further than
before but did not top it) or **No progress**. A new row has **no outcome** until you pick
one: a row left without an outcome is not counted (it is never read as a send). On a
*High point* or *No progress* row you can also count the **crux moves** you did — crux
moves on a problem at your target hold the target. When you log problems, they decide the
next target instead of the effort chips:

- **Up half a grade**: one send above the target, or two sends at the target.
- **Stays**: one send at the target, a high point at the target, or crux moves done —
  a session spent working one hard problem without topping it never lowers your
  target.
- **Down half a grade** only after **two sessions in a row** without progress (no send
  near the target, no high point).
- Never more than half a grade per session.
- More than **20 hard attempts** in one session (on problems at or near the target):
  the target cannot go up (it can still come down after two sessions without progress)
  and the app reminds you to recover fully — that much hard
  pulling on small holds is a finger-safety signal, not a performance.
- A send **above your boulder redpoint** on the gym wall never changes your redpoint by
  itself: after saving you get a message suggesting you update it in Settings → Profile & Maxes
  if it was a real send.
- In a re-entry (the 2 easier sessions after a break) the problems are logged but the
  target stays on your pre-break grade; the session that closes the re-entry is judged
  against that grade.

Not logging any problem keeps the old behaviour: the target grade is sent as the grade
you climbed and the effort chip moves it.

A limit exercise inside a **custom session** — including one the Coach composed — gets the
same target as the plan on the day you play it, and its outcome counts. The target is
never saved with the session: it is worked out again every time you open it, for that
day, whether you start it from Today, This Week, the session builder or the Coach's
"Add to today & run". A custom session is not tied to a gym, so when you have
more than one limit surface (Kilter, spray wall, boulder wall…) the player asks **Where are
you climbing?**: the target shown and the memory updated are the ones of the wall you pick. For the weekly **Limit** key session, a custom
session counts when you logged at least **two problems at your target** (sent or high
point); a custom limit spent on easier problems shows as a partial dose. If you log no
problems it counts as done, as before.

### Grades on endurance and technique drills

Rope intervals, threshold laps, 4×4s and drills get a grade worked out from your
onsight or redpoint (e.g. "one grade below your onsight"). Grades with a `+` keep it:
with a 7a+ onsight, route intervals one grade below come out as **6c+** (before
October 2026 the `+` was dropped and they came out as 6c). When your endurance
feedback agrees twice in a row (two *easy* or two *hard*), the remembered grade moves
by half a grade.

**Power-endurance work on routes** (route intervals, linked laps, routes on the
minute, threshold climbing) is anchored a little differently: to your onsight **or**
to three half grades below your redpoint, whichever is harder. If your onsight is
far behind your redpoint — a 7a+ onsight with an 8a+ redpoint — the intervals are
sized from the redpoint side (7c, so one grade below is **7b**) instead of from an
onsight that would make them too easy. If your onsight is within three half grades
of your redpoint nothing changes. Aerobic laps and ARC still follow your onsight.

A session you changed with the pencil keeps the exercises you chose, but its grade
targets still follow these rules: from today on they are worked out again each time
the week loads. Sessions you already did, skipped, or that are in the past stay exactly as they were.

---

## 6. Test Sessions

Tests re-measure your baseline numbers and update your 5-axis profile. Your max only ever changes with a test: feedback moves your working loads, not your max.

**Once you have tested** (a max hang and/or a weighted pull-up test in the last 90 days), the plan schedules your next tests by itself:

- at the **end of the Strength & Power phase**, to measure what the block built;
- at the **start of a new cycle**;
- **12 weeks** after your last test at the latest;
- **earlier**, when two sessions in which you measured your effort show you are clearly above your tested max (labels alone never trigger a test).

A test is never repeated too soon: **4 weeks** if the last one came after little recent max-strength work (low confidence), **6 weeks** otherwise. If that gap pushes the end-of-strength test past the end of the phase, it moves **one week** later. No tests in the performance and deload phases, in the 10 days before a trip, or within 3 days of a session you rated *very hard*. The finger test needs **72 hours** without hard finger work before it (limit bouldering, max hangs, a hard day outdoors — custom sessions count too) and the pull-up test **48 hours** without heavy pulling. When both are due they share a day: **max hang first, pull-up after**, in a later slot.

**Week** shows a **"Your tested maxes"** card: each max with its test date and confidence, how it moved since the previous test (under 5% counts as *stable*), and the next test with the reason. Only numbers from a real test appear there — an estimate made at onboarding is never shown as a tested max. If something lands too close to a planned test after the plan was made (a very hard session, a finger session you added), the card tells you — the test is not moved automatically; move it yourself if you are not fresh.

**Until the plan schedules both tests itself** — you have not tested yet, only one of the two tests is recent, your last test is older than 90 days, or you train fingers on a loading pin — every **~6 weeks** a **"Time to retest"** card appears on **Today** with three choices:

- **Schedule test week** — a test session is added to next week's plan
- **Next week** — you'll be asked again in 7 days
- **Not this cycle** — you'll be asked again in about 6 weeks

There's no way to dismiss the card without choosing: each option tells the engine something different, and skipping the decision entirely is how baselines quietly go stale. If you keep postponing, your prescriptions stay anchored to numbers that no longer describe you.

**The tests:**

- **Max Hang (7s)**: Maximum weight you can hang for 7 seconds on a 20mm edge. Measures finger max strength.
- **Repeater (7:3 to failure)**: How many reps you can sustain at 60% of your max hang. Measures finger endurance.
- **Weighted Pull-Up (2RM)**: Maximum added weight for 2 reps. This 2RM stays your pulling reference: training loads are a percentage of it for the current phase (e.g. ~86% of the 2RM total for heavy 4×3 sets in the strength phase), never the 2RM itself. Training sessions can raise the reference when a set shows you are stronger; only a set you rate *hard* or *very hard* lowers it.
- **Bodyweight Pull-Up Gate**: If you've never done the weighted test, the system first checks if you can do 15+ bodyweight pull-ups. If yes, you progress to the weighted test.
- **Hip Flexibility**: Straddle measurement in cm. Informs mobility prescription.

If you use a **loading pin** instead of a hangboard, the system automatically substitutes the finger tests with loading pin variants (LP Max 5s and LP Repeater). Your pin numbers feed the finger-strength axis exactly like a hangboard result: enter the **external load only** for each hand (don't add your bodyweight), and the engine converts the one-hand lift into the two-hand equivalent the benchmarks are built on. Both hands are averaged, so a left/right difference shows up as an asymmetry to train rather than as extra strength.

If you only have a couple of training days a week, a test week can run out of room — a test needs to respect the same rest spacing as your hard sessions. When that happens you'll see a **"Couldn't schedule a test this week"** note on **Week**: free up an available day or move a session, then use **Replan** to fit the test in.

**Why they matter**: Without fresh test data, the system keeps using your old baselines. Your loads won't progress accurately, and your plan won't adapt to your real improvements. Tests are not optional extras — they're the system recalibrating itself.

**After a test session**: Your profile radar updates, working loads recalculate (a test result is a max, so it resets the training load to a percentage of the new max instead of becoming the next training load), and the remaining macrocycle adjusts its emphasis based on your new strengths and weaknesses. Each max-hang and pull-up test is also compared with the previous one (a change under 5% counts as **stable**) and marked as low-confidence when you hadn't trained that kind of strength in the three weeks before. Both are recorded with the test and the Coach sees them; they are not yet shown on a screen of their own.

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

**After a *very hard* or *failed* session the plan is never changed for you.** The app used to downgrade your next hard session (or turn the next day into recovery after repeated very hard sessions) on its own; it no longer does. Whether to lighten the next hard session is your call: swap or edit it yourself, for example with a custom session.

**Important**: Regenerating creates a new plan. Past sessions are **never modified** — they're immutable history. Only future weeks are affected.

**What you put on the plan stays there.** Whenever a week is rebuilt — a new cycle, a change to your weekly availability or planning preferences, a one-week availability change, resuming after a pause, asking for tests — the app regenerates the parts it planned itself and keeps everything that is yours exactly as it was:

- custom sessions, sessions added from the body-part picker or the coach, quick-adds (forced or not), day overrides, sessions you moved, re-scheduled key sessions, sessions whose exercises you edited;
- sessions you already marked done or skipped, and your outdoor days with their pitch plans;
- what you **removed**: a session you deleted, or the spot you moved a session away from, does not come back when the week is rebuilt. If you replaced a whole day with an override, the app does not add its own sessions back to the slots you replaced; if you replaced one session of a day, only that one stays out (and the new session takes its slot, e.g. the lunch). A session you added next to a planned one in the same slot does not cost you the planned one.

If keeping your sessions puts two finger days back to back or goes over your hard-day cap, the rebuilt week records an alert about it — it does not change your sessions or the app's own ones for you.

Changing your availability or planning preferences now updates the weeks already planned (current and future), not only the weeks you have not opened yet. If a week cannot be rebuilt for a technical reason, you keep seeing your current plan unchanged and the app tries again the next time you open it.

---

## 7b. Pausing & Resuming Your Plan

Going away — travel, illness, a busy stretch? Instead of regenerating, you can **pause** your plan from **Settings**:

- **Pause plan**: Freezes your plan exactly where you are. While paused, Today shows a "Plan paused" card instead of sessions, and Week/Plan show a small "Paused" banner. No new sessions are scheduled.
- **Resume plan**: Picks up exactly where you left off and shifts the remaining weeks forward by however long you were away. Your end date moves out by the same amount.

**How the shift works:**

- The shift is measured in **whole weeks** (Monday to Monday). A short break of **less than a week** resumes in place and does **not** shift the plan.
- You can pause and resume as many times as you need — the shifts add up.
- Your start date never changes, so all your completed history stays exactly where it happened.
- The weeks ahead are rebuilt for the new timeline, but anything you put on a future date yourself (a custom session, a forced or quick-added session, an override…) stays on **the date you chose** — it is not moved along with the shift.

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

### Moving a Session

On **Week** or **Today**, move a planned session to another day or slot. The slot you leave stays empty — it simply becomes rest; nothing is added in its place. A planned session already in the slot you move to is replaced; a completed or skipped one is not — that move is refused. Nothing else changes: if the move puts two finger-heavy days back to back, or goes over your weekly limit of hard days, the week shows a recovery alert and both sessions stay as they are. Completed or skipped sessions cannot be moved.

### Removing an Exercise

Expand a planned session card and tap the trash icon (🗑) next to any exercise to remove it. A confirmation dialog will appear. You cannot remove the last exercise — a session must always have at least one. Completed or skipped sessions cannot be modified.

### Reordering Exercises

Exercises are ordered by the engine for safety and performance (e.g., warmup → main → cooldown). If you want a different order, grab the drag handle (≡) on the left of any exercise and drag it to the desired position. A one-time warning reminds you that the default order is optimized.

### Skipping an Exercise

Within the guided session, you can skip any exercise. If you consistently skip an exercise, your feedback will signal the system to adjust.

### Changing Load

If the prescribed load isn't available (e.g., you don't have the exact weight plate), adjust within the guided session. The system will adapt based on your feedback at the end.

### Boulder only (today)

Ropes busy, closed, or no partner? Open the session's **⋯** menu and tap **Boulder only (today)**. The session is rebuilt for the boulder wall — either swapping to the boulder equivalent the catalog declares for it, or re-running the same session without the rope wall — and an amber banner marks the card. What you see is what the guided player runs and what your feedback is recorded against.

It applies to that day only and never touches the rest of your plan. **Undo** in the banner restores the planned session. If your gym has no boulder wall, the app says so rather than handing you a session that is boulder in name only.

### Session-Level Changes

For bigger changes (wrong session type, wrong day), use the **Replan** feature instead of modifying the session — see [Section 10](#10-replanning-your-week).

---

## 9. Adding Extra Sessions

### Quick-Add (Climbing Sessions)

From the **Today** or **Week** view, tap the **+** button to open the Quick-Add dialog. The system suggests sessions compatible with your current phase and today's location/equipment.

These are full engine sessions — they get resolved with exercises, loads, and prescriptions just like planned sessions. Their load counts toward your weekly total.

**What you add is what you get — the recovery rules become alerts.** The session you pick goes into the slot you chose exactly as it is, and nothing else in your week changes: the app does not ease it, does not ease the next day, and does not touch any other session. If the session breaks one of the recovery rules, a short note tells you which — see **Recovery alerts** below. Training through an alert is your decision.

### Supplementary Training

The Quick-Add dialog also offers supplementary sessions — non-climbing work you can add any time:

- **Upper Body** — Push/antagonist work (home)
- **Legs (Home)** — Squat/hinge/unilateral
- **Legs (Gym)** — Full leg session with equipment
- **Heavy Conditioning** — Full-body conditioning (gym)
- **Pulling** — Dedicated pulling session (gym)

Four of them are sized for a **lunch break** (about 35 minutes of work inside 45 minutes) at a weights gym:

- **Treadmill HIIT 4x4** — 8 min warm-up, then 4 × 4 min at 85-95% of max heart rate with 3 min easy walking between. Needs a *Treadmill* in the gym's equipment. Zero finger load, but systemically hard: keep it to one a week and away from the day of (or before) a maximal or limit session.
- **Treadmill Zone 2 + Hip Mobility** — 25 min steady incline walk at conversational pace, then optional hip mobility. Needs a *Treadmill*. Fits next to any climbing day.
- **Upper Push + Arms** — bench press, triceps cable pushdown and a curl for the biceps. Needs dumbbells and a *Cable machine* in the gym's equipment, so the triceps work is real triceps work. Keep it out of the 24 h before a heavy pulling session.
- **Legs Maintenance + Foot Strength** — goblet squat, Romanian deadlift and about 8 min of foot strength: toe flexor presses and big-toe calf raises on an edge. The app orders the exercises with its usual sequence, so the light calf raise can come before the squat. Keep heavy legs out of the 48 h before a limit or outdoor day.

The two treadmill sessions need **Treadmill** ticked in the gym's equipment (Settings → Equipment); without it the 4x4 intervals are never prescribed, and if you add the HIIT session anyway at a gym without a treadmill it shows up empty (warm-up only) instead of quietly turning into an easy walk. These four sessions are only offered for you to add: the planner does not schedule them on its own.

Supplementary sessions count as an active training day for adherence and their load counts toward your weekly total. They do not trigger replanning or macrocycle adaptation.

### Free Session

You can also add a free session from Quick-Add. See [Section 11](#11-free-sessions).

---

## 10. Replanning Your Week

The **Replan Dialog** lets you make changes to your weekly plan without regenerating everything. Access it from the **Week** view by tapping a day.

**What you can do:**

- **Change location**: Switch a day from home to gym, gym to outdoor, etc.
- **Change intent**: Override what kind of session you want (e.g., strength, endurance, technique, projecting, rest, recovery, power endurance, or "hard" for auto-select)
- **Go outdoor**: Switch to an outdoor intent (easy outdoor, projecting, volume routes, boulder outdoor). The dialog asks **where**: pick one of your saved spots, or add a new one inline. Apply stays disabled until you choose — the crag name is what the Coach geocodes to give you the weather for that day, so it can't be guessed from the intent.
- **Rest**: Set the intent to "Rest" to replace a session with rest (the other sessions of the day stay — remove them too for a full rest day)

Changing a day's intent replaces **one session**: the one you opened the dialog from, or — when you replan a whole day — the app's evening session (or the app's only session of the day). A session you put there yourself (custom, coach, quick-add, a session you moved) is never replaced this way: the new one is added next to it. **Skip day** clears every session the app planned that day (lunch included) and leaves one recovery session; what you added yourself and what you already did stay. The other sessions of that day stay, and so does every other day of the week: the replanner no longer eases the following days, and a finger session you lose this way is not moved to another day. If the new session breaks a recovery rule — including two hard days in a row because of a session you added or changed — you get a recovery alert instead. Going outdoor clears the app's sessions of that day but keeps the ones you added yourself. It uses 8 indoor intents and 4 outdoor intents to handle all scenarios.

**Skipping a session** is always OK. The system is designed for real life. Skipping doesn't break anything — the plan adapts. Don't add make-up sessions to "compensate" — that leads to overtraining.

### Recovery alerts

When you change the plan yourself — quick-add, replan a day, move a session, add a custom or coach session, change gym, log an outdoor day — the app never rewrites anything you did not touch, not even its own sessions next to yours. It checks the week instead and tells you what the recovery rules object to:

- **Finger gap** — two finger sessions closer than the recovery gap (48 hours, more with slower recovery), Sunday of the previous week included.
- **Before a finger test** — finger-hard work in the 72 hours before a max hang test.
- **Heavy pulling** — more than two heavy pulling days (weighted pull-ups at 85 % of your max or more) in 7 days.
- **HIIT next to a max day** — HIIT on the day of, or the day before, a max finger or pulling session.
- **Hard-day cap** — more hard days in the week than your cap.
- **Before a trip** — a hard session in the no-hard days before a trip.
- **After a big outdoor day** — a hard or finger session the day after a heavy outdoor day.

Alerts are about what can still change: sessions already done, skipped or in the past are counted, never flagged. When the app builds a week on its own, it still follows every one of these rules.

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

### Free boulder sessions as limit sessions

On a boulder surface (gym wall, Kilter, MoonBoard, other board) the summary screen has a
**It was a limit session** switch. A free boulder session counts as this week's **Limit**
key session when you climbed at least **two problems at or above your limit target for
that surface** (sent or tried), or when you turn the switch on. It never changes your
limit target and never feeds the plan's progression — free sessions stay off-plan. Even
when it does not count as a limit session, two or more climbs near your redpoint still
count as a hard finger day for the finger-recovery and test rules. Deleting the free
session removes it from the count.

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

### Session Builder

Reached from **Free Sessions**, the Session Builder is for a workout you want to keep and repeat — as opposed to Body Part Training, which generates one on the spot and forgets it.

- **Build it** — give the session a name, then pick exercises from the full catalog (searchable and filterable) and set sets, reps and rest for each. Warm-up and cool-down blocks are resolved for you into concrete exercises, so you don't have to design them.
- **Harder bodyweight levels and technique drills** — the catalog also holds exercises that the planner never picks on its own and that you only find here: the steps of the bodyweight progressions (tuck → straddle L-sit → V-sit, ring fallouts and standing rollouts, dragon flag from the tuck negative, advanced-tuck and full front lever, Copenhagen variations, ring dips, pistol squats, Nordic curls…), technique and try-hard drills with a single number to track (glued feet on the board, the three-way position menu, the three-attempt comp, no-take leading, the three-step fall ladder, the pre-attempt routine) and a pocket warm-up on the hangboard's 2- and 3-finger pockets (submaximal, feet supported — never a gym mono). Each one says in its cues how to make it harder and what to measure.
- **Progress or Fixed (bodyweight levels)** — when an exercise is a step of a bodyweight progression (L-sit → V-sit, toes to bar, rollouts, front lever, Copenhagen, push-ups, dips, pistols, Nordics…), its editor shows **Progress / Fixed**. *Progress* (the default for new rows) means: if you have a recent strength test, the app sets the sets and reps from **your level on that ladder** on the day you play the session, and the card shows *Level 4/6 · Straddle L-sit · 3x20 s*. When you have done the top of the band enough times, the session shows **"Ready for V-sit 45°: switch?"** — nothing changes until you tap **Switch** (the row is rewritten for the next times; past sessions never change). **Stay** keeps you where you are. *Fixed* keeps exactly the sets and reps you typed. Rows saved before this feature are *Fixed* until you change them.
- **Save it** — your custom sessions are stored on your account and listed on the builder's home screen. Open one to view it read-only, edit it, or delete it. If you tap back with unsaved changes, the builder asks before discarding them.
- **Read the load** — the header shows the session's estimated load score and duration as you add exercises, using the same formula the engine uses for a planned session.
- **Run it** — a saved session plays back in the same guided runner as a planned session, with the timer, the load fields and the per-exercise cues.

Exercises that are performed **one side at a time** — Copenhagen plank, Pallof press, side-lying hip abduction and the like — are labelled **"per side"** wherever they appear, and the runner walks you through both: it counts a RIGHT bout and a LEFT bout for each prescribed set, showing which side you're on. So "3×20s" means three sets on each side, and the session's estimated duration accounts for all six.

**How a bodyweight level moves** (athletes with a recent strength test only — everyone else keeps the catalog doses): the label you give after the exercise moves the target inside its band (*easy* one step up, *very easy* two, *hard* one down, *very hard* two down); an untouched label changes nothing. If you enter the optional **clean reps / seconds held on your weakest set**, that number is the base and the label only adjusts it. Two *very hard* in a row drop one level. Harder skills (front lever from the advanced tuck, dragon flag, standing rollouts, Copenhagen long, ring dips, one-arm work) need **two** sessions at the top before moving up — and a session only counts once you have actually done the top of the band (a *very easy* one step below it takes you to the top, not to the next level). At the last level of a family that has a loaded version (weighted L-sit, weighted side plank, weighted push-up, back extension, weighted hanging leg raise) the message tells you to move on to it and with how many kg to start; a slower eccentric or added kg prescribed at the last level shows up on the exercise card. After a break of more than four months (two for skills) you restart one level lower — or, in a custom session that keeps your old level, at the bottom of its band. In the performance and deload phases doses are frozen with one set fewer. Lower-back levels (standing rollouts, straddle/full dragon flag, weighted hollow) are never assigned automatically — but if you set one yourself in Settings, planned sessions respect it. Recovery and deload sessions keep their own light doses. In planned sessions the engine itself puts you on your level and moves you up; after each session a short message tells you what changes next time ("Next time: 3x25 s", "Same dose next time: 3x20 s" after an *ok*, "Promoted: …"). Technique: on the feet drills you can enter the **foot readjustments on your sample problem**, on the fall ladder your **max fear (0-10)** (asked only on the drills of your current feet level) — two clean sessions move you one step up the feet (P1-P4) or falls (F1-F3) ladder.

Custom sessions sit **outside the macrocycle**: running one logs the work and updates your working loads, but it does not feed the closed loop or alter your planned progression.

Max hangs and weighted pull-ups / chin-ups in a custom session are **recalculated on the day you play it** (see *Max hangs and weighted pull-ups* in §5), so a session saved weeks ago never replays a stale weight. To keep your own weight instead, open the exercise in the builder and pick **Fixed kg**.

---

## 12. Confirming Next Week's Availability

Your default availability (days, locations, time slots) is set in **Settings**. But real life changes week to week.

**Training twice in a day (split training)**: if you tick more than one time slot on the same day — say lunch at home and evening at the gym — Settings shows a second slider, **Sessions per week**. Leave it alone and nothing changes: you get one session per training day, as before. Raise it and the planner fills those extra slots, typically with a complementary session at lunch and your climbing in the evening. The extra sessions are never hard ones, and your cap on hard days per week still holds — that cap is what protects recovery, and split training does not touch it.

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

**The location you set for a day is binding.** If a day is marked "home", the planner keeps it at home rather than sending you to the gym — even if that means a lighter session. The one exception is when home isn't somewhere you can train at all (you've turned off the home setup, or listed no equipment there): in that case a home day falls back to your gym instead of leaving the day empty.

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
- **Projecting**: after a **Fell**, the panel stays on the **same route** — the next Sent/Fell logs another attempt on it (no need to re-enter grade or name). Tap **New route** to switch to a different climb; a **Sent** closes the project automatically.
- A **rest timer** runs between burns (with the suggested rest beside it). Each logged route shows how long ago your **last try** on it was — tap the card to expand a **per-try breakdown**: `✗ try 1 · rest — · climb 2:41`, `✓ try 2 · rest 14:20`, so you can read the rest and climb progression try after try. Rest is measured across the whole session — if you climb another route in between, that time isn't counted as rest for the next try.
- Optionally tap **Start climb timer** before a burn to time the climb itself — that try then also shows its **climb time**. This is optional; skip it and the climb segment is simply omitted.

**Crags have no signal, and the app assumes it.** Every route you log is written to your phone first and sent to the server after, so nothing depends on the network being there at the moment you tap. If you're offline you can still **start** the session (the strategy simply doesn't load — it's advice, not a requirement), log the whole day, and close it: an amber line tells you it's saved on the device and will sync when you're back online. Reopening the day — after a refresh, a crash, or a flat battery — brings back the session with every route you logged. Finish the session normally; it uploads by itself the next time you have a connection.

A live **weather widget** shows conditions for the day, rated by a **friction score** (0–100) into four bands — **PRIME / GOOD / OK / POOR** — with a plain-language verdict (e.g. "Conditions are prime — go send your project."). When a later part of the day scores clearly better, a **best window** line tells you when (e.g. "Peak conditions from 19:00 — temp drops to 17°C"). Tap to expand the metrics — each one carries a small tag that says what it means for friction (e.g. **dew spread** "15° below air — prime friction", humidity "dry air", wind "helps drying"). The same card appears on the Today page and on outdoor days. The first time, the Today page shows a small **"Show outdoor conditions"** button instead — tap it to grant location access; once granted, the widget loads automatically from then on.

**Heat is treated as a limiter, not as dry air.** Above about 26 °C the score is capped and keeps falling as it gets hotter, so a 34 °C afternoon never rates better than a 26 °C morning just because the air dried out; from 28 °C the band is at most **OK**, and from 32 °C it is **POOR**. For the same reason the **best window** never points you at an hour hotter than the one you're in — on a hot day it will simply stay silent unless the evening genuinely cools down. On a cold day a warmer later window is still suggested, as before.

Outdoor sessions appear in your weekly timeline. The planner knows about your outdoor days (if you've set them in availability) and plans around them — no indoor sessions are scheduled on outdoor days.

**Multiple crags in one day:** if you climb at more than one crag on the same date (a multi-sector day), Today/Week shows both names joined ("Symplegades - Ourania") — each crag's routes are still logged and kept separate underneath, only the day's label is combined.

### Plan for the day (grades and rests)

An outdoor day on Today or Week carries a **plan**: the pitches to climb, in order, each with an **absolute grade, how many burns, and how long to rest afterwards**.

Tap the kind of day you're having — **Onsight**, **Project**, **Volume** or **Scout** — and the plan is generated from *your* grades, taken from the onsight and redpoint you recorded (if you've only recorded a redpoint, the onsight is estimated one number grade below it). An onsight day for a 7a+ onsight / 8a+ redpoint climber comes out as 6a → 6b+ → 7a → 7a+ → 7b (two burns) → 7a → 6b.

The rests are the part worth reading. On an onsight day the closing pitch gets a deliberately **short** rest — climbing it already pumped is the point, and it's the number most people get wrong when they're tired.

Everything is editable: the pencil opens the list, where you can change any grade, burn count or rest, add pitches and delete them. Once you've edited it by hand the plan is marked **Edited**, and regenerating asks before overwriting your version. Completed outdoor days show their plan read-only — like every past session, they can't be changed.

### Your onsight, from your log

If your outdoor log shows harder onsights than the one you declared, **Settings**
shows a card: *"Your log says onsight 7b"*. It lists the routes behind it — lead
routes you sent in one try the first time they appear in your log — and asks, for
each one, whether it really was **Onsight**, **Flash** or **Worked** (a route you had
tried on a day you never logged looks exactly like an onsight). It takes at least two
onsight or flash routes at that grade, on two different days or at two different
crags. **Confirm** updates your onsight; **Not my onsight** declines that grade for
good — the card stops asking about it (a harder one will still be proposed) and the
routes you marked *Worked* are remembered. A route you mark *Worked* is never counted
again. A route you logged as **onsight** or **flash** counts even if another route
with the same name at that spot came first (generic names like "Tiro 3" repeat). Nothing in your outdoor log is changed — to change a route's style
there, edit the session.

### Stats

The Outdoor page shows: per-spot breakdown, grade histogram, and session history. Tap any session to expand the routes you climbed that day. The **Routes** list can be sorted by hardest grade or most recent, and collapses to the top 10 with a "Show all" toggle. Two charts track your **grade progression** (hardest send per month) and **monthly volume**.

---

## 15. Weekly Report

The **Weekly Report** (Reports tab) gives you a snapshot of your training week:

- **Adherence**: How many planned sessions you completed vs. skipped
- **Load**: Total training load for the week (engine sessions + free sessions + supplementary). It counts what you **actually did**: if you skip exercises inside a guided session, only the ones you completed contribute, so a half-done session no longer shows as a full one.
- **Difficulty Distribution**: How exercises felt across the week (histogram of feedback)
- **Progression Table**: Which exercises progressed, regressed, or stayed flat
- **Free Climbing Summary**: If you had free sessions — number of climbs, max grade, send rate, duration
- **Hardest sends**: your hardest boulder **sent** this week on each surface (Kilter, MoonBoard, spray wall, boulder wall…), with how many sends and your current limit target there. It counts the problems you logged in limit sessions (planned, custom or from the Coach) and the climbs of your free boulder sessions — each climb once. Grades follow your Font / V-scale preference.
- **Month at a glance**: A calendar heatmap at the bottom of the page. Trained days are green (darker = bigger load), and **respected rest days get their own soft green** — recovery counts as a win here, not an empty box. Skipped days stay neutral (no red, ever). Tap any day to open it.

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

It can also pull **real weather** on demand (OpenWeatherMap): just ask. Say "here" (allow location access on the Coach page) for current conditions where you are, or name any crag/city and a day up to 5 ahead — "what conditions will I find at Berdorf on Sunday?" gets a real answer with a friction score and advice. It only checks the weather when your question needs it, and it never invents conditions: if it can't reach the provider it tells you so.

Since A275 it can also answer questions about a **specific time window** and about **daylight** — "what will it be like between 14:00 and 20:00?", "how much light is left?", "which way is the wind coming from?" — because the weather it receives now includes the day hour by hour (in 3-hour steps, in the crag's own local time), sunrise and sunset, and the wind's compass bearing. Those hours are read from the forecast, not estimated: if an hour isn't covered, the Coach says so rather than filling the gap.

Two ways to make it more personal:

- **Notes for your Coach** (Settings): anything it should always keep in mind — fears, schedule constraints, personal goals. It factors them into every answer.
- **Suggested questions**: tap a chip above the message box — they adapt to your week (outdoor day coming up, today's session, current phase).

**What it's good at:**

- "Where am I in my plan? How is it going?"
- "What did I do this week?"
- "I'm climbing outdoors today and it's hot — how should I adapt?"
- "I'm traveling without equipment — what can I do?"
- **"I'm at a regular gym today — build me a session."** The Coach composes a structured strength/antagonist session (warm-up → main blocks → optional core/prehab) from real catalog exercises, adapted to your current phase and the rest of your week. Every exercise that takes a weight always shows a kg field you can log into — even the first time (it just starts empty). For finger/hangboard and weighted pull-up work it pre-fills a starting weight derived from your test max; otherwise it shows your last-logged weight, and never an invented number. The composed session appears as a **card in the chat with one button, "Add to today & run"** — tap it and the Coach adds it to today as an off-plan session and opens the guided player so you can run and log it. It never touches your planned training: it drops into the first free slot of the day (evening, then morning, then lunch), and if all three are already taken it tells you the day is full instead of failing silently. (The AI only reads your request and picks the shape; a deterministic engine chooses the exercises and loads.) Ask it for an alternative when you don't feel like the planned session and it'll weigh what you want against what the plan needs. **Name specific muscles** ("chest, abs and triceps" / "just biceps") and the session is built around exactly those — no unrelated squats or rows padded in. You can also name a **movement** rather than a muscle: lock-offs, pull-ups, hangs, or **handstand work** each map to their own focus, so "45 minutes of lock-offs" gets you actual lock-offs and "handstand practice" gets the real progression — frog stand, wall walk-up, kick-ups, heel pulls, shoulder shrugs and pike push-ups — rather than generic pulling. If you ask for **two sessions in one message** (e.g. one at the gym at lunch and another at home tonight), the Coach builds the sooner one and tells you so plainly, inviting you to ask again for the other — it never silently drops the second. Short follow-ups work too: if the Coach offers to build something and you answer **"yes"/"sì"** (or "create it", "redo it shorter"), that goes straight to the builder. The card **stays in your chat history** — reload the app and it's still there, button included. A limit-bouldering line on the card shows **today's limit target** (e.g. "limit 7A+–7B · Kilter") — the same one the player will show when you tap the button. On a card from an earlier day the target is hidden: it is worked out again for the day you actually play. The session honors the time you asked for (a 60-minute request composes ~60 minutes of work), and if some requested focus has no equipment-compatible exercises where you are, the Coach says so instead of quietly composing less.
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

### Getting back in

Your account is tied to the email address you signed up with, and your training data lives on the server — not on the phone. If you reinstall the app, switch device, or the iOS PWA clears its local data, **sign in with the same email** and everything is there.

> **Note (2026-08-02):** earlier versions of this guide described a `CLIMB-XXXX-XXXX` recovery code stored in Settings. That flow was replaced by email sign-in; B320 removed the last leftovers of it (the welcome-screen link and the page behind it). If you are locked out, sign in with your original email — or restore from the export file below.

### "I tap Sign in and nothing happens"

Sign-in is handled by an external service on `clerk.climbagent.app`. Some
networks never reach it: corporate Wi-Fi and VPNs that block unknown
subdomains, and privacy extensions whose blocklists match on `clerk`. When that
happens the sign-in page now says so instead of sitting blank (B339).

To confirm it is the network and not the app, open
`https://clerk.climbagent.app/v1/environment` in the same browser. If it returns
JSON, the block is elsewhere; if it fails, try mobile data, another browser, or
pausing the extension.

### Export / Import

In **Settings**, you can:
- **Export**: Download your full training state as a JSON file. Use this as a backup.
- **Import**: Upload a previously exported state to restore your data.

---

## 18b. Subscription & Free Trial

> **If billing is paused, none of this applies.** When **Settings → Subscription** reads **Free**, the app is free for everyone: nothing to pay, nothing to manage, no trial counting down, and no training action can lock. The rest of this section describes how it works when billing is switched back on.

Your first 15 days are a **free trial — no card required**. It starts automatically the moment you finish onboarding: you land on Today with the trial already running, nothing to click.

- While trialing, a banner shows how many days remain. If you haven't added a payment method, the banner offers **Add payment method** — it opens Stripe's secure billing portal.
- If the trial ends **without** a card on file, nothing is charged: access to training actions simply locks, and you can subscribe whenever you're ready. **Your training data is safe** — plans, history, and logs are all preserved.
- If the trial ends **with** a card on file, the subscription starts automatically. Cancel anytime from **Settings → Manage subscription**.
- The free trial is one per account. If yours has already ended, subscribing restarts access immediately (billed from day one).

---

## 19. Need Help?

- **Equipment requests**: If you have non-standard equipment you'd like integrated into your plan, email **[your email]** with details.
- **Bug reports**: Use the **What's Next** page to submit feedback, or email directly.
- **Feature requests**: Vote and comment on the **What's Next** page — your input shapes what gets built next.

---

*climb-agent is built on peer-reviewed climbing training science: Hörst, Lattice Training, Eva López, Tyler Nelson, and more. No bro-science. No guessing. Train better, not more.*
