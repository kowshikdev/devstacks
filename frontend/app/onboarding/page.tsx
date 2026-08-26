"use client";

import { useState } from "react";

import { ApiError, createProfile } from "../../lib/api/client";

const HANDLE_PATTERN = /^[a-z0-9][a-z0-9-]{2,38}$/;

export default function OnboardingPage() {
  const [handle, setHandle] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!HANDLE_PATTERN.test(handle)) {
      setError("Handle must be 3-39 lowercase letters, digits, or hyphens, starting with a letter or digit.");
      return;
    }
    setBusy(true);
    try {
      await createProfile(handle, displayName || undefined);
      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create your profile");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="dashboard">
      <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 20, padding: "40px 36px" }}>
        <section className="intro">
          <p className="eyebrow">Almost there</p>
          <h1 style={{ fontSize: "1.7rem", margin: "8px 0 0" }}>Choose your handle</h1>
          <p className="muted" style={{ margin: "6px 0 0" }}>
            This becomes your public profile URL.
          </p>
        </section>

        <form className="auth-form" onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="your-handle"
            value={handle}
            onChange={(event) => setHandle(event.target.value.toLowerCase())}
            required
          />
          <input
            type="text"
            placeholder="Display name (optional)"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
          />
          <button type="submit" disabled={busy}>
            Create profile
          </button>
        </form>

        {error && <p className="error-text">{error}</p>}
      </div>
    </main>
  );
}
