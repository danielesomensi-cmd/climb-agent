// demo.jsx — climb-agent /demo page, Direction A (Editorial Dark)

const { useState, useEffect, useRef, useMemo, Fragment } = React;

// ─────────────────────────────────────────────────────────────
// Design tokens
// ─────────────────────────────────────────────────────────────
const C = {
  bg: '#0A0A0A',
  ink: '#F5F1EA',          // cream body
  inkDim: 'rgba(245,241,234,0.55)',
  inkFaint: 'rgba(245,241,234,0.32)',
  rule: 'rgba(245,241,234,0.14)',
  ruleStrong: 'rgba(245,241,234,0.28)',
  card: '#121211',
  cardInk: '#F5F1EA',
  orange: '#FF4A1C',
  orangeDim: 'rgba(255,74,28,0.15)',
};

const FONT_DISPLAY = '"Archivo Narrow", "Oswald", Impact, sans-serif';
const FONT_MONO = '"JetBrains Mono", ui-monospace, Menlo, monospace';
const FONT_BODY = '"Inter", -apple-system, system-ui, sans-serif';

// ─────────────────────────────────────────────────────────────
// Session content
// ─────────────────────────────────────────────────────────────
// Cumulative timestamps: start at 08:00, each section begins at offset
const SESSION = [
  {
    n: '01', title: 'Warmup', mins: 12, start: '08:00', tier: 'prep',
    exercises: [
      { t: 'Pulse raise / cardio', d: '1 × 3 min', desc: 'Jumping jacks, skipping, or light jog. Raise heart rate and warm the body.',
        cues: ['Nasal breathing only', 'Shoulders down, relaxed', 'Stop before you break a sweat'] },
      { t: 'Joint circles', d: '1 × 2 min', desc: 'Wrists, shoulders, hips, ankles. Slow circles, 10 reps each direction per joint.',
        cues: ['Control over speed', 'Full range of motion', 'Both directions'] },
      { t: 'Dynamic mobility', d: '1 × 4 min', desc: 'Leg swings, arm circles, thoracic rotation, Cossack squats. Use a band for leg swings if available.',
        cues: ['10 reps per movement', 'Progressive range', 'Find the end-range without forcing'] },
      { t: 'Easy traversing', d: '3 × 3 min — Rest 1:00', desc: 'Boulder 2–3 grades below your max. Focus on smooth movement and quiet feet, not difficulty.',
        cues: ['Silent feet', 'Straight arms between moves', 'Breathe through cruxes'] },
    ],
  },
  {
    n: '02', title: 'Finger Strength — Max Hangs', mins: 10, start: '08:12', tier: 'main',
    exercises: [
      { t: 'Max hangs', d: '5 × 10s hang — Rest 3:00', desc: 'Half crimp, largest comfortable edge. 5 sets × 10s hang, 3 min rest. Add weight or reduce edge size until 10s is genuinely hard.',
        cues: ['Half crimp, not full', 'Shoulders engaged, not passive', 'If you can hold 12s, add load next set', 'Stop if tendons feel sharp'] },
    ],
  },
  {
    n: '03', title: 'Weighted Pull-ups', mins: 10, start: '08:22', tier: 'main',
    exercises: [
      { t: 'Weighted pull-ups', d: '4 × 5 — Rest 3:00', desc: 'Add weight so the last rep is hard but controlled. 4 sets × 5 reps, 3 min rest.',
        cues: ['Full dead hang at bottom', 'Chin clearly over the bar', 'Slow negative (2–3s)', 'Last rep should be a grind, not a failure'] },
    ],
  },
  {
    n: '04', title: 'Projecting — Limit Bouldering', mins: 20, start: '08:32', tier: 'main',
    exercises: [
      { t: 'Limit boulder projecting', d: '4 × 3 attempts — Rest 3:00', desc: 'Pick 4 boulder problems at your limit (hardest grade you can try). 3 attempts per problem, 3 min rest between attempts.',
        cues: ['Pick problems you cannot flash', 'Rest fully between attempts', 'Quality over quantity', 'Film the crux if you can'] },
    ],
  },
  {
    n: '05', title: '4×4 Bouldering', mins: 20, start: '08:52', tier: 'main',
    exercises: [
      { t: '4×4 boulder', d: '4 × 4 problems — Rest 4:00', desc: 'Pick 4 problems 1–2 grades below your max. Climb all 4 back-to-back without rest, then rest 4 min. Repeat 4 times.',
        cues: ['Choose clean, secure problems', 'No falling — downclimb if needed', 'Keep breathing rhythmic', 'This is power endurance, not strength'] },
    ],
  },
  {
    n: '06', title: 'Core Circuit', mins: 10, start: '09:12', tier: 'support',
    exercises: [
      { t: 'Core circuit', d: '3 × see notes — Rest 1:00', desc: '3 rounds: front lever raises or hanging knee raises × 8, side plank × 30s each side, hollow body hold × 30s. 1 min rest between rounds.',
        cues: ['Brace — don\'t just hold', 'Ribs down, pelvis neutral', 'Full exhale at the top of each rep'] },
    ],
  },
  {
    n: '07', title: 'Antagonist Work', mins: 10, start: '09:22', tier: 'support',
    exercises: [
      { t: 'Antagonist circuit', d: '3 × see notes — Rest 1:00', desc: '3 rounds: push-ups × 12 (or dips), band pull-aparts × 15, reverse wrist curls × 12. 1 min rest between rounds.',
        cues: ['Push the opposite direction of climbing', 'Slow and controlled', 'Full range, no bouncing'] },
    ],
  },
  {
    n: '08', title: 'Stretching & Cooldown', mins: 10, start: '09:32', tier: 'prep',
    exercises: [
      { t: 'Forearm flexor + extensor stretch', d: '2 × 30s each', desc: 'Flexor: arm extended, palm down, pull fingers toward you. Extensor: palm up, pull fingers down.',
        cues: ['Gentle pull, no pain', 'Breathe into the stretch'] },
      { t: 'Shoulder stretch', d: '2 × 30s each side', desc: 'Cross-body and doorframe. Both sides.',
        cues: ['Relax the shoulder down', 'Don\'t force the range'] },
      { t: 'Hip flexor stretch', d: '2 × 30s each side', desc: 'Low lunge position. Tuck pelvis under to deepen the stretch.',
        cues: ['Squeeze the glute of the back leg', 'Tall through the spine'] },
      { t: 'Thoracic spine rotation', d: '2 × 30s each side', desc: 'Seated or on all fours. Rotate from mid-back, not the lower back.',
        cues: ['Fix the hips', 'Lead with the ribcage'] },
      { t: 'Hamstring stretch', d: '2 × 30s each side', desc: 'Seated forward fold or standing. Keep the back straight — hinge from the hips.',
        cues: ['Hinge, don\'t round', 'Soft knees if needed'] },
      { t: 'Deep breathing', d: '1 × 1 min', desc: 'Inhale 4s, hold 4s, exhale 6s. Close your eyes.',
        cues: ['Longer exhale than inhale', 'Nasal in, mouth or nasal out'] },
    ],
  },
];

// Total sections + 09 = end-of-session marker (editorial closure)
const TOTAL_MIN = SESSION.reduce((a,s) => a + s.mins, 0);

// ─────────────────────────────────────────────────────────────
// Small atoms
// ─────────────────────────────────────────────────────────────
function Mono({ children, style = {}, size = 10, color = C.inkDim, weight = 500 }) {
  return (
    <span style={{
      fontFamily: FONT_MONO, fontSize: size, letterSpacing: '0.08em',
      textTransform: 'uppercase', color, fontWeight: weight,
      fontFeatureSettings: '"tnum" 1, "ss01" 1', ...style,
    }}>{children}</span>
  );
}

function HairRule({ color = C.rule, style = {} }) {
  return <div style={{ height: 1, background: color, width: '100%', ...style }} />;
}

function Chevron({ open, size = 10, color = C.inkDim }) {
  return (
    <svg width={size} height={size} viewBox="0 0 10 10" style={{
      transition: 'transform 200ms ease', transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
    }}>
      <path d="M3 2 L7 5 L3 8" stroke={color} strokeWidth="1.2" fill="none" strokeLinecap="square" />
    </svg>
  );
}

function TriangleMark({ size = 10, color = C.orange }) {
  return (
    <svg width={size} height={size} viewBox="0 0 10 10">
      <path d={`M5 1 L9 8 L1 8 Z`} fill={color} />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// Top metadata bar + header
// ─────────────────────────────────────────────────────────────
function Masthead() {
  return (
    <div style={{ background: C.bg, borderBottom: `1px solid ${C.rule}` }}>
      {/* Top utility bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 16px', borderBottom: `1px solid ${C.rule}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <TriangleMark size={8} />
          <Mono size={9.5} color={C.ink} weight={600}>CLIMB-AGENT</Mono>
          <span style={{ color: C.inkFaint, fontFamily: FONT_MONO, fontSize: 9.5 }}>·</span>
          <Mono size={9.5}>N° 001 · DEMO</Mono>
        </div>
        <Mono size={9.5}>SPEC · V26</Mono>
      </div>

      {/* Masthead title block */}
      <div style={{ padding: '18px 16px 14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
          <Mono size={9.5}>A TRAINING BRIEF</Mono>
          <Mono size={9.5}>{TOTAL_MIN} MIN · 08 PARTS</Mono>
        </div>
        <h1 style={{
          fontFamily: FONT_DISPLAY, fontWeight: 800, fontStretch: 'condensed',
          fontSize: 42, lineHeight: 0.92, letterSpacing: '-0.01em',
          color: C.ink, margin: 0, textTransform: 'uppercase',
        }}>
          Gym session,<br/>engineered.
        </h1>
        <div style={{ marginTop: 10, display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ flex: 1, height: 1, background: C.ruleStrong }} />
          <Mono size={9.5}>FIG. 00 — SESSION OVERVIEW</Mono>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Info / spec card (replaces "Sample session" yellow box)
// ─────────────────────────────────────────────────────────────
function SpecCard() {
  const rows = [
    ['CLIMBER', 'Intermediate · 6b–7a'],
    ['MODALITY', 'Lead + Boulder'],
    ['DURATION', `~${TOTAL_MIN} min · 08 parts`],
    ['STATUS', 'Preview · Not personalized'],
  ];
  return (
    <div style={{ padding: '16px' }}>
      <div style={{
        border: `1px solid ${C.ruleStrong}`, background: 'rgba(245,241,234,0.015)',
        padding: '14px 14px 12px', position: 'relative',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
          <Mono size={9.5} color={C.orange} weight={600}>FIG. 01 — SPEC SHEET</Mono>
          <Mono size={9.5}>THIS IS A PREVIEW</Mono>
        </div>
        <p style={{
          fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 20, lineHeight: 1.1,
          letterSpacing: '-0.005em', color: C.ink, margin: '0 0 12px',
          textTransform: 'none',
        }}>
          Your real plan is built around your grades, goals, days, and gym.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr', rowGap: 6, columnGap: 12 }}>
          {rows.map(([k, v], i) => (
            <Fragment key={i}>
              <Mono size={9.5} color={C.inkFaint}>{k}</Mono>
              <div style={{ fontFamily: FONT_BODY, fontSize: 12.5, color: C.ink, lineHeight: 1.25 }}>{v}</div>
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Inline timer
// ─────────────────────────────────────────────────────────────
function fmt(s) {
  const m = Math.floor(s / 60), r = s % 60;
  return `${String(m).padStart(2,'0')}:${String(r).padStart(2,'0')}`;
}

function Timer({ initial = 180, onClose }) {
  const [left, setLeft] = useState(initial);
  const [running, setRunning] = useState(true);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setLeft(l => Math.max(0, l - 1)), 1000);
    return () => clearInterval(id);
  }, [running]);
  const pct = 1 - left / initial;
  const done = left === 0;
  return (
    <div style={{
      marginTop: 10, border: `1px solid ${C.orange}`, background: '#0E0E0E',
      padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Mono size={9.5} color={C.orange} weight={600}>
          {done ? 'REST COMPLETE' : 'REST TIMER'}
        </Mono>
        <button onClick={onClose} style={{
          background: 'transparent', border: 'none', color: C.inkDim,
          fontFamily: FONT_MONO, fontSize: 9.5, letterSpacing: '0.08em',
          textTransform: 'uppercase', cursor: 'pointer', padding: 0,
        }}>CLOSE ✕</button>
      </div>
      <div style={{
        fontFamily: FONT_MONO, fontWeight: 500, fontSize: 44, lineHeight: 1,
        color: done ? C.orange : C.ink, letterSpacing: '-0.02em',
        fontFeatureSettings: '"tnum" 1',
      }}>{fmt(left)}</div>
      <div style={{ marginTop: 10, height: 2, background: 'rgba(255,74,28,0.2)', position: 'relative' }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, bottom: 0,
          width: `${pct * 100}%`, background: C.orange,
          transition: 'width 1s linear',
        }} />
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <button onClick={() => setRunning(r => !r)} style={{
          flex: 1, padding: '8px 10px', background: C.orange, color: C.bg,
          border: 'none', fontFamily: FONT_MONO, fontWeight: 600, fontSize: 10.5,
          letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
        }}>{running ? 'Pause' : 'Resume'}</button>
        <button onClick={() => { setLeft(initial); setRunning(true); }} style={{
          flex: 1, padding: '8px 10px', background: 'transparent', color: C.ink,
          border: `1px solid ${C.ruleStrong}`, fontFamily: FONT_MONO,
          fontWeight: 500, fontSize: 10.5, letterSpacing: '0.08em',
          textTransform: 'uppercase', cursor: 'pointer',
        }}>Reset</button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Exercise card
// ─────────────────────────────────────────────────────────────
function ExerciseCard({ ex, tier, idx }) {
  const [showCues, setShowCues] = useState(false);
  const [timerOn, setTimerOn] = useState(false);
  const restSec = useMemo(() => {
    const m = ex.d.match(/Rest\s+(\d+):(\d+)/i);
    if (m) return Number(m[1]) * 60 + Number(m[2]);
    const mm = ex.d.match(/(\d+)\s*min/i);
    return mm ? Number(mm[1]) * 60 : 180;
  }, [ex.d]);
  const isMain = tier === 'main';
  return (
    <div style={{ position: 'relative', padding: '0 16px', marginTop: 10 }}>
      <div style={{
        position: 'relative', background: C.card,
        borderLeft: isMain ? `3px solid ${C.orange}` : `3px solid transparent`,
        padding: '12px 14px 14px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
          <div style={{
            fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 18,
            lineHeight: 1.15, color: C.ink, letterSpacing: '-0.005em',
          }}>{ex.t}</div>
          <Mono size={9.5} color={C.inkFaint}>{String(idx + 1).padStart(2,'0')}</Mono>
        </div>
        <div style={{
          fontFamily: FONT_MONO, fontSize: 11, letterSpacing: '0.02em',
          color: isMain ? C.orange : C.ink, fontWeight: 500,
          marginBottom: 6, fontFeatureSettings: '"tnum" 1',
        }}>{ex.d}</div>
        <div style={{
          fontFamily: FONT_BODY, fontSize: 13, lineHeight: 1.45,
          color: C.inkDim,
        }}>{ex.desc}</div>

        <div style={{ display: 'flex', gap: 0, marginTop: 12, borderTop: `1px solid ${C.rule}`, paddingTop: 10 }}>
          <button onClick={() => setShowCues(s => !s)} style={{
            flex: 1, display: 'flex', alignItems: 'center', gap: 8,
            background: 'transparent', border: 'none', padding: '2px 0',
            color: C.ink, cursor: 'pointer', textAlign: 'left',
          }}>
            <Chevron open={showCues} color={C.ink} />
            <Mono size={10} color={C.ink} weight={600}>CUES</Mono>
          </button>
          <button onClick={() => setTimerOn(t => !t)} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: 'transparent', border: `1px solid ${timerOn ? C.orange : C.ruleStrong}`,
            padding: '4px 10px', color: timerOn ? C.orange : C.ink,
            cursor: 'pointer',
          }}>
            <span style={{ fontSize: 10 }}>{timerOn ? '●' : '○'}</span>
            <Mono size={10} color={timerOn ? C.orange : C.ink} weight={600}>TIMER</Mono>
          </button>
        </div>

        {showCues && ex.cues && (
          <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px dashed ${C.rule}` }}>
            <Mono size={9.5} color={C.inkFaint} style={{ marginBottom: 6, display: 'block' }}>
              COACHING CUES · {String(ex.cues.length).padStart(2,'0')}
            </Mono>
            <ol style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {ex.cues.map((c, i) => (
                <li key={i} style={{
                  display: 'grid', gridTemplateColumns: '22px 1fr', gap: 6,
                  padding: '4px 0', borderBottom: i < ex.cues.length - 1 ? `1px solid ${C.rule}` : 'none',
                }}>
                  <Mono size={9.5} color={C.orange} weight={600}>{String(i+1).padStart(2,'0')}</Mono>
                  <div style={{ fontFamily: FONT_BODY, fontSize: 12.5, color: C.ink, lineHeight: 1.35 }}>{c}</div>
                </li>
              ))}
            </ol>
          </div>
        )}

        {timerOn && <Timer initial={restSec} onClose={() => setTimerOn(false)} />}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Section header
// ─────────────────────────────────────────────────────────────
function SectionHeader({ n, title, mins, start, tier }) {
  const tierLabel = tier === 'main' ? 'MAIN WORK' : tier === 'support' ? 'SUPPORT' : 'PREP';
  return (
    <div style={{ padding: '28px 16px 6px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <Mono size={9.5} color={C.inkFaint}>
          {start} · {tierLabel}
        </Mono>
        <Mono size={9.5} color={C.inkFaint}>~{mins} MIN</Mono>
      </div>
      <HairRule color={C.ruleStrong} style={{ marginBottom: 10 }} />
      <div style={{ display: 'grid', gridTemplateColumns: '52px 1fr', gap: 10, alignItems: 'start' }}>
        <div style={{
          fontFamily: FONT_DISPLAY, fontWeight: 800, fontSize: 42,
          lineHeight: 0.85, color: tier === 'main' ? C.orange : C.ink,
          letterSpacing: '-0.02em', fontFeatureSettings: '"tnum" 1',
        }}>{n}</div>
        <h2 style={{
          fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 26,
          lineHeight: 0.95, color: C.ink, margin: '4px 0 0',
          letterSpacing: '-0.01em', textTransform: 'uppercase',
        }}>{title}</h2>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Mid-session editorial sidebar
// ─────────────────────────────────────────────────────────────
function PersonalAside() {
  return (
    <div style={{ padding: '24px 16px 4px' }}>
      <div style={{
        display: 'grid', gridTemplateColumns: '3px 1fr', gap: 12,
        padding: '2px 0',
      }}>
        <div style={{ background: C.orange, width: 3 }} />
        <div>
          <Mono size={9.5} color={C.orange} weight={600}>FIG. 02 — A NOTE ON PERSONALIZATION</Mono>
          <p style={{
            fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 22,
            lineHeight: 1.05, letterSpacing: '-0.005em',
            color: C.ink, margin: '8px 0 6px', textTransform: 'none',
          }}>
            This session is generic. Yours won't be.
          </p>
          <p style={{
            fontFamily: FONT_BODY, fontSize: 13, lineHeight: 1.5,
            color: C.inkDim, margin: '0 0 12px',
          }}>
            Your real plan is calibrated to your grades, goals, available days, and gym.
            Computed in 5 minutes. Adapts every week from your session feedback.
          </p>
          <button style={{
            display: 'inline-flex', alignItems: 'center', gap: 10,
            background: C.orange, color: C.bg, border: 'none',
            padding: '11px 14px', fontFamily: FONT_MONO, fontSize: 11,
            fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
            cursor: 'pointer',
          }}>
            Build your plan
            <span style={{ fontSize: 13, lineHeight: 1 }}>→</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Closure
// ─────────────────────────────────────────────────────────────
function Closure() {
  return (
    <div style={{ padding: '32px 16px 20px' }}>
      <HairRule color={C.ruleStrong} style={{ marginBottom: 10 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 18 }}>
        <Mono size={9.5}>END OF SESSION · 09</Mono>
        <Mono size={9.5}>~{TOTAL_MIN} MIN · COMPLETE</Mono>
      </div>
      <div style={{
        fontFamily: FONT_DISPLAY, fontWeight: 800, fontSize: 38,
        lineHeight: 0.9, color: C.ink, letterSpacing: '-0.02em',
        textTransform: 'uppercase', marginBottom: 10,
      }}>
        That's the shape<br/>of one session.
      </div>
      <p style={{
        fontFamily: FONT_BODY, fontSize: 13.5, lineHeight: 1.55,
        color: C.inkDim, margin: '0 0 20px', maxWidth: 320,
      }}>
        Every session in your real plan includes feedback tracking,
        automatic load adaptation, and week-over-week progression.
        Session logs shape next week.
      </p>
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0,
        border: `1px solid ${C.ruleStrong}`,
      }}>
        {[
          ['FEEDBACK', 'After each session'],
          ['ADAPTATION', 'Automatic, weekly'],
          ['ENGINE', 'Deterministic · No LLM'],
          ['READY', '10 min to first plan'],
        ].map(([k, v], i) => (
          <div key={i} style={{
            padding: '10px 12px',
            borderRight: i % 2 === 0 ? `1px solid ${C.ruleStrong}` : 'none',
            borderBottom: i < 2 ? `1px solid ${C.ruleStrong}` : 'none',
          }}>
            <Mono size={9} color={C.inkFaint} style={{ display: 'block', marginBottom: 4 }}>{k}</Mono>
            <div style={{ fontFamily: FONT_BODY, fontSize: 12, color: C.ink, lineHeight: 1.3 }}>{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Sticky bottom CTA
// ─────────────────────────────────────────────────────────────
function StickyCTA() {
  return (
    <div style={{
      position: 'sticky', bottom: 0, left: 0, right: 0,
      background: C.bg, borderTop: `1px solid ${C.ruleStrong}`,
      zIndex: 10,
    }}>
      <div style={{ padding: '10px 16px 14px' }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'baseline', marginBottom: 8,
        }}>
          <Mono size={9.5}>PERIODIZED. STRENGTH + SKILL.</Mono>
          <Mono size={9.5} color={C.inkFaint}>10 MIN SETUP</Mono>
        </div>
        <button style={{
          width: '100%', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', padding: '14px 16px',
          background: C.orange, color: C.bg, border: 'none',
          fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 18,
          letterSpacing: '-0.005em', cursor: 'pointer',
          textTransform: 'uppercase',
        }}>
          <span>Build my plan</span>
          <span style={{ fontSize: 20, lineHeight: 1 }}>→</span>
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────
function DemoPage() {
  return (
    <div style={{ background: C.bg, color: C.ink, minHeight: '100%', fontFamily: FONT_BODY }}>
      <Masthead />
      <SpecCard />
      {SESSION.slice(0, 4).map((s, i) => (
        <Fragment key={s.n}>
          <SectionHeader {...s} />
          {s.exercises.map((ex, j) => (
            <ExerciseCard key={j} ex={ex} tier={s.tier} idx={j} />
          ))}
        </Fragment>
      ))}
      <PersonalAside />
      {SESSION.slice(4).map((s, i) => (
        <Fragment key={s.n}>
          <SectionHeader {...s} />
          {s.exercises.map((ex, j) => (
            <ExerciseCard key={j} ex={ex} tier={s.tier} idx={j} />
          ))}
        </Fragment>
      ))}
      <Closure />
      <StickyCTA />
    </div>
  );
}

Object.assign(window, { DemoPage });
