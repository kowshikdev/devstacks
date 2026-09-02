"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { signInWithGitHub, signInWithPassword, signUpWithPassword } from "../../lib/supabase/client";
import { Button } from "../../components/ui/Button";
import { Flash } from "../../components/ui/Feedback";
import { TextField } from "../../components/ui/Field";
import { CheckCircleIcon, DevStacksMark, GitHubIcon, ShieldIcon } from "../../components/ui/Icon";

type Mode = "sign-in" | "sign-up";

const PROOF_POINTS = [
  "Connector tokens stay server-side, encrypted at rest.",
  "The GitHub connector starts at read:user — nothing more.",
  "Nothing reaches your public profile without your review.",
];

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthSkeleton />}>
      <LoginContent />
    </Suspense>
  );
}

function AuthSkeleton() {
  return (
    <div className="auth-layout">
      <div className="auth-panel">
        <div className="auth-card stack gap-4">
          <div className="skeleton" style={{ height: 32, width: 180 }} />
          <div className="skeleton" style={{ height: 44 }} />
          <div className="skeleton" style={{ height: 44 }} />
        </div>
      </div>
    </div>
  );
}

function LoginContent() {
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<Mode>(
    searchParams.get("intent") === "sign-up" ? "sign-up" : "sign-in"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [oauthBusy, setOauthBusy] = useState(false);

  const isSignUp = mode === "sign-up";

  async function handleGithub() {
    setError(null);
    setOauthBusy(true);
    try {
      await signInWithGitHub(`${window.location.origin}/auth/callback`);
      // The browser navigates away to GitHub; nothing more to do here.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start GitHub sign-in");
      setOauthBusy(false);
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      if (isSignUp) {
        const hasSession = await signUpWithPassword(email, password);
        if (hasSession) {
          window.location.href = "/dashboard";
          return;
        }
        setNotice("Check your email to confirm your account, then sign in.");
        setMode("sign-in");
      } else {
        await signInWithPassword(email, password);
        window.location.href = "/dashboard";
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  function switchMode() {
    setMode(isSignUp ? "sign-in" : "sign-up");
    setError(null);
    setNotice(null);
  }

  return (
    <div className="auth-layout">
      <div className="auth-panel">
        <div className="auth-card">
          <Link href="/" className="wordmark mb-6" style={{ display: "inline-flex" }}>
            <DevStacksMark className="wordmark__mark" />
            DevStacks
          </Link>

          <h1 style={{ fontSize: "var(--text-h2)" }}>
            {isSignUp ? "Create your evidence graph" : "Sign in to DevStacks"}
          </h1>
          <p className="text-sm text-muted mt-2">
            {isSignUp
              ? "Connect a source once. Review what it proves. Publish only what stands up."
              : "Pick up where your evidence left off."}
          </p>

          <div className="mt-6 stack gap-4">
            <Button
              variant="contrast"
              size="lg"
              block
              onClick={handleGithub}
              loading={oauthBusy}
              leadingIcon={<GitHubIcon size={17} />}
            >
              Continue with GitHub
            </Button>

            <p className="divider--labelled">or use email</p>

            <form className="stack gap-4" onSubmit={handleSubmit} noValidate>
              <TextField
                label="Email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
              <TextField
                label="Password"
                type="password"
                autoComplete={isSignUp ? "new-password" : "current-password"}
                placeholder={isSignUp ? "At least 8 characters" : "Your password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={8}
                hint={isSignUp ? "Use at least 8 characters." : undefined}
                required
              />
              <Button type="submit" variant="primary" size="lg" block loading={busy}>
                {isSignUp ? "Create account" : "Sign in"}
              </Button>
            </form>

            {notice ? <Flash tone="success">{notice}</Flash> : null}
            {error ? <Flash tone="danger">{error}</Flash> : null}

            <p className="text-sm text-muted" style={{ textAlign: "center" }}>
              {isSignUp ? "Already have an account?" : "New to DevStacks?"}{" "}
              <button type="button" className="text-accent font-semibold" onClick={switchMode}>
                {isSignUp ? "Sign in" : "Create an account"}
              </button>
            </p>

            <p className="text-xs text-subtle" style={{ textAlign: "center" }}>
              Prefer to look first?{" "}
              <Link href="/try">Preview any public GitHub username</Link> — no account needed.
            </p>
          </div>
        </div>
      </div>

      <aside className="auth-aside">
        <div className="quote">
          <ShieldIcon size={28} className="text-accent mb-4" />
          <p className="quote__text">
            &ldquo;A profile is only worth what it can withstand. DevStacks publishes the evidence
            chain, not the conclusion.&rdquo;
          </p>
          <p className="quote__attribution">The DevStacks assurance model</p>
        </div>

        <ul className="stack gap-3" style={{ position: "relative", zIndex: 1 }}>
          {PROOF_POINTS.map((point) => (
            <li className="row row--start gap-3 text-sm text-muted" key={point}>
              <CheckCircleIcon size={16} className="text-success shrink-0" />
              {point}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
