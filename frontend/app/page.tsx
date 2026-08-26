const stages = ["Source", "Evidence", "Claim Revision", "Verification", "Profile"];

export default function HomePage() {
  return (
    <main>
      <section className="intro" aria-labelledby="page-title">
        <p className="eyebrow">Developer evidence graph</p>
        <h1 id="page-title">DevStacks</h1>
        <p className="summary">
          A reviewable public profile built from immutable source evidence, not inferred biography.
        </p>
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
        <p>Foundation in progress</p>
        <strong>GitHub evidence path is next.</strong>
      </section>
    </main>
  );
}