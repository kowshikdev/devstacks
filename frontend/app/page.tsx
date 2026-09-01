import type { Metadata } from "next";

import { PublicShell } from "../components/AppShell";
import { ButtonLink } from "../components/ui/Button";
import { Label } from "../components/ui/Label";
import {
  ArrowRightIcon,
  CheckIcon,
  ClockIcon,
  FingerprintIcon,
  GitHubIcon,
  GraphIcon,
  HistoryIcon,
  LockIcon,
  ShieldIcon,
  SparkIcon,
} from "../components/ui/Icon";

export const metadata: Metadata = {
  title: "Verified developer evidence",
  description:
    "DevStacks turns source observations into immutable evidence, explainable claim revisions, and a reviewable public profile. No self-reported skills.",
};

const PIPELINE = [
  { name: "Source", note: "Connectors observe GitHub, exports, and certificates." },
  { name: "Evidence", note: "Each observation is hashed into an immutable version." },
  { name: "Claim revision", note: "Interpretation is proposed, never asserted." },
  { name: "Verification", note: "Support, contradiction, and freshness are scored." },
  { name: "Profile", note: "You review, then publish what stands up." },
];

const FEATURES = [
  {
    icon: <FingerprintIcon />,
    title: "Immutable evidence versions",
    body: "Every observation is content-hashed and appended. Nothing is edited in place, so history stays auditable and replays are idempotent.",
  },
  {
    icon: <GraphIcon />,
    title: "Explainable claim revisions",
    body: "A claim never stands alone. Each revision carries the evidence that supports it, the evidence that contradicts it, and the reasoning path.",
  },
  {
    icon: <ShieldIcon />,
    title: "Assurance classes, not badges",
    body: "Verified, self-attested, and inferred are distinct states with distinct weight. A reader can tell instantly how much a claim is worth.",
  },
  {
    icon: <ClockIcon />,
    title: "Freshness that decays",
    body: "Claims are revalidated on a schedule and on webhook events. Stale evidence is marked stale rather than quietly presented as current.",
  },
  {
    icon: <LockIcon />,
    title: "Least-privilege connectors",
    body: "The GitHub connector starts at read:user. Repository access is a separate, explicit authorization step, and tokens never reach the browser.",
  },
  {
    icon: <HistoryIcon />,
    title: "Human review before publish",
    body: "Nothing reaches your public profile without your approval. Approve, edit, or reject each revision — every decision is recorded.",
  },
];

const ASSURANCE_ROWS = [
  {
    tone: "success" as const,
    label: "Verified",
    body: "Derived from a source DevStacks observed directly, with provenance and a passing verification run.",
  },
  {
    tone: "attention" as const,
    label: "Self-attested",
    body: "You stated it. It is shown as your statement, never dressed up as an independent finding.",
  },
  {
    tone: "info" as const,
    label: "Inferred",
    body: "Structured interpretation over evidence. Useful, labelled as interpretation, and always traceable to its inputs.",
  },
];

const FAQ = [
  {
    question: "Is this another skills badge?",
    answer:
      "No. A badge asserts a conclusion. DevStacks publishes the evidence chain behind a conclusion, along with how fresh it is and what contradicts it.",
  },
  {
    question: "What does DevStacks read from GitHub?",
    answer:
      "The initial connector requests only read:user. Repository access is a separate authorization you grant explicitly, and connector tokens stay server-side, encrypted at rest.",
  },
  {
    question: "Who decides what is published?",
    answer:
      "You do. Claim revisions land in a review inbox. Approve, edit the statement, or reject — publishing is always a deliberate action.",
  },
  {
    question: "What happens when my work changes?",
    answer:
      "Webhooks and scheduled revalidation re-run verification. A claim whose evidence has aged is marked stale on your profile instead of silently standing.",
  },
];

export default function HomePage() {
  return (
    <PublicShell bare>
      {/* ---------- Hero ---------- */}
      <section className="hero">
        <div className="container hero__inner">
          <div>
            <Label tone="accent">
              <SparkIcon size={12} />
              GitHub golden path is live
            </Label>

            <h1 className="hero__title">
              Every claim on your profile,
              <br />
              <em>provably</em> earned.
            </h1>

            <p className="hero__lede">
              DevStacks builds a reviewable public developer profile from immutable source evidence
              — not inferred biography, not self-reported skills. Only what your commits, pull
              requests, and releases actually prove.
            </p>

            <div className="hero__actions">
              <ButtonLink
                href="/try"
                variant="primary"
                size="lg"
                trailingIcon={<ArrowRightIcon size={16} />}
              >
                Preview your GitHub — no sign-up
              </ButtonLink>
              <ButtonLink
                href="/login"
                size="lg"
                leadingIcon={<GitHubIcon size={16} />}
              >
                Sign in with GitHub
              </ButtonLink>
            </div>

            <div className="hero__meta">
              <div className="stat">
                <span className="stat__value">5</span>
                <span className="stat__label">lifecycle stages, each auditable</span>
              </div>
              <div className="stat">
                <span className="stat__value">3</span>
                <span className="stat__label">assurance classes, never blurred</span>
              </div>
              <div className="stat">
                <span className="stat__value">0</span>
                <span className="stat__label">claims published without your review</span>
              </div>
            </div>
          </div>

          {/* Proof, in the product's own vocabulary. */}
          <div className="window">
            <div className="window__bar">
              <span className="window__dot" />
              <span className="window__dot" />
              <span className="window__dot" />
              <span className="window__title">devstacks — evidence sync</span>
            </div>
            <div className="window__body">
              <p className="window__prompt">devstacks sync github</p>
              <p className="window__line window__line--ok">
                <CheckIcon size={14} />
                227 evidence versions collected
              </p>
              <p className="window__line window__line--ok">
                <CheckIcon size={14} />
                4 claim revisions proposed for review
              </p>
              <p className="window__line window__line--ok">
                <CheckIcon size={14} />
                1 revision marked stale — evidence aged out
              </p>
              <p className="window__line">
                replay confirmed idempotent
                <span className="cursor" />
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- Lifecycle ---------- */}
      <section className="section" id="how-it-works">
        <div className="container">
          <div className="section__head">
            <span className="eyebrow">How it works</span>
            <h2 className="section__title">Source to profile, with nothing lost in between.</h2>
            <p className="section__lede">
              Deterministic application code owns ingestion, identity binding, hashing, provenance,
              policy, and lifecycle transitions. Agents assist interpretation; they are never the
              source of truth.
            </p>
          </div>

          <ol className="pipeline">
            {PIPELINE.map((stage, index) => (
              <li className="pipeline__step" key={stage.name}>
                <span className="pipeline__index">{String(index + 1).padStart(2, "0")}</span>
                <p className="pipeline__name">{stage.name}</p>
                <p className="pipeline__note">{stage.note}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ---------- Features ---------- */}
      <section className="section">
        <div className="container">
          <div className="section__head">
            <span className="eyebrow">What makes it hold up</span>
            <h2 className="section__title">Built to survive a sceptical reader.</h2>
            <p className="section__lede">
              A profile is only worth what it can withstand. Each of these exists because a claim
              without it can be doubted.
            </p>
          </div>

          <div className="feature-grid">
            {FEATURES.map((feature) => (
              <article className="feature" key={feature.title}>
                <span className="feature__icon">{feature.icon}</span>
                <h3 className="feature__title">{feature.title}</h3>
                <p className="feature__body">{feature.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Assurance model ---------- */}
      <section className="section" id="assurance">
        <div className="container">
          <div className="section__head">
            <span className="eyebrow">Assurance</span>
            <h2 className="section__title">Three states. No blending.</h2>
            <p className="section__lede">
              Most profiles present everything at the same confidence. DevStacks refuses to, because
              the difference is the entire point.
            </p>
          </div>

          <div className="card">
            {ASSURANCE_ROWS.map((row) => (
              <div className="card__row" key={row.label}>
                <span style={{ minWidth: 120 }}>
                  <Label tone={row.tone} size="lg">
                    {row.label}
                  </Label>
                </span>
                <p className="text-sm text-muted flex-1">{row.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- FAQ ---------- */}
      <section className="section" id="faq">
        <div className="container">
          <div className="section__head">
            <span className="eyebrow">Questions</span>
            <h2 className="section__title">The ones worth asking.</h2>
          </div>

          <div className="feature-grid">
            {FAQ.map((entry) => (
              <article className="feature" key={entry.question}>
                <h3 className="feature__title">{entry.question}</h3>
                <p className="feature__body">{entry.answer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Close ---------- */}
      <section className="cta-band">
        <div className="container">
          <h2 className="cta-band__title">See what your GitHub already proves.</h2>
          <p className="cta-band__lede">
            The preview reads only public data, saves nothing, and publishes nothing. It takes one
            username and about four seconds.
          </p>
          <div className="row gap-3" style={{ justifyContent: "center", flexWrap: "wrap" }}>
            <ButtonLink href="/try" variant="primary" size="lg" trailingIcon={<ArrowRightIcon size={16} />}>
              Run a live preview
            </ButtonLink>
            <ButtonLink href="/login?intent=sign-up" size="lg">
              Create an account
            </ButtonLink>
          </div>
        </div>
      </section>
    </PublicShell>
  );
}
