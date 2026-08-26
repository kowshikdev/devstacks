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
      <section className="intro">
        <p className="eyebrow">Try it, no sign-up</p>
        <h1>See your evidence graph</h1>
        <p className="summary">
          Paste any public GitHub username. Nothing is saved, nothing is published — just a live look
          at what DevStacks would find.
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
    </main>
  );
}
