"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { PublicShell } from "../../components/AppShell";
import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { TextField } from "../../components/ui/Field";
import { Label } from "../../components/ui/Label";
import {
  ArrowRightIcon,
  CheckIcon,
  GitHubIcon,
  LockIcon,
  SparkIcon,
} from "../../components/ui/Icon";

const SUGGESTIONS = ["torvalds", "gaearon", "sindresorhus"];

const GUARANTEES = [
  "Reads only data GitHub already makes public.",
  "Saves nothing, publishes nothing, creates no account.",
  "No agent run, no evidence write — a look, not a commitment.",
];

export default function TryLandingPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = username.trim().replace(/^@/, "");
    if (!trimmed) return;
    router.push(`/try/${encodeURIComponent(trimmed)}`);
  }

  return (
    <PublicShell>
      <div className="container container--md">
        <div className="mb-6">
          <Label tone="accent">
            <SparkIcon size={12} />
            No sign-up required
          </Label>
          <h1 className="mt-3" style={{ fontSize: "var(--text-h1)" }}>
            See what your GitHub already proves.
          </h1>
          <p className="text-muted mt-3 leading-relaxed" style={{ maxWidth: "58ch" }}>
            Enter any public GitHub username. DevStacks pulls the same public facts a connector would
            observe first — repositories, languages, recent commits — so you can judge the idea before
            you authorize anything.
          </p>
        </div>

        <Card>
          <CardBody>
            <form className="stack gap-4" onSubmit={submit}>
              <TextField
                label="GitHub username"
                prefix="github.com/"
                mono
                placeholder="octocat"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoFocus
                required
              />
              <Button
                type="submit"
                variant="primary"
                size="lg"
                block
                trailingIcon={<ArrowRightIcon size={16} />}
                disabled={username.trim().length === 0}
              >
                Run live preview
              </Button>
            </form>

            <div className="row row--wrap gap-2 mt-4">
              <span className="text-xs text-subtle">Try:</span>
              {SUGGESTIONS.map((suggestion) => (
                <Button
                  key={suggestion}
                  size="sm"
                  variant="invisible"
                  onClick={() => router.push(`/try/${suggestion}`)}
                  leadingIcon={<GitHubIcon size={13} />}
                >
                  {suggestion}
                </Button>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card subtle className="mt-4">
          <CardBody>
            <p className="row gap-2 text-sm font-semibold">
              <LockIcon size={15} />
              What this preview does and does not do
            </p>
            <ul className="stack gap-2 mt-3">
              {GUARANTEES.map((line) => (
                <li className="row row--start gap-2 text-sm text-muted" key={line}>
                  <CheckIcon size={14} className="text-success shrink-0" />
                  {line}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      </div>
    </PublicShell>
  );
}
