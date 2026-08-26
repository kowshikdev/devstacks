"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import AppShell from "../../../../components/AppShell";
import { ApiError, beginGithubAuth, syncGithubConnection } from "../../../../lib/api/client";

const ERROR_MESSAGES: Record<string, string> = {
  denied: "You declined the GitHub authorization request.",
  invalid: "GitHub authorization could not be completed — the request may have expired.",
  unavailable: "The GitHub connector service is temporarily unavailable.",
};

export default function ConnectGithubPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <section className="intro">
            <p className="eyebrow">Connect GitHub</p>
            <h1>Loading…</h1>
          </section>
        </AppShell>
      }
    >
      <ConnectGithubContent />
    </Suspense>
  );
}

function ConnectGithubContent() {
  const searchParams = useSearchParams();
  const connected = searchParams.get("connected") === "1";
  const errorCode = searchParams.get("error");
  const githubLogin = searchParams.get("github_login");
  const connectionId = searchParams.get("connection_id");

  const [error, setError] = useState<string | null>(errorCode ? ERROR_MESSAGES[errorCode] ?? "GitHub authorization failed." : null);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  useEffect(() => {
    if (connected || errorCode) return;
    beginGithubAuth()
      .then((authorizationUrl) => {
        window.location.href = authorizationUrl;
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Could not start GitHub authorization");
      });
  }, [connected, errorCode]);

  async function handleSync() {
    if (!connectionId) return;
    setSyncing(true);
    setSyncMessage(null);
    try {
      await syncGithubConnection(connectionId);
      setSyncMessage("Sync queued — evidence collection is running in the background.");
    } catch (err) {
      setSyncMessage(err instanceof ApiError ? err.message : "Could not queue a sync");
    } finally {
      setSyncing(false);
    }
  }

  if (connected) {
    return (
      <AppShell>
        <section className="intro">
          <p className="eyebrow">Connect GitHub</p>
          <h1>
            Connected as <em>@{githubLogin}</em>
          </h1>
        </section>

        <div className="terminal">
          <div className="terminal-bar">
            <span />
            <span />
            <span />
            <span className="terminal-file">devstacks — connector</span>
          </div>
          <div className="terminal-body">
            <div className="terminal-line">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 8.5L6.2 11.7L13 4" stroke="#34d399" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              GitHub identity bound
            </div>
            <div className="terminal-prompt">devstacks sync github{syncMessage ? "" : <span className="cursor" />}</div>
            {syncMessage && <div className="terminal-line">{syncMessage}</div>}
          </div>
        </div>

        <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
          <button type="button" onClick={handleSync} disabled={syncing || !connectionId}>
            {syncing ? "Queuing…" : "Sync evidence now"}
          </button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <section className="intro">
        <p className="eyebrow">Connect GitHub</p>
        <h1>{error ? "Couldn't connect" : "Redirecting to GitHub…"}</h1>
      </section>
      {error && <p className="error-text">{error}</p>}
    </AppShell>
  );
}
