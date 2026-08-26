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
      <section className="intro">
        <p className="eyebrow">{mode === "sign-in" ? "Sign in" : "Sign up"}</p>
        <h1>DevStacks</h1>
      </section>

      <button className="github-button" onClick={handleGithub} type="button">
        Continue with GitHub
      </button>

      <p className="muted">or use email and password</p>

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
    </main>
  );
}
