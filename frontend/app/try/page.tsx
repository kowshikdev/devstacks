"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function TryLandingPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = username.trim();
    if (!trimmed) return;
    router.push(`/try/${encodeURIComponent(trimmed)}`);
  }

  return (
    <main className="dashboard">
      <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 20, padding: "40px 36px" }}>
        <section className="intro">
          <p className="eyebrow">Try it, no sign-up</p>
          <h1 style={{ fontSize: "1.7rem", margin: "8px 0 0" }}>See your evidence graph</h1>
          <p className="muted" style={{ margin: "6px 0 0" }}>
            Paste any public GitHub username. Nothing is saved, nothing is published — just a live
            look at what DevStacks would find.
          </p>
        </section>

        <form className="auth-form" onSubmit={handleSubmit}>
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="GitHub username"
            autoFocus
          />
          <button type="submit">Preview</button>
        </form>
      </div>
    </main>
  );
}
