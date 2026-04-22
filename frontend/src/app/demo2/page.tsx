"use client";

import {
  CSSProperties,
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { captureUtmOnMount, trackEvent } from "@/lib/analytics";
import { DEMO2_SESSION, DEMO2_TOTAL_MIN, type Demo2Block, type Demo2Exercise, type Tier } from "./session-data";

const VARIANT = "editorial_dark" as const;
const CTA_HREF = "/onboarding/welcome";

const C = {
  bg: "#0A0A0A",
  ink: "#F5F1EA",
  inkDim: "rgba(245,241,234,0.55)",
  inkFaint: "rgba(245,241,234,0.32)",
  rule: "rgba(245,241,234,0.14)",
  ruleStrong: "rgba(245,241,234,0.28)",
  card: "#121211",
  orange: "#FF4A1C",
} as const;

const FONT_DISPLAY = "var(--font-demo2-display), Impact, sans-serif";
const FONT_MONO = "var(--font-demo2-mono), ui-monospace, Menlo, monospace";
const FONT_BODY = "var(--font-demo2-body), system-ui, sans-serif";

function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

function parseRestSec(d: string): number {
  const m = d.match(/Rest\s+(\d+):(\d+)/i);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  const mm = d.match(/(\d+)\s*min/i);
  return mm ? Number(mm[1]) * 60 : 180;
}

function Mono({
  children,
  size = 10,
  color = C.inkDim,
  weight = 500,
  style,
}: {
  children: React.ReactNode;
  size?: number;
  color?: string;
  weight?: number;
  style?: CSSProperties;
}) {
  return (
    <span
      style={{
        fontFamily: FONT_MONO,
        fontSize: size,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color,
        fontWeight: weight,
        fontFeatureSettings: '"tnum" 1',
        ...style,
      }}
    >
      {children}
    </span>
  );
}

function HairRule({
  color = C.rule,
  style,
}: {
  color?: string;
  style?: CSSProperties;
}) {
  return <div style={{ height: 1, background: color, width: "100%", ...style }} />;
}

function Chevron({ open, color = C.inkDim }: { open: boolean; color?: string }) {
  return (
    <svg
      width={10}
      height={10}
      viewBox="0 0 10 10"
      style={{
        transition: "transform 200ms ease",
        transform: open ? "rotate(90deg)" : "rotate(0deg)",
      }}
    >
      <path
        d="M3 2 L7 5 L3 8"
        stroke={color}
        strokeWidth={1.2}
        fill="none"
        strokeLinecap="square"
      />
    </svg>
  );
}

function TriangleMark({ color = C.orange }: { color?: string }) {
  return (
    <svg width={8} height={8} viewBox="0 0 10 10">
      <path d="M5 1 L9 8 L1 8 Z" fill={color} />
    </svg>
  );
}

function Masthead() {
  return (
    <div style={{ background: C.bg, borderBottom: `1px solid ${C.rule}` }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 16px",
          borderBottom: `1px solid ${C.rule}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <TriangleMark />
          <Mono size={9.5} color={C.ink} weight={600}>
            CLIMB-AGENT
          </Mono>
          <span
            style={{
              color: C.inkFaint,
              fontFamily: FONT_MONO,
              fontSize: 9.5,
            }}
          >
            ·
          </span>
          <Mono size={9.5}>N° 001 · DEMO</Mono>
        </div>
        <Mono size={9.5}>SPEC · V26</Mono>
      </div>
      <div style={{ padding: "18px 16px 14px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: 8,
          }}
        >
          <Mono size={9.5}>A TRAINING BRIEF</Mono>
          <Mono size={9.5}>{DEMO2_TOTAL_MIN} MIN · 08 PARTS</Mono>
        </div>
        <h1
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 700,
            fontSize: 42,
            lineHeight: 0.92,
            letterSpacing: "-0.01em",
            color: C.ink,
            margin: 0,
            textTransform: "uppercase",
          }}
        >
          Gym session,
          <br />
          engineered.
        </h1>
        <div
          style={{
            marginTop: 10,
            display: "flex",
            gap: 10,
            alignItems: "center",
          }}
        >
          <div style={{ flex: 1, height: 1, background: C.ruleStrong }} />
          <Mono size={9.5}>FIG. 00 — SESSION OVERVIEW</Mono>
        </div>
      </div>
    </div>
  );
}

function SpecCard() {
  const rows: [string, string][] = [
    ["CLIMBER", "Intermediate · 6b–7a"],
    ["MODALITY", "Lead + Boulder"],
    ["DURATION", `~${DEMO2_TOTAL_MIN} min · 08 parts`],
    ["STATUS", "Preview · Not personalized"],
  ];
  return (
    <div style={{ padding: 16 }}>
      <div
        style={{
          border: `1px solid ${C.ruleStrong}`,
          background: "rgba(245,241,234,0.015)",
          padding: "14px 14px 12px",
          position: "relative",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginBottom: 10,
          }}
        >
          <Mono size={9.5} color={C.orange} weight={600}>
            FIG. 01 — SPEC SHEET
          </Mono>
          <Mono size={9.5}>THIS IS A PREVIEW</Mono>
        </div>
        <p
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 700,
            fontSize: 20,
            lineHeight: 1.1,
            letterSpacing: "-0.005em",
            color: C.ink,
            margin: "0 0 12px",
          }}
        >
          Your real plan is built around your grades, goals, days, and gym.
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "90px 1fr",
            rowGap: 6,
            columnGap: 12,
          }}
        >
          {rows.map(([k, v]) => (
            <Fragment key={k}>
              <Mono size={9.5} color={C.inkFaint}>
                {k}
              </Mono>
              <div
                style={{
                  fontFamily: FONT_BODY,
                  fontSize: 12.5,
                  color: C.ink,
                  lineHeight: 1.25,
                }}
              >
                {v}
              </div>
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

function RestTimer({
  initial,
  onClose,
}: {
  initial: number;
  onClose: () => void;
}) {
  const [left, setLeft] = useState(initial);
  const [running, setRunning] = useState(true);

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setLeft((l) => Math.max(0, l - 1)), 1000);
    return () => clearInterval(id);
  }, [running]);

  const pct = initial === 0 ? 0 : 1 - left / initial;
  const done = left === 0;

  return (
    <div
      style={{
        marginTop: 10,
        border: `1px solid ${C.orange}`,
        background: "#0E0E0E",
        padding: "12px 14px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <Mono size={9.5} color={C.orange} weight={600}>
          {done ? "REST COMPLETE" : "REST TIMER"}
        </Mono>
        <button
          onClick={onClose}
          style={{
            background: "transparent",
            border: "none",
            color: C.inkDim,
            fontFamily: FONT_MONO,
            fontSize: 9.5,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            cursor: "pointer",
            padding: 0,
          }}
        >
          CLOSE ✕
        </button>
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontWeight: 500,
          fontSize: 44,
          lineHeight: 1,
          color: done ? C.orange : C.ink,
          letterSpacing: "-0.02em",
          fontFeatureSettings: '"tnum" 1',
        }}
      >
        {fmtTime(left)}
      </div>
      <div
        style={{
          marginTop: 10,
          height: 2,
          background: "rgba(255,74,28,0.2)",
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            bottom: 0,
            width: `${pct * 100}%`,
            background: C.orange,
            transition: "width 1s linear",
          }}
        />
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <button
          onClick={() => setRunning((r) => !r)}
          style={{
            flex: 1,
            padding: "8px 10px",
            background: C.orange,
            color: C.bg,
            border: "none",
            fontFamily: FONT_MONO,
            fontWeight: 600,
            fontSize: 10.5,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            cursor: "pointer",
          }}
        >
          {running ? "Pause" : "Resume"}
        </button>
        <button
          onClick={() => {
            setLeft(initial);
            setRunning(true);
          }}
          style={{
            flex: 1,
            padding: "8px 10px",
            background: "transparent",
            color: C.ink,
            border: `1px solid ${C.ruleStrong}`,
            fontFamily: FONT_MONO,
            fontWeight: 500,
            fontSize: 10.5,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            cursor: "pointer",
          }}
        >
          Reset
        </button>
      </div>
    </div>
  );
}

function ExerciseCard({
  ex,
  tier,
  idx,
  onEngage,
}: {
  ex: Demo2Exercise;
  tier: Tier;
  idx: number;
  onEngage: () => void;
}) {
  const [showCues, setShowCues] = useState(false);
  const [timerOn, setTimerOn] = useState(false);
  const restSec = useMemo(() => parseRestSec(ex.dosage), [ex.dosage]);
  const isMain = tier === "main";
  return (
    <div style={{ position: "relative", padding: "0 16px", marginTop: 10 }}>
      <div
        style={{
          position: "relative",
          background: C.card,
          borderLeft: `3px solid ${isMain ? C.orange : "transparent"}`,
          padding: "12px 14px 14px",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            gap: 10,
            marginBottom: 4,
          }}
        >
          <div
            style={{
              fontFamily: FONT_DISPLAY,
              fontWeight: 700,
              fontSize: 18,
              lineHeight: 1.15,
              color: C.ink,
              letterSpacing: "-0.005em",
            }}
          >
            {ex.title}
          </div>
          <Mono size={9.5} color={C.inkFaint}>
            {String(idx + 1).padStart(2, "0")}
          </Mono>
        </div>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 11,
            letterSpacing: "0.02em",
            color: isMain ? C.orange : C.ink,
            fontWeight: 500,
            marginBottom: 6,
            fontFeatureSettings: '"tnum" 1',
          }}
        >
          {ex.dosage}
        </div>
        <div
          style={{
            fontFamily: FONT_BODY,
            fontSize: 13,
            lineHeight: 1.45,
            color: C.inkDim,
          }}
        >
          {ex.description}
        </div>

        <div
          style={{
            display: "flex",
            gap: 0,
            marginTop: 12,
            borderTop: `1px solid ${C.rule}`,
            paddingTop: 10,
          }}
        >
          <button
            onClick={() => {
              setShowCues((s) => !s);
              onEngage();
            }}
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: "transparent",
              border: "none",
              padding: "2px 0",
              color: C.ink,
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            <Chevron open={showCues} color={C.ink} />
            <Mono size={10} color={C.ink} weight={600}>
              CUES
            </Mono>
          </button>
          <button
            onClick={() => {
              setTimerOn((t) => !t);
              onEngage();
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: "transparent",
              border: `1px solid ${timerOn ? C.orange : C.ruleStrong}`,
              padding: "4px 10px",
              color: timerOn ? C.orange : C.ink,
              cursor: "pointer",
            }}
          >
            <span style={{ fontSize: 10 }}>{timerOn ? "●" : "○"}</span>
            <Mono size={10} color={timerOn ? C.orange : C.ink} weight={600}>
              TIMER
            </Mono>
          </button>
        </div>

        {showCues && ex.cues.length > 0 && (
          <div
            style={{
              marginTop: 10,
              paddingTop: 10,
              borderTop: `1px dashed ${C.rule}`,
            }}
          >
            <Mono
              size={9.5}
              color={C.inkFaint}
              style={{ marginBottom: 6, display: "block" }}
            >
              COACHING CUES · {String(ex.cues.length).padStart(2, "0")}
            </Mono>
            <ol style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {ex.cues.map((c, i) => (
                <li
                  key={i}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "22px 1fr",
                    gap: 6,
                    padding: "4px 0",
                    borderBottom:
                      i < ex.cues.length - 1 ? `1px solid ${C.rule}` : "none",
                  }}
                >
                  <Mono size={9.5} color={C.orange} weight={600}>
                    {String(i + 1).padStart(2, "0")}
                  </Mono>
                  <div
                    style={{
                      fontFamily: FONT_BODY,
                      fontSize: 12.5,
                      color: C.ink,
                      lineHeight: 1.35,
                    }}
                  >
                    {c}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        )}

        {timerOn && (
          <RestTimer initial={restSec} onClose={() => setTimerOn(false)} />
        )}
      </div>
    </div>
  );
}

function SectionHeader({ block }: { block: Demo2Block }) {
  const { n, title, mins, start, tier } = block;
  const tierLabel =
    tier === "main" ? "MAIN WORK" : tier === "support" ? "SUPPORT" : "PREP";
  return (
    <div style={{ padding: "28px 16px 6px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 8,
        }}
      >
        <Mono size={9.5} color={C.inkFaint}>
          {start} · {tierLabel}
        </Mono>
        <Mono size={9.5} color={C.inkFaint}>
          ~{mins} MIN
        </Mono>
      </div>
      <HairRule color={C.ruleStrong} style={{ marginBottom: 10 }} />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "52px 1fr",
          gap: 10,
          alignItems: "start",
        }}
      >
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 700,
            fontSize: 42,
            lineHeight: 0.85,
            color: tier === "main" ? C.orange : C.ink,
            letterSpacing: "-0.02em",
            fontFeatureSettings: '"tnum" 1',
          }}
        >
          {n}
        </div>
        <h2
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 700,
            fontSize: 26,
            lineHeight: 0.95,
            color: C.ink,
            margin: "4px 0 0",
            letterSpacing: "-0.01em",
            textTransform: "uppercase",
          }}
        >
          {title}
        </h2>
      </div>
    </div>
  );
}

function PersonalAside({ onCtaClick }: { onCtaClick: () => void }) {
  return (
    <div style={{ padding: "24px 16px 4px" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "3px 1fr",
          gap: 12,
          padding: "2px 0",
        }}
      >
        <div style={{ background: C.orange, width: 3 }} />
        <div>
          <Mono size={9.5} color={C.orange} weight={600}>
            FIG. 02 — A NOTE ON PERSONALIZATION
          </Mono>
          <p
            style={{
              fontFamily: FONT_DISPLAY,
              fontWeight: 700,
              fontSize: 22,
              lineHeight: 1.05,
              letterSpacing: "-0.005em",
              color: C.ink,
              margin: "8px 0 6px",
            }}
          >
            This session is generic. Yours won&apos;t be.
          </p>
          <p
            style={{
              fontFamily: FONT_BODY,
              fontSize: 13,
              lineHeight: 1.5,
              color: C.inkDim,
              margin: "0 0 12px",
            }}
          >
            Your real plan is calibrated to your grades, goals, available days,
            and gym. Computed in 5 minutes. Adapts every week from your session
            feedback.
          </p>
          <Link
            href={CTA_HREF}
            onClick={onCtaClick}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              background: C.orange,
              color: C.bg,
              padding: "11px 14px",
              fontFamily: FONT_MONO,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              textDecoration: "none",
            }}
          >
            Build your plan
            <span style={{ fontSize: 13, lineHeight: 1 }}>→</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

function Closure({
  endMarkerRef,
}: {
  endMarkerRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <div style={{ padding: "32px 16px 20px" }} ref={endMarkerRef}>
      <HairRule color={C.ruleStrong} style={{ marginBottom: 10 }} />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 18,
        }}
      >
        <Mono size={9.5}>END OF SESSION · 09</Mono>
        <Mono size={9.5}>~{DEMO2_TOTAL_MIN} MIN · COMPLETE</Mono>
      </div>
      <div
        style={{
          fontFamily: FONT_DISPLAY,
          fontWeight: 700,
          fontSize: 38,
          lineHeight: 0.9,
          color: C.ink,
          letterSpacing: "-0.02em",
          textTransform: "uppercase",
          marginBottom: 10,
        }}
      >
        That&apos;s the shape
        <br />
        of one session.
      </div>
      <p
        style={{
          fontFamily: FONT_BODY,
          fontSize: 13.5,
          lineHeight: 1.55,
          color: C.inkDim,
          margin: "0 0 20px",
          maxWidth: 320,
        }}
      >
        Every session in your real plan includes feedback tracking, automatic
        load adaptation, and week-over-week progression. Session logs shape next
        week.
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 0,
          border: `1px solid ${C.ruleStrong}`,
        }}
      >
        {(
          [
            ["FEEDBACK", "After each session"],
            ["ADAPTATION", "Automatic, weekly"],
            ["ENGINE", "Deterministic · No LLM"],
            ["READY", "10 min to first plan"],
          ] as [string, string][]
        ).map(([k, v], i) => (
          <div
            key={k}
            style={{
              padding: "10px 12px",
              borderRight: i % 2 === 0 ? `1px solid ${C.ruleStrong}` : "none",
              borderBottom: i < 2 ? `1px solid ${C.ruleStrong}` : "none",
            }}
          >
            <Mono
              size={9}
              color={C.inkFaint}
              style={{ display: "block", marginBottom: 4 }}
            >
              {k}
            </Mono>
            <div
              style={{
                fontFamily: FONT_BODY,
                fontSize: 12,
                color: C.ink,
                lineHeight: 1.3,
              }}
            >
              {v}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StickyCTA({ onCtaClick }: { onCtaClick: () => void }) {
  return (
    <div
      style={{
        position: "sticky",
        bottom: 0,
        left: 0,
        right: 0,
        background: C.bg,
        borderTop: `1px solid ${C.ruleStrong}`,
        zIndex: 10,
      }}
    >
      <div
        style={{
          padding:
            "10px 16px calc(14px + env(safe-area-inset-bottom))",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: 8,
          }}
        >
          <Mono size={9.5}>PERIODIZED. STRENGTH + SKILL.</Mono>
          <Mono size={9.5} color={C.inkFaint}>
            10 MIN SETUP
          </Mono>
        </div>
        <Link
          href={CTA_HREF}
          onClick={onCtaClick}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "14px 16px",
            background: C.orange,
            color: C.bg,
            fontFamily: FONT_DISPLAY,
            fontWeight: 700,
            fontSize: 18,
            letterSpacing: "-0.005em",
            textTransform: "uppercase",
            textDecoration: "none",
          }}
        >
          <span>Build my plan</span>
          <span style={{ fontSize: 20, lineHeight: 1 }}>→</span>
        </Link>
      </div>
    </div>
  );
}

export default function Demo2Page() {
  const engagedRef = useRef(false);
  const endMarkerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    captureUtmOnMount();
    trackEvent("demo_viewed", { variant: VARIANT });
  }, []);

  useEffect(() => {
    const node = endMarkerRef.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    let fired = false;
    const observer = new IntersectionObserver(
      (entries) => {
        if (fired) return;
        for (const entry of entries) {
          if (entry.isIntersecting) {
            fired = true;
            trackEvent("demo_scrolled_to_end", { variant: VARIANT });
            observer.disconnect();
            return;
          }
        }
      },
      { threshold: 0.5 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const handleEngagement = useCallback(() => {
    if (engagedRef.current) return;
    engagedRef.current = true;
    trackEvent("demo_engaged", { variant: VARIANT });
  }, []);

  const handleCtaClick = useCallback((location: "inline" | "sticky") => {
    trackEvent("demo_cta_clicked", { location, variant: VARIANT });
  }, []);

  const firstHalf = DEMO2_SESSION.slice(0, 4);
  const secondHalf = DEMO2_SESSION.slice(4);

  return (
    <div
      className="mx-auto"
      style={{
        background: C.bg,
        color: C.ink,
        minHeight: "100vh",
        fontFamily: FONT_BODY,
        maxWidth: "28rem",
        position: "relative",
      }}
    >
      <Masthead />
      <SpecCard />
      {firstHalf.map((block) => (
        <Fragment key={block.n}>
          <SectionHeader block={block} />
          {block.exercises.map((ex, j) => (
            <ExerciseCard
              key={ex.id}
              ex={ex}
              tier={block.tier}
              idx={j}
              onEngage={handleEngagement}
            />
          ))}
        </Fragment>
      ))}
      <PersonalAside onCtaClick={() => handleCtaClick("inline")} />
      {secondHalf.map((block) => (
        <Fragment key={block.n}>
          <SectionHeader block={block} />
          {block.exercises.map((ex, j) => (
            <ExerciseCard
              key={ex.id}
              ex={ex}
              tier={block.tier}
              idx={j}
              onEngage={handleEngagement}
            />
          ))}
        </Fragment>
      ))}
      <Closure endMarkerRef={endMarkerRef} />
      <StickyCTA onCtaClick={() => handleCtaClick("sticky")} />
    </div>
  );
}
