/** Guide content — all 19 sections from user_guide_v1.md (A-GUIDE). */

import type { ReactNode } from "react";

export interface GuideSection {
  id: string;
  title: string;
  searchText: string;
  body: ReactNode;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function P({ children }: { children: ReactNode }) {
  return <p className="text-sm text-zinc-300 leading-relaxed mb-3">{children}</p>;
}
function B({ children }: { children: ReactNode }) {
  return <strong className="text-zinc-100">{children}</strong>;
}
function H3({ children }: { children: ReactNode }) {
  return <h3 className="text-sm font-semibold text-zinc-200 mt-4 mb-2">{children}</h3>;
}
function Ul({ children }: { children: ReactNode }) {
  return <ul className="list-disc list-inside space-y-1 text-sm text-zinc-300 mb-3">{children}</ul>;
}
function Li({ children }: { children: ReactNode }) {
  return <li className="leading-relaxed">{children}</li>;
}
function Dont({ children }: { children: ReactNode }) {
  return <p className="text-sm text-zinc-500 italic mb-3">{children}</p>;
}
function Flow({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1 text-sm text-zinc-300 mb-3">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <span className="text-zinc-500">&rarr;</span>}
          <span className="font-medium text-zinc-200">{item}</span>
        </span>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sections                                                            */
/* ------------------------------------------------------------------ */

export const GUIDE_SECTIONS: GuideSection[] = [
  {
    id: "how-the-plan-works",
    title: "How the Plan Works",
    searchText:
      "assessment goal macrocycle weekly plan session exercises pipeline 5-axis profile finger strength pulling power endurance technique deterministic feedback loop closed-loop 3-pass algorithm planner",
    body: (
      <>
        <P>climb-agent builds your training plan through a pipeline:</P>
        <Flow items={["Assessment", "Goal", "Macrocycle", "Weekly Plan", "Session", "Exercises"]} />
        {/* IMAGE: plan_page — screenshot of Plan page showing radar chart + macrocycle timeline */}
        <Ul>
          <Li><B>Assessment</B>: During onboarding, you provide your climbing experience, grades, test results, and self-reported weaknesses. This generates a 5-axis profile (finger strength, pulling strength, power endurance, technique, endurance) scored 0&ndash;100 <B>against your goal grade</B> &mdash; see &ldquo;Reading the radar&rdquo; below.</Li>
          <Li><B>Goal</B>: You set a target grade and a deadline. The engine calculates how many weeks you have and what needs to improve.</Li>
          <Li><B>Macrocycle</B>: A periodized plan (typically 10&ndash;13 weeks, minimum 9) is generated, divided into phases. Each phase has a specific physiological purpose.</Li>
          <Li><B>Weekly Plan</B>: Each week, the planner selects sessions based on your current phase, available days, locations, and equipment. It runs a 3-pass algorithm: primary sessions first, then complementary work, then tests when due.</Li>
          <Li><B>Session Resolution</B>: Each session is resolved into concrete exercises with sets, reps, load, rest times, and tempo &mdash; all calculated from your current working loads.</Li>
          <Li><B>Feedback Loop</B>: After each session, your feedback drives the closed-loop adaptation system. Loads adjust up or down. Every ~6 weeks, test sessions re-assess your profile.</Li>
        </Ul>
        <P><B>This is fully deterministic.</B> Same inputs always produce the same outputs. No randomness, no AI guessing &mdash; just rules, catalogs, and your data.</P>
      </>
    ),
  },
  {
    id: "reading-the-radar",
    title: "Reading the Radar",
    searchText:
      "radar chart 5-axis profile assessment score 0-100 readiness for goal grade at target benchmark elite comparison toggle greyed axis finger strength pulling strength tooltip info what does 100 mean",
    body: (
      <>
        <P>
          The five-axis radar at the top of <B>Plan</B> is scored <B>against your goal
          grade</B>, not against an absolute maximum &mdash; the subtitle says so
          (&ldquo;Readiness for 8a+&rdquo;). A score of 100 means you already meet the
          benchmark that grade typically demands, so that axis shows <B>&#10003; At
          target</B> instead of a number. Two climbers with identical strength but
          different goals see different radars. That is intended.
        </P>
        <P>
          Tap the <B>&#9432;</B> next to any axis for what it measures, what it is scored
          against, and &mdash; when the score is low &mdash; what training moves it.
        </P>
        <P>
          <B>Goal vs Elite.</B> If you have entered a max hang or a weighted pull-up, a
          <B> Goal / Elite </B> toggle appears above the radar. Goal is the default and is
          the scale the rest of the app uses. Elite re-draws the same axes against fixed
          benchmarks for climbers operating around 8b&ndash;9a, so you can see how far the
          top of the sport is instead of how close your own goal is. <B>It changes nothing
          but the picture</B> &mdash; your plan, your domain weights and your progression
          are always computed from the Goal scale.
        </P>
        <P>
          Only <B>Finger Strength</B> and <B>Pulling Strength</B> have an elite benchmark
          today. Endurance, Power Endurance and Technique appear greyed with an em dash,
          because there is no benchmark for them we would stand behind. A greyed axis means
          &ldquo;we have no ruler&rdquo;, never &ldquo;you score zero&rdquo;.
        </P>
        <P>
          The same radar and the same toggle appear on the public <B>/assessment</B> page,
          where anyone can get a profile without an account. Nothing entered there is
          stored.
        </P>
      </>
    ),
  },
  {
    id: "training-phases",
    title: "Training Phases",
    searchText:
      "macrocycle phase base endurance strength power performance deload periodization Hörst ARC aerobic capillary max hangs weighted pull-ups campus bouldering 4x4 intervals pump tapering recovery supercompensating",
    body: (
      <>
        <P>Your macrocycle follows the H&ouml;rst 4-3-2-1 periodization model. Each phase builds on the previous one. <B>Trust the progression.</B></P>

        <H3>Base / Endurance (4&ndash;6 weeks)</H3>
        <P><B>What you&apos;ll do</B>: ARC training, easy sustained climbing, repeaters, technique drills, general conditioning.</P>
        <P><B>What it feels like</B>: Easy. You&apos;ll think &ldquo;this is too easy.&rdquo; That&apos;s normal. This phase builds the aerobic base that everything else depends on.</P>
        <Dont>Don&apos;t: Push hard, add extra bouldering at your limit, or skip sessions because they feel easy.</Dont>

        <H3>Strength &amp; Power (2&ndash;3 weeks)</H3>
        <P><B>What you&apos;ll do</B>: Max hangs, weighted pull-ups, limit bouldering, campus work (if qualified), power exercises.</P>
        <P><B>What it feels like</B>: Hard. Low reps, long rests, high intensity. Sessions are shorter but more demanding neurally.</P>
        <Dont>Don&apos;t: Add volume. Long rest periods are not wasted time &mdash; your nervous system needs them.</Dont>

        <H3>Power Endurance (2&ndash;3 weeks)</H3>
        <P><B>What you&apos;ll do</B>: 4&times;4 intervals, linked boulders, route intervals, PE circuits.</P>
        <P><B>What it feels like</B>: The hardest phase. High intensity AND high volume. You&apos;ll feel tired. That&apos;s the point.</P>
        <Dont>Don&apos;t: Skip rest days. Recovery between sessions is critical in this phase.</Dont>

        <H3>Performance (2 weeks)</H3>
        <P><B>What you&apos;ll do</B>: Reduced volume, maintained intensity. Projecting, route practice, quality climbing.</P>
        <P><B>What it feels like</B>: You&apos;re tapering. Volume drops 40&ndash;60%, but intensity stays high. This is where you send.</P>
        <Dont>Don&apos;t: Panic about the reduced volume. Less is more in this phase.</Dont>

        <H3>Deload (1 week)</H3>
        <P><B>What you&apos;ll do</B>: Easy climbing, stretching, light movement. Active recovery.</P>
        <P><B>What it feels like</B>: A break. Enjoy it. Your body is recovering and supercompensating.</P>
        <Dont>Don&apos;t: &ldquo;Just do a quick session&rdquo; at full intensity. Deload means deload.</Dont>
      </>
    ),
  },
  {
    id: "your-weekly-routine",
    title: "Your Weekly Routine",
    searchText:
      "monday sunday today page week page daily workflow done skip undo mark session guided",
    body: (
      <>
        <P>Every week runs <B>Monday to Sunday</B>. The planner assigns sessions to the days you&apos;re available, respecting your locations and equipment.</P>
        <P><B>The Today page</B> shows what&apos;s planned for today. <B>The Week page</B> shows the full 7-day grid with all sessions.</P>
        {/* IMAGE: today_page — screenshot of Today page with session cards */}
        <P>Your daily workflow:</P>
        <Ul>
          <Li>Open the app &rarr; <B>Today</B> shows your session(s)</Li>
          <Li>Tap a session to see the full exercise list with loads</Li>
          <Li>Start the <B>Guided Session</B> for step-by-step coaching, or train independently</Li>
          <Li>When done, tap <B>Done</B> and give feedback</Li>
          <Li>If you can&apos;t train, tap <B>Skip</B> &mdash; the system adapts</Li>
        </Ul>
        <P><B>Done</B> and <B>Skip</B> are always reversible — tap <B>Undo completion</B> or <B>Undo skip</B> to reverse &mdash; don&apos;t worry about misclicks.</P>
      </>
    ),
  },
  {
    id: "guided-session",
    title: "Guided Session",
    searchText:
      "guided session timer beeps voice cues process cue prescription sets reps load rest tempo skip exercise adjust weight iOS Safari wall-clock audio",
    body: (
      <>
        <P>The guided session is your in-gym companion. It walks you through every exercise step by step.</P>
        {/* IMAGE: guided_session — screenshot of guided session with exercise timer */}
        <H3>How it works</H3>
        <Ul>
          <Li>Each exercise is displayed one at a time with its full prescription: sets, reps, load, rest, grip type, tempo</Li>
          <Li><B>Timers</B> count down rest periods, hang times, and work intervals automatically</Li>
          <Li><B>Beeps</B> alert you at 3-2-1 before each work phase starts</Li>
          <Li><B>Voice cues</B> provide encouragement and phase transitions</Li>
          <Li>A <B>process cue</B> banner reminds you what to focus on today</Li>
          <Li>On the <B>Plan</B> page, each phase has an expandable &ldquo;About this phase&rdquo; section</Li>
        </Ul>
        <P><B>iOS Safari note</B>: The timer uses a wall-clock engine designed to survive background suspension. Audio cues require one initial tap to activate.</P>
        <H3>You can always</H3>
        <Ul>
          <Li>Skip an exercise within the guided session</Li>
          <Li>Adjust the weight/load if the prescribed load isn&apos;t available</Li>
          <Li>Exit the guided session and mark the session manually</Li>
        </Ul>
      </>
    ),
  },
  {
    id: "giving-feedback",
    title: "Giving Feedback",
    searchText:
      "feedback very easy easy ok hard very hard progression closed-loop loads increase decrease honest",
    body: (
      <>
        <P>After completing a session, you&apos;re asked for feedback on each exercise:</P>
        {/* IMAGE: feedback_dialog — screenshot of feedback dialog with 5 options */}
        <Ul>
          <Li><B>Very Easy</B> &mdash; Could do much more</Li>
          <Li><B>Easy</B> &mdash; Comfortable, could add load</Li>
          <Li><B>OK</B> &mdash; Appropriate challenge</Li>
          <Li><B>Hard</B> &mdash; Struggled but completed</Li>
          <Li><B>Very Hard</B> &mdash; Barely completed or had to reduce</Li>
        </Ul>
        <P><B>This feedback directly drives your progression.</B> The closed-loop system adjusts loads for next time:</P>
        <Ul>
          <Li>&ldquo;Very Easy&rdquo; or &ldquo;Easy&rdquo; &rarr; loads increase next session</Li>
          <Li>&ldquo;OK&rdquo; &rarr; loads stay the same</Li>
          <Li>&ldquo;Hard&rdquo; &rarr; loads stay or decrease slightly</Li>
          <Li>&ldquo;Very Hard&rdquo; &rarr; loads decrease</Li>
        </Ul>
        <P><B>Be honest.</B> The system only works if your feedback is accurate. There&apos;s no benefit to saying &ldquo;OK&rdquo; when it was &ldquo;Very Hard.&rdquo;</P>
      </>
    ),
  },
  {
    id: "test-sessions",
    title: "Test Sessions",
    searchText:
      "test session 6 weeks max hang 7s repeater weighted pull-up bodyweight gate hip flexibility loading pin LP baselines profile radar recalibrate",
    body: (
      <>
        <P>Every <B>~6 weeks</B>, the system schedules test sessions. These re-measure your baselines and update your 5-axis profile.</P>
        <H3>The tests</H3>
        <Ul>
          <Li><B>Max Hang (7s)</B>: Maximum weight on a 20mm edge for 7 seconds. Measures finger max strength.</Li>
          <Li><B>Repeater (7:3 to failure)</B>: Reps sustained at 60% of max hang. Measures finger endurance.</Li>
          <Li><B>Weighted Pull-Up (2RM)</B>: Maximum added weight for 2 reps. Estimates 1RM. Measures pulling strength.</Li>
          <Li><B>Bodyweight Pull-Up Gate</B>: If you&apos;ve never done the weighted test, checks if you can do 15+ BW pull-ups first.</Li>
          <Li><B>Hip Flexibility</B>: Straddle measurement in cm. Informs mobility prescription.</Li>
        </Ul>
        <P>If you use a <B>loading pin</B> instead of a hangboard, the system automatically substitutes the finger tests with LP variants.</P>
        <P><B>Why they matter</B>: Without fresh test data, the system keeps using old baselines. Tests are the system recalibrating itself.</P>
        <P><B>After a test session</B>: Your profile radar updates, working loads recalculate, and the plan adjusts its emphasis.</P>
      </>
    ),
  },
  {
    id: "regenerating-your-plan",
    title: "Regenerating Your Plan",
    searchText:
      "regenerate assessment macrocycle settings profile goal restart danger zone immutable past sessions",
    body: (
      <>
        <P>You can regenerate your plan from <B>Settings</B>:</P>
        <Ul>
          <Li><B>Edit Profile or Goal</B>: When you save changes, the system automatically recomputes your 5-axis assessment and offers to regenerate the macrocycle.</Li>
          <Li><B>Restart Macrocycle</B> (Danger Zone): Creates a new macrocycle from week 1. Use when you set a completely new goal or the current macrocycle ends.</Li>
        </Ul>
        <H3>When to regenerate</H3>
        <Ul>
          <Li>After completing all tests and the plan feels misaligned</Li>
          <Li>After a long break (2+ weeks off)</Li>
          <Li>When changing your primary goal or deadline</Li>
          <Li>When you make significant equipment or location changes</Li>
        </Ul>
        <H3>When NOT to regenerate</H3>
        <Ul>
          <Li>After a bad week &mdash; the closed-loop adapts automatically</Li>
          <Li>Mid-phase because you&apos;re impatient &mdash; give the phase time to work</Li>
          <Li>Because one session was too easy or too hard &mdash; feedback handles this</Li>
        </Ul>
        <P><B>Important</B>: Past sessions are <B>never modified</B> &mdash; they&apos;re immutable history. Only future weeks are affected.</P>
      </>
    ),
  },
  {
    id: "modifying-a-session",
    title: "Modifying a Session",
    searchText:
      "modify session add exercise skip remove change load prescription replan session card menu",
    body: (
      <>
        <H3>Adding an Exercise</H3>
        <P>From the <B>Today</B> or <B>Week</B> page, tap a session card&apos;s menu to add exercises. The system shows compatible exercises filtered by your equipment.</P>
        <H3>Skipping an Exercise</H3>
        <P>Within the guided session, you can skip any exercise. If you consistently skip an exercise, your feedback will signal the system to adjust.</P>
        <H3>Changing Load</H3>
        <P>If the prescribed load isn&apos;t available, adjust within the guided session. The system adapts based on your feedback.</P>
        <H3>Session-Level Changes</H3>
        <P>For bigger changes (wrong session type, wrong day), use the <B>Replan</B> feature instead.</P>
      </>
    ),
  },
  {
    id: "adding-extra-sessions",
    title: "Adding Extra Sessions",
    searchText:
      "quick-add supplementary training upper body legs gym heavy conditioning pulling free session extra",
    body: (
      <>
        <H3>Quick-Add (Climbing Sessions)</H3>
        <P>From the <B>Today</B> or <B>Week</B> view, tap the <B>+</B> button to open the Quick-Add dialog. The system suggests sessions compatible with your current phase and location/equipment.</P>
        <P>These are full engine sessions &mdash; resolved with exercises, loads, and prescriptions. Their load counts toward your weekly total.</P>
        <H3>Supplementary Training</H3>
        <P>The Quick-Add dialog also offers supplementary sessions &mdash; non-climbing work you can add any time:</P>
        <Ul>
          <Li><B>Upper Body</B> &mdash; Push/antagonist work (home)</Li>
          <Li><B>Legs (Home)</B> &mdash; Squat/hinge/unilateral</Li>
          <Li><B>Legs (Gym)</B> &mdash; Full leg session with equipment</Li>
          <Li><B>Heavy Conditioning</B> &mdash; Full-body conditioning (gym)</Li>
          <Li><B>Pulling</B> &mdash; Dedicated pulling session (gym)</Li>
        </Ul>
        <P>Supplementary sessions count as an active training day and their load counts toward your weekly total. They do not trigger replanning or macrocycle adaptation.</P>
        <H3>Free Session</H3>
        <P>You can also add a free session from Quick-Add.</P>
      </>
    ),
  },
  {
    id: "replanning-your-week",
    title: "Replanning Your Week",
    searchText:
      "replan dialog change location intent rest outdoor strength endurance technique projecting ripple effects skip session week view",
    body: (
      <>
        <P>The <B>Replan Dialog</B> lets you make changes to your weekly plan without regenerating everything. Access it from the <B>Week</B> view by tapping a day.</P>
        {/* IMAGE: replan_dialog — screenshot of replan dialog with intent options */}
        <H3>What you can do</H3>
        <Ul>
          <Li><B>Change location</B>: Switch a day from home to gym, gym to outdoor, etc.</Li>
          <Li><B>Change intent</B>: Override what kind of session you want (strength, endurance, technique, projecting, rest, recovery, power endurance, or &ldquo;hard&rdquo; for auto-select)</Li>
          <Li><B>Go outdoor</B>: Switch to an outdoor intent (easy outdoor, projecting, volume routes, boulder outdoor)</Li>
          <Li><B>Rest</B>: Set the intent to &ldquo;Rest&rdquo; to turn a training day into a rest day</Li>
        </Ul>
        <P>The replanner handles <B>ripple effects</B> &mdash; when you change a day&apos;s intent, it adjusts surrounding days to maintain proper recovery spacing.</P>
        <P><B>Skipping a session</B> is always OK. The system is designed for real life. Don&apos;t add make-up sessions to &ldquo;compensate&rdquo; &mdash; that leads to overtraining.</P>
      </>
    ),
  },
  {
    id: "free-climbing-sessions",
    title: "Free Sessions",
    searchText:
      "free session surfaces gym boulder kilter moonboard board routes core circuit template mode volume projecting endurance technique flash sent attempted onsight redpoint context standalone add-on replacement load score phase compatibility",
    body: (
      <>
        <P>Free Sessions let you log unstructured climbing &mdash; bouldering, board sessions, or route climbing outside the planned training.</P>
        {/* IMAGE: free_session_surfaces — screenshot of free session surface picker */}
        <H3>Surfaces</H3>
        <P>Six surfaces available: Gym Boulder, Kilter Board, MoonBoard, Other Board, Gym Routes (Lead/Top-rope), and Core Circuit.</P>
        <H3>Two Modes</H3>
        <P><B>Template Mode</B>: Choose a preset and get structure.</P>
        <Ul>
          <Li><B>Volume</B> &mdash; Many problems at moderate grade, moderate rest</Li>
          <Li><B>Projecting</B> &mdash; Few attempts at your limit, long rest</Li>
          <Li><B>Endurance</B> &mdash; Many easy problems, short rest</Li>
          <Li><B>Technique</B> &mdash; Easy problems, focus on movement quality</Li>
        </Ul>
        <P>Each preset shows a <B>phase compatibility badge</B> (recommended / caution / not recommended) so you know what fits your current phase.</P>
        <P><B>Free Mode</B>: Just climb and log. You get a phase-appropriate tip and nothing else.</P>
        <H3>Logging Climbs</H3>
        <P>For each climb: grade, status (Flash / Sent / Attempted), and attempts. For lead routes: style (Onsight / Flash / Redpoint / Project).</P>
        <H3>Context</H3>
        <Ul>
          <Li><B>Planned session not done yet</B>: Replace it or add on top</Li>
          <Li><B>Planned session already done</B>: Automatically tagged as add-on</Li>
          <Li><B>Rest day / no session</B>: Standalone</Li>
        </Ul>
        <H3>Load</H3>
        <P>Free sessions generate a load score based on climbs, difficulty relative to your max, and send rate. This feeds into your weekly total.</P>
      </>
    ),
  },
  {
    id: "next-weeks-availability",
    title: "Next Week's Availability",
    searchText:
      "weekly override availability days location gym home outdoor settings temporary planner monday",
    body: (
      <>
        <P>Your default availability is set in <B>Settings</B>. But real life changes week to week.</P>
        <P><B>Weekly Override</B>: From the <B>Week</B> view, you can override availability for any upcoming week. Tap the availability section to:</P>
        <Ul>
          <Li>Toggle days on/off</Li>
          <Li>Change location for specific days (gym, home, outdoor)</Li>
          <Li>Select which gym for each day</Li>
        </Ul>
        <P>Overrides are temporary &mdash; they only apply to that specific week. Your default settings remain unchanged.</P>
        <P><B>Tip</B>: Set your overrides for next week before Monday. The planner generates the new week plan on Monday morning based on your availability at that point.</P>
      </>
    ),
  },
  {
    id: "locations-and-equipment",
    title: "Locations & Equipment",
    searchText:
      "locations equipment gym home hangboard campus board pull-up bar weights kettlebell bench homewall boulder sessions required_equipment planner settings",
    body: (
      <>
        <P>The plan is built around <B>what equipment you have</B>, not where you are. The planner only assigns sessions you can actually do.</P>
        <H3>Setting Up</H3>
        <P>In <B>Settings &rarr; Locations</B>, configure:</P>
        <Ul>
          <Li>Your gym(s): name + available equipment (hangboard, campus board, pull-up bar, weights, kettlebell, bench, etc.)</Li>
          <Li>Your home setup: what equipment you have at home</Li>
          <Li>Homewall: if you have a homewall, boulder sessions become available for home days</Li>
        </Ul>
        <H3>How It Works</H3>
        <P>The planner checks each day&apos;s location and available equipment, then selects only sessions whose required equipment is a subset of what you have.</P>
      </>
    ),
  },
  {
    id: "outdoor-sessions",
    title: "Outdoor Sessions",
    searchText:
      "outdoor climbing crag spot discipline lead boulder log conditions humidity rock wind stats grade histogram session history",
    body: (
      <>
        <P>Outdoor climbing is tracked separately from indoor training.</P>
        <H3>Setting Up Spots</H3>
        <P>In <B>Settings &rarr; Outdoor Spots</B>, add your regular crags with name, discipline (lead, boulder, or both), and typical days you visit.</P>
        <H3>Logging</H3>
        <P>From the <B>Outdoor</B> page: select the spot, log date, discipline, grades climbed, record conditions (humidity, rock condition, wind), and add notes.</P>
        <P>The planner knows about your outdoor days and plans around them &mdash; no indoor sessions are scheduled on outdoor days.</P>
        <H3>Stats</H3>
        <P>The Outdoor page shows: per-spot breakdown, grade histogram, session history, and conditions trends.</P>
      </>
    ),
  },
  {
    id: "weekly-report",
    title: "Weekly Report",
    searchText:
      "weekly report adherence load difficulty distribution progression table free session summary feedback hard easy ok",
    body: (
      <>
        <P>The <B>Weekly Report</B> (Reports tab) gives you a snapshot of your training week:</P>
        {/* IMAGE: weekly_report — screenshot of weekly report page */}
        <Ul>
          <Li><B>Adherence</B>: Planned sessions completed vs. skipped</Li>
          <Li><B>Load</B>: Total training load (engine sessions + free sessions + supplementary)</Li>
          <Li><B>Difficulty Distribution</B>: How exercises felt across the week</Li>
          <Li><B>Progression Table</B>: Which exercises progressed, regressed, or stayed flat</Li>
          <Li><B>Free Session Summary</B>: Climbs, max grade, send rate, duration</Li>
        </Ul>
        <H3>How to read it</H3>
        <Ul>
          <Li>Adherence &gt; 80% is great. Below 60% consistently &mdash; adjust your availability.</Li>
          <Li>Load should trend gradually upward within a phase, with drops during deload.</Li>
          <Li>Feedback clustering around &ldquo;OK&rdquo; is a healthy distribution.</Li>
        </Ul>
      </>
    ),
  },
  {
    id: "tabata-timer",
    title: "Tabata Timer",
    searchText:
      "tabata timer interval prepare work rest cycles sets cool down progress ring beeps voice fullscreen expand",
    body: (
      <>
        <P>The <B>Tabata</B> timer (in the More menu) is a standalone configurable interval timer &mdash; use it for any timed protocol.</P>
        {/* IMAGE: tabata_timer — screenshot of tabata timer in execution mode */}
        <H3>Parameters (all editable)</H3>
        <Ul>
          <Li>Prepare time (default 10s)</Li>
          <Li>Work time (default 40s)</Li>
          <Li>Rest time (default 10s)</Li>
          <Li>Cycles per set (default 8)</Li>
          <Li>Sets (default 1)</Li>
          <Li>Rest between sets (default 60s)</Li>
          <Li>Cool down (default 0s)</Li>
        </Ul>
        <P>During execution: animated progress ring, phase-colored backgrounds (teal for work, blue for rest), 3-2-1 countdown beeps, and voice encouragement. Expand mode gives you a fullscreen display.</P>
      </>
    ),
  },
  {
    id: "trust-the-process",
    title: "Trust the Process",
    searchText:
      "overtrain rest days deload volume increase injury recovery adaptation feedback very hard overreaching fatigue plateau",
    body: (
      <>
        <P>The biggest risk for motivated climbers isn&apos;t under-training &mdash; it&apos;s doing too much.</P>
        <H3>Key principles</H3>
        <Ul>
          <Li><B>Rest days are training days.</B> Adaptation happens during recovery, not during the session.</Li>
          <Li><B>Don&apos;t add sessions to &ldquo;make up&rdquo; for missed days.</B> The system already adapts. Adding volume creates load spikes.</Li>
          <Li><B>Deload is not optional.</B> Your body needs a full deload week to consolidate gains.</Li>
          <Li><B>Follow the phase.</B> If Base phase feels easy, that&apos;s correct. Don&apos;t add limit bouldering because you&apos;re bored.</Li>
          <Li><B>Weekly volume increases should stay under 10%.</B> Keep an eye on your weekly report.</Li>
          <Li><B>If you feel consistently beaten up</B>, give honest feedback and the system will reduce loads.</Li>
        </Ul>
        <H3>Signs you might be overreaching</H3>
        <Ul>
          <Li>Performance declining over 2+ weeks</Li>
          <Li>Sessions feeling consistently harder than expected</Li>
          <Li>Completing fewer sessions than usual</Li>
          <Li>General fatigue that doesn&apos;t resolve with a rest day</Li>
        </Ul>
        <P>If this happens, give honest feedback (&ldquo;Hard&rdquo; / &ldquo;Very Hard&rdquo;) and the closed-loop system will reduce your loads. Consider taking an extra rest day or moving your deload forward.</P>
      </>
    ),
  },
  {
    id: "backup-and-recovery",
    title: "Backup & Recovery",
    searchText:
      "backup recovery lost access sign in email export import JSON settings restore data PWA reinstall",
    body: (
      <>
        <H3>Getting back in</H3>
        <P>Your account is tied to the email address you signed up with, and your training data lives on the server &mdash; not on your phone. If you reinstall the app, switch device, or the iOS PWA clears its local data, <B>sign in with the same email</B> and everything is there.</P>
        <H3>Export / Import</H3>
        <P>In <B>Settings</B>, you can:</P>
        <Ul>
          <Li><B>Export</B>: Download your full training state as a JSON file. Use this as a backup.</Li>
          <Li><B>Import</B>: Upload a previously exported state to restore your data.</Li>
        </Ul>
      </>
    ),
  },
  {
    id: "need-help",
    title: "Need Help?",
    searchText:
      "help feedback bug report feature request what's next page email equipment",
    body: (
      <>
        <Ul>
          <Li><B>Bug reports</B>: Use the <B>What&apos;s Next</B> page to submit feedback, or email directly.</Li>
          <Li><B>Feature requests</B>: Vote and comment on the <B>What&apos;s Next</B> page &mdash; your input shapes what gets built next.</Li>
        </Ul>
      </>
    ),
  },
];
