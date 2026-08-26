"use client";

import { useState } from "react";

import { signInWithGitHub, signInWithPassword, signUpWithPassword } from "../../lib/supabase/client";

type Mode = "sign-in" | "sign-up";

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleGithub() {
    setError(null);
    try {
      await signInWithGitHub(`${window.location.origin}/auth/callback`);
      // Browser navigates away to GitHub; nothing more to do here.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start GitHub sign-in");
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      if (mode === "sign-in") {
        await signInWithPassword(email, password);
        window.location.href = "/dashboard";
      } else {
        const hasSession = await signUpWithPassword(email, password);
        if (hasSession) {
          window.location.href = "/dashboard";
        } else {
          setNotice("Check your email to confirm your account, then sign in.");
          setMode("sign-in");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="dashboard">
      <div className="panel glass" style={{ padding: "40px 36px" }}>
        <section className="intro" style={{ marginBottom: 24 }}>
          <p className="eyebrow">{mode === "sign-in" ? "Sign in" : "Sign up"}</p>
          <h1 style={{ fontSize: "1.7rem", margin: "8px 0 0" }}>
            {mode === "sign-in" ? (
              <>
                Sign in to your <em>graph</em>
              </>
            ) : (
              <>
                Build your <em>graph</em>
              </>
            )}
          </h1>
        </section>

        <button className="github-button" onClick={handleGithub} type="button" style={{ width: "100%" }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
          </svg>
          Continue with GitHub
        </button>

        <p className="muted" style={{ margin: "16px 0" }}>
          or use email and password
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={8}
            required
          />
          <button type="submit" disabled={busy}>
            {mode === "sign-in" ? "Sign in" : "Sign up"}
          </button>
        </form>

        <button
          type="button"
          className="link-button"
          style={{ marginTop: 16 }}
          onClick={() => {
            setMode(mode === "sign-in" ? "sign-up" : "sign-in");
            setError(null);
            setNotice(null);
          }}
        >
          {mode === "sign-in" ? "Need an account? Sign up" : "Already have an account? Sign in"}
        </button>

        {notice && <p className="muted">{notice}</p>}
        {error && <p className="error-text">{error}</p>}
      </div>
    </main>
  );
}
