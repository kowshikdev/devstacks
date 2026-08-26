import Link from "next/link";

const stages = ["Source", "Evidence", "Claim Revision", "Verification", "Profile"];

export default function HomePage() {
  return (
    <main>
      <section className="intro" aria-labelledby="page-title">
        <span className="badge glass">
          <span className="badge-dot" />
          Continuously verified developer evidence graph
        </span>

        <h1 id="page-title">
          Every claim,
          <br />
          <em>verified</em>.
        </h1>

        <p className="summary">
          A reviewable public profile built from immutable source evidence, not inferred biography.
          No self-reported skills — only what your commits, PRs, and releases actually prove.
        </p>

        <div style={{ display: "flex", gap: 12, marginTop: 24, flexWrap: "wrap" }}>
          <Link href="/try" className="github-button" style={{ display: "inline-flex" }}>
            Try it on your GitHub — no sign-up
            <span className="kbd">↵</span>
          </Link>
          <Link href="/login" className="link-button" style={{ display: "inline-flex", alignItems: "center" }}>
            Sign in
          </Link>
        </div>

        <div className="terminal glass" style={{ marginTop: 36, maxWidth: 560 }}>
          <div className="terminal-bar">
            <span />
            <span />
            <span />
            <span className="terminal-file">devstacks — evidence sync</span>
          </div>
          <div className="terminal-body">
            <div className="terminal-prompt">devstacks sync github</div>
            <div className="terminal-line">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 8.5L6.2 11.7L13 4" stroke="#34d399" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              227 evidence versions collected
            </div>
            <div className="terminal-line">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 8.5L6.2 11.7L13 4" stroke="#34d399" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              4 claim revisions verified
            </div>
            <div className="terminal-line">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 8.5L6.2 11.7L13 4" stroke="#34d399" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              replay confirmed idempotent<span className="cursor" />
            </div>
          </div>
        </div>
      </section>

      <section className="flow" aria-label="Evidence lifecycle">
        {stages.map((stage, index) => (
          <div className="stage" key={stage}>
            <span className="sequence">{String(index + 1).padStart(2, "0")}</span>
            <strong>{stage}</strong>
          </div>
        ))}
      </section>

      <section className="status" aria-label="Implementation status">
        <p>Golden path live</p>
        <strong>GitHub evidence is verified end to end.</strong>
      </section>
    </main>
  );
}
