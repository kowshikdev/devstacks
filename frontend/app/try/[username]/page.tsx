"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";

import { ApiError, DemoPreview, getGithubDemoPreview } from "../../../lib/api/client";

interface PageProps {
  params: Promise<{ username: string }>;
}

export default function TryPreviewPage({ params }: PageProps) {
  const { username } = use(params);

  const [preview, setPreview] = useState<DemoPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getGithubDemoPreview(username)
      .then(setPreview)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setError(`No public GitHub user found for "${username}".`);
          return;
        }
        if (err instanceof ApiError && err.status === 429) {
          setError("Too many previews right now — try again in a minute.");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load a preview");
      })
      .finally(() => setLoading(false));
  }, [username]);

  return (
    <main className="dashboard dashboard--wide">
      <section className="intro">
        <p className="eyebrow">Live preview · not saved · not published</p>
        <h1>@{username}</h1>
      </section>

      {loading && <p className="muted">Fetching real GitHub evidence…</p>}
      {error && <p className="error-text">{error}</p>}

      {preview && (
        <>
          <section className="panel">
            <p>
              <strong>{preview.display_name ?? preview.username}</strong>
            </p>
            <p className="muted">{preview.public_repos} public repositories</p>
            {preview.top_languages.length > 0 && (
              <div className="status-pills">
                {preview.top_languages.map((language) => (
                  <span className="status-pill" key={language}>
                    {language}
                  </span>
                ))}
              </div>
            )}
          </section>

          <section>
            <p className="claim-category" style={{ marginBottom: 12 }}>
              Recent repositories
            </p>
            <ul className="claim-list">
              {preview.repositories.map((repository) => (
                <li key={repository.name} className="review-card">
                  <p className="claim-statement">
                    <svg
                      width="13"
                      height="13"
                      viewBox="0 0 16 16"
                      fill="none"
                      aria-hidden="true"
                      style={{ marginRight: 7, verticalAlign: -2 }}
                    >
                      <circle cx="4" cy="3.2" r="1.6" stroke="var(--text-secondary)" strokeWidth="1.3" />
                      <circle cx="4" cy="12.8" r="1.6" stroke="var(--text-secondary)" strokeWidth="1.3" />
                      <circle cx="12" cy="12.8" r="1.6" stroke="var(--text-secondary)" strokeWidth="1.3" />
                      <path
                        d="M4 4.8V11.2M4 6.2C4 8.6 6 9 8 9H12M12 9V11.2"
                        stroke="var(--text-secondary)"
                        strokeWidth="1.3"
                      />
                    </svg>
                    {repository.name}
                  </p>
                  {repository.description && <p className="muted">{repository.description}</p>}
                  <div className="status-pills">
                    {repository.language && <span className="status-pill">{repository.language}</span>}
                    <span className="status-pill">★ {repository.stargazers_count}</span>
                  </div>
                </li>
              ))}
              {preview.repositories.length === 0 && <p className="muted">No public repositories found.</p>}
            </ul>
          </section>

          {preview.recent_commits.length > 0 && (
            <section>
              <p className="claim-category" style={{ marginBottom: 12 }}>
                Recent commits (real evidence, unpublished)
              </p>
              <ul className="evidence-list">
                {preview.recent_commits.map((commit) => (
                  <li key={commit.sha}>
                    <span className="evidence-mark">+</span>
                    <a href={commit.html_url} target="_blank" rel="noreferrer">
                      {commit.sha}
                    </a>{" "}
                    · {commit.repository} · {commit.message}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="panel">
            <p>
              <strong>This is only what&apos;s public.</strong> Connect your real account to build a
              verified, reviewable profile with provenance for every claim.
            </p>
            <Link href="/login" className="github-button" style={{ display: "inline-block", marginTop: 12 }}>
              Sign in with GitHub
            </Link>
          </section>
        </>
      )}
    </main>
  );
}
