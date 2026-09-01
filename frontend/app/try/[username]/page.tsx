"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { ApiError, getGithubDemoPreview, type DemoPreview } from "../../../lib/api/client";
import { PublicShell } from "../../../components/AppShell";
import { Avatar } from "../../../components/ui/Avatar";
import { Button, ButtonLink } from "../../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { EmptyState, Flash, Skeleton } from "../../../components/ui/Feedback";
import { Label } from "../../../components/ui/Label";
import { RelativeTime } from "../../../components/ui/Time";
import {
  ArrowRightIcon,
  CommitIcon,
  GitHubIcon,
  RepoIcon,
  ShieldIcon,
  StarIcon,
} from "../../../components/ui/Icon";

interface PageProps {
  params: Promise<{ username: string }>;
}

export default function TryPreviewPage({ params }: PageProps) {
  const { username } = use(params);

  const [preview, setPreview] = useState<DemoPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getGithubDemoPreview(username)
      .then((result) => {
        if (!cancelled) setPreview(result);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
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
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [username]);

  return (
    <PublicShell bare>
      <div className="profile-cover" />

      <div className="container">
        <header className="profile-head">
          {loading ? (
            <Skeleton width={104} height={104} radius={999} />
          ) : (
            <Avatar
              name={preview?.display_name ?? username}
              src={preview?.avatar_url}
              size={104}
              className="profile-head__avatar"
            />
          )}

          <div className="profile-head__row">
            <div>
              <h1 className="profile-head__name">{preview?.display_name ?? username}</h1>
              <p className="profile-head__handle">@{username}</p>
            </div>
            <div className="row row--wrap gap-2">
              <ButtonLink
                href={`https://github.com/${encodeURIComponent(username)}`}
                leadingIcon={<GitHubIcon size={15} />}
                target="_blank"
                rel="noreferrer"
              >
                View on GitHub
              </ButtonLink>
              <ButtonLink href="/login" variant="primary">
                Build the verified version
              </ButtonLink>
            </div>
          </div>

          <div className="profile-head__meta">
            <Label tone="attention">
              <ShieldIcon size={12} />
              Live preview · not saved · not published
            </Label>
            {preview ? <span>{preview.public_repos} public repositories</span> : null}
          </div>
        </header>

        {error ? (
          <div className="mt-4 mb-6">
            <Flash tone="danger" actions={<ButtonLink href="/try" size="sm">Try another</ButtonLink>}>
              {error}
            </Flash>
          </div>
        ) : null}

        <div className="profile-layout">
          <div className="stack gap-5">
            <section className="stack gap-3">
              <div className="section-title">
                <h2 style={{ fontSize: "var(--text-h3)" }}>Recent repositories</h2>
                {preview ? (
                  <span className="text-xs text-muted">{preview.repositories.length} shown</span>
                ) : null}
              </div>

              {loading ? (
                <div className="stack gap-3">
                  {[0, 1, 2].map((row) => (
                    <Card key={row}>
                      <CardBody>
                        <Skeleton width="40%" height={16} />
                        <div className="mt-3">
                          <Skeleton width="80%" height={12} />
                        </div>
                        <div className="mt-3">
                          <Skeleton width="30%" height={12} />
                        </div>
                      </CardBody>
                    </Card>
                  ))}
                </div>
              ) : preview && preview.repositories.length > 0 ? (
                preview.repositories.map((repository) => (
                  <article className="repo-row" key={repository.name}>
                    <RepoIcon size={18} className="text-subtle shrink-0" style={{ marginTop: 2 }} />
                    <div className="flex-1">
                      <a
                        className="repo-row__name"
                        href={repository.html_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {repository.name}
                      </a>
                      {repository.description ? (
                        <p className="repo-row__description">{repository.description}</p>
                      ) : null}
                      <div className="repo-row__meta">
                        {repository.language ? (
                          <span className="row gap-2">
                            <span className="lang-dot" />
                            {repository.language}
                          </span>
                        ) : null}
                        <span className="row gap-1">
                          <StarIcon size={13} />
                          {repository.stargazers_count}
                        </span>
                        {repository.pushed_at ? (
                          <span>
                            Updated <RelativeTime value={repository.pushed_at} />
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </article>
                ))
              ) : !error ? (
                <Card>
                  <EmptyState
                    icon={<RepoIcon size={20} />}
                    title="No public repositories"
                    description="There is nothing public here for a connector to observe."
                  />
                </Card>
              ) : null}
            </section>

            {preview && preview.recent_commits.length > 0 ? (
              <Card>
                <CardHeader
                  title="Recent commits"
                  actions={<Label tone="attention">Real evidence, unpublished</Label>}
                />
                <CardBody>
                  {preview.recent_commits.map((commit) => (
                    <div className="commit-row" key={commit.sha}>
                      <CommitIcon size={15} className="text-subtle shrink-0" />
                      <a
                        className="commit-row__sha"
                        href={commit.html_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {commit.sha.slice(0, 7)}
                      </a>
                      <span className="commit-row__message">{commit.message}</span>
                      <span className="text-xs text-subtle shrink-0 hide-sm">
                        {commit.repository}
                      </span>
                    </div>
                  ))}
                </CardBody>
              </Card>
            ) : null}
          </div>

          <aside className="stack gap-4">
            {preview && preview.top_languages.length > 0 ? (
              <div className="sidebar-card">
                <p className="sidebar-card__title">Top languages</p>
                <div className="row row--wrap gap-2">
                  {preview.top_languages.map((language) => (
                    <Label key={language}>
                      <span className="lang-dot" />
                      {language}
                    </Label>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="sidebar-card">
              <p className="sidebar-card__title">What is missing here</p>
              <p className="text-sm text-muted">
                This is only what GitHub shows the world. A connected account produces hashed
                evidence versions, verification runs, contradiction checks, and a freshness signal —
                none of which a public scrape can give you.
              </p>
              <div className="mt-4 stack gap-2">
                <ButtonLink
                  href="/login"
                  variant="primary"
                  block
                  leadingIcon={<GitHubIcon size={15} />}
                >
                  Connect your account
                </ButtonLink>
                <Link href="/try" className="text-xs text-muted" style={{ textAlign: "center" }}>
                  Preview a different username
                </Link>
              </div>
            </div>

            <div className="sidebar-card">
              <p className="sidebar-card__title">Next step</p>
              <p className="text-sm text-muted">
                Connecting takes one authorization and produces a review queue, not a published
                page. You still decide what the world sees.
              </p>
              <div className="mt-3">
                <Button
                  variant="invisible"
                  size="sm"
                  onClick={() => {
                    window.location.href = "/#how-it-works";
                  }}
                  trailingIcon={<ArrowRightIcon size={14} />}
                >
                  How the pipeline works
                </Button>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </PublicShell>
  );
}
