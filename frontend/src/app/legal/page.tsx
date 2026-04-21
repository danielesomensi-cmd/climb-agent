{/*
  PLACEHOLDER LEGAL CONTENT — Soft launch version.
  Daniele should review and get legal advice before hard launch.
  Last updated: 2026-03-22
*/}

import Link from "next/link";

export const metadata = {
  title: "Legal — climb-agent",
};

export default function LegalPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 text-sm text-muted-foreground">
      <Link
        href="/"
        className="mb-8 inline-block text-primary underline text-xs"
      >
        &larr; Back to app
      </Link>

      <h1 className="mb-8 text-2xl font-bold text-foreground">
        Legal Information
      </h1>

      {/* ── Terms of Service ────────────────────────────── */}
      <section className="mb-12">
        <h2 className="mb-4 text-xl font-semibold text-foreground">
          Terms of Service
        </h2>
        <p className="mb-2 text-xs italic">
          Effective date: March 2026. This is a placeholder for soft launch —
          full legal review pending.
        </p>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          1. Service Description
        </h3>
        <p className="mb-4">
          climb-agent is a deterministic climbing training planning tool. It
          generates personalised weekly training plans based on your goals,
          assessment data, and available equipment. The service uses rule-based
          logic — no AI/LLM is used in the training plan generation.
        </p>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          2. Not Medical or Coaching Advice
        </h3>
        <p className="mb-4">
          climb-agent is a software tool, not a certified coach or medical
          professional. The training plans generated are based on published
          climbing training literature (H&ouml;rst, L&oacute;pez-Rivera, Lattice
          Training, etc.) but are not a substitute for professional coaching,
          physiotherapy, or medical advice. Consult a qualified professional
          before starting any training programme, especially if you have
          pre-existing injuries or medical conditions.
        </p>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          3. User Responsibilities
        </h3>
        <ul className="mb-4 list-disc pl-6 space-y-1">
          <li>Provide accurate assessment data (grades, test results, experience)</li>
          <li>Consult a doctor before starting a structured training programme</li>
          <li>Stop training and seek medical advice if you experience pain or injury</li>
          <li>Use the service at your own risk — climbing is an inherently dangerous activity</li>
        </ul>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          4. Data Ownership
        </h3>
        <p className="mb-4">
          You own your data. You can export all your training data at any time
          via Settings &rarr; Export Data (JSON format). You can delete all your
          data at any time via Settings &rarr; Reset &amp; Restart. Deletion is
          permanent and irreversible.
        </p>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          5. Payments
        </h3>
        <p className="mb-4">
          Payment terms will be defined when the paid subscription launches.
          During the beta / soft launch period, the service is free to use.
        </p>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          6. Limitation of Liability
        </h3>
        <p className="mb-4">
          climb-agent is provided &ldquo;as is&rdquo; without warranty of any
          kind. The developer is not liable for any injury, loss, or damage
          arising from the use of the service, including but not limited to
          training injuries, data loss, or service interruptions.
        </p>
      </section>

      {/* ── Privacy Policy ──────────────────────────────── */}
      <section className="mb-12">
        <h2 className="mb-4 text-xl font-semibold text-foreground">
          Privacy Policy
        </h2>
        <p className="mb-2 text-xs italic">
          GDPR-aware placeholder — full legal review pending before hard launch.
        </p>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          1. What Data We Collect
        </h3>
        <ul className="mb-4 list-disc pl-6 space-y-1">
          <li>Profile data: name, age, weight, height, climbing experience</li>
          <li>Assessment data: grades, test results (max hang, pull-up, repeater)</li>
          <li>Training logs: session completion, exercise feedback, outdoor sessions</li>
          <li>Goals and preferences: target grade, availability, equipment</li>
          <li>Authentication data: managed by Clerk (email, login method)</li>
        </ul>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          2. Why We Collect It
        </h3>
        <p className="mb-4">
          All data is collected solely to generate personalised training plans
          and track your progression. We do not use your data for advertising,
          profiling, or any purpose other than providing the training service.
        </p>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          3. Data Storage &amp; Security
        </h3>
        <ul className="mb-4 list-disc pl-6 space-y-1">
          <li>Training data: stored on Railway (EU region) / Supabase Postgres (planned migration)</li>
          <li>Authentication: managed by Clerk (SOC 2 compliant)</li>
          <li>All data transmitted over HTTPS</li>
          <li>No data is stored on your device beyond session cache (localStorage)</li>
        </ul>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          4. Data Retention
        </h3>
        <p className="mb-4">
          Your data is retained as long as your account is active. When you
          delete your account (Settings &rarr; Reset &amp; Restart), all
          training data is permanently deleted. Authentication data managed by
          Clerk follows their retention policy.
        </p>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          5. Your Rights (GDPR Articles 15-20)
        </h3>
        <ul className="mb-4 list-disc pl-6 space-y-1">
          <li><strong>Access:</strong> Export all your data via Settings &rarr; Export Data</li>
          <li><strong>Rectification:</strong> Edit your profile, grades, and assessment via Settings</li>
          <li><strong>Erasure:</strong> Delete all data via Settings &rarr; Reset &amp; Restart</li>
          <li><strong>Data portability:</strong> Export as JSON (machine-readable format)</li>
          <li><strong>Object:</strong> Contact us to object to specific data processing</li>
        </ul>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          6. Third-Party Sharing
        </h3>
        <p className="mb-4">
          We do not sell, share, or transfer your data to third parties. The
          only external services that process your data are:
        </p>
        <ul className="mb-4 list-disc pl-6 space-y-1">
          <li>Clerk (authentication)</li>
          <li>Railway / Supabase (data hosting)</li>
          <li>Vercel (frontend hosting — no user data stored)</li>
          <li>
            Vercel Analytics (anonymous, cookieless pageview and funnel
            analytics — cannot identify individual users)
          </li>
        </ul>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          7. Cookies &amp; analytics
        </h3>
        <p className="mb-4">
          We use minimal cookies for authentication (Clerk session management).
          We also collect aggregated, anonymous pageview and funnel analytics
          through Vercel Analytics. This uses no cookies, no fingerprinting,
          and cannot identify individual users. No advertising or third-party
          tracking cookies are used.
        </p>

        <h3 className="mt-6 mb-2 font-medium text-foreground">
          8. Contact
        </h3>
        <p className="mb-4">
          For any privacy-related questions, data access requests, or concerns,
          contact:{" "}
          <a
            href="mailto:daniele.somensi@gmail.com"
            className="text-primary underline"
          >
            daniele.somensi@gmail.com
          </a>
        </p>
      </section>

      <p className="text-xs text-muted-foreground/60">
        Last updated: March 2026
      </p>
    </div>
  );
}
