"use client";

import { useEffect, useState } from "react";

import AppShell from "../../../../components/AppShell";
import { ApiError, beginGithubAuth } from "../../../../lib/api/client";

export default function ConnectGithubPage() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // GitHub redirects the browser straight to the backend's own callback
    // route (GITHUB_OAUTH_REDIRECT_URI), which returns JSON today rather than
    // a browser redirect back into this app. Unresolved integration detail —
    // see the implementation plan's Phase 3/5 note.
    beginGithubAuth()
      .then((authorizationUrl) => {
        window.location.href = authorizationUrl;
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Could not start GitHub authorization");
      });
  }, []);

  return (
    <AppShell>
      <section className="intro">
        <p className="eyebrow">Connect GitHub</p>
        <h1>Redirecting to GitHub…</h1>
      </section>
      {error && <p className="error-text">{error}</p>}
    </AppShell>
  );
}
