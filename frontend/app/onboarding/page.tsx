"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ApiError, createProfile } from "../../lib/api/client";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { Flash, ProgressBar } from "../../components/ui/Feedback";
import { TextField } from "../../components/ui/Field";
import {
  ArrowRightIcon,
  CheckCircleIcon,
  CheckIcon,
  DevStacksMark,
  GitHubIcon,
  GlobeIcon,
} from "../../components/ui/Icon";

const HANDLE_PATTERN = /^[a-z0-9][a-z0-9-]{2,38}$/;

type Step = "identity" | "connect";

const STEPS: { id: Step; title: string; description: string }[] = [
  {
    id: "identity",
    title: "Claim your handle",
    description: "This becomes your public profile URL and cannot be reused by anyone else.",
  },
  {
    id: "connect",
    title: "Connect a source",
    description: "Evidence only exists once a connector has observed something real.",
  },
];

export default function OnboardingPage() {
  const [step, setStep] = useState<Step>("identity");
  const [handle, setHandle] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const stepIndex = STEPS.findIndex((entry) => entry.id === step);
  const current = STEPS[stepIndex];

  const handleError = useMemo(() => {
    if (!handle) return null;
    if (!HANDLE_PATTERN.test(handle)) {
      return "3–39 characters: lowercase letters, digits, or hyphens, starting with a letter or digit.";
    }
    return null;
  }, [handle]);

  async function submitIdentity(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!HANDLE_PATTERN.test(handle)) {
      setError("Choose a handle that matches the format below before continuing.");
      return;
    }
    setBusy(true);
    try {
      await createProfile(handle, displayName || undefined);
      setStep("connect");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        window.location.href = "/login";
        return;
      }
      setError(err instanceof ApiError ? err.message : "Could not create your profile");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-frame">
      <main className="app-main" id="main">
        <div className="container container--sm">
          <Link href="/" className="wordmark mb-6" style={{ display: "inline-flex" }}>
            <DevStacksMark className="wordmark__mark" />
            DevStacks
          </Link>

          <div className="mb-6">
            <div className="row row--between mb-2">
              <span className="eyebrow">
                Step {stepIndex + 1} of {STEPS.length}
              </span>
              <span className="text-xs text-subtle">{current.title}</span>
            </div>
            <ProgressBar
              value={((stepIndex + (step === "connect" ? 1 : 0)) / STEPS.length) * 100}
              label="Onboarding progress"
            />
          </div>

          <Card>
            <CardBody>
              <h1 style={{ fontSize: "var(--text-h2)" }}>{current.title}</h1>
              <p className="text-sm text-muted mt-2">{current.description}</p>

              {step === "identity" ? (
                <form className="stack gap-5 mt-6" onSubmit={submitIdentity} noValidate>
                  <TextField
                    label="Handle"
                    prefix="devstacks.dev/"
                    mono
                    placeholder="your-handle"
                    value={handle}
                    onChange={(event) =>
                      setHandle(event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))
                    }
                    error={handleError}
                    hint="3–39 characters: lowercase letters, digits, or hyphens."
                    autoFocus
                    required
                  />
                  <TextField
                    label="Display name"
                    trailingLabel={<span className="text-xs text-subtle">Optional</span>}
                    placeholder="How your name should appear"
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                  />

                  {error ? <Flash tone="danger">{error}</Flash> : null}

                  <Button
                    type="submit"
                    variant="primary"
                    size="lg"
                    block
                    loading={busy}
                    trailingIcon={<ArrowRightIcon size={16} />}
                  >
                    Continue
                  </Button>
                </form>
              ) : (
                <div className="stack gap-5 mt-6">
                  <Flash tone="success">
                    Profile created. <strong>@{handle}</strong> is yours.
                  </Flash>

                  <ul className="stack gap-3">
                    <li className="row row--start gap-3 text-sm">
                      <CheckCircleIcon size={16} className="text-success shrink-0" />
                      <span>
                        <strong>Connect GitHub</strong> so DevStacks can observe commits, pull
                        requests, and releases.
                      </span>
                    </li>
                    <li className="row row--start gap-3 text-sm">
                      <CheckIcon size={16} className="text-subtle shrink-0" />
                      <span>
                        <strong>Review the proposed claims</strong> — nothing publishes on its own.
                      </span>
                    </li>
                    <li className="row row--start gap-3 text-sm">
                      <GlobeIcon size={16} className="text-subtle shrink-0" />
                      <span>
                        <strong>Publish</strong> what stands up, and share your profile URL.
                      </span>
                    </li>
                  </ul>

                  <div className="stack gap-2">
                    <ButtonLink
                      href="/dashboard/connect/github"
                      variant="primary"
                      size="lg"
                      block
                      leadingIcon={<GitHubIcon size={16} />}
                    >
                      Connect GitHub
                    </ButtonLink>
                    <ButtonLink href="/dashboard" size="lg" block>
                      Skip for now — go to dashboard
                    </ButtonLink>
                  </div>
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </main>
    </div>
  );
}
