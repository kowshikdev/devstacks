"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import {
  ApiError,
  getCommunitySpace,
  type CommunityPost,
  type CommunitySpace,
} from "../../../lib/api/client";
import { PublicShell } from "../../../components/AppShell";
import { Composer } from "../../../components/community/Composer";
import { ThreadRow } from "../../../components/community/PostCard";
import { ButtonLink } from "../../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { EmptyState, Flash, Skeleton } from "../../../components/ui/Feedback";
import { Label } from "../../../components/ui/Label";
import { getAccessToken } from "../../../lib/supabase/client";
import { ChevronLeftIcon, InboxIcon, ShieldIcon } from "../../../components/ui/Icon";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export default function SpacePage({ params }: PageProps) {
  const { slug } = use(params);

  const [space, setSpace] = useState<CommunitySpace | null>(null);
  const [threads, setThreads] = useState<CommunityPost[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [signedIn, setSignedIn] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await getCommunitySpace(slug);
      setSpace(result.space);
      setThreads(result.threads);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError(`No space called "${slug}".`);
      } else {
        setError(err instanceof ApiError ? err.message : "Could not load this space");
      }
      setThreads([]);
    }
  }, [slug]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void getAccessToken().then((token) => setSignedIn(Boolean(token)));
  }, []);

  const topics = space?.topic_categories ?? [];

  return (
    <PublicShell>
      <div className="container">
        <nav className="breadcrumb mb-4" aria-label="Breadcrumb">
          <Link href="/community" className="row gap-1">
            <ChevronLeftIcon size={14} />
            Community
          </Link>
          <span className="breadcrumb__separator">/</span>
          <span>{space?.name ?? slug}</span>
        </nav>

        {error ? (
          <div className="mb-5">
            <Flash tone="danger">{error}</Flash>
          </div>
        ) : null}

        <div className="page-header">
          <div>
            <h1 className="page-header__title">
              {space?.name ?? <Skeleton width={220} height={26} />}
            </h1>
            {space ? <p className="page-header__description">{space.description}</p> : null}
            {space && space.allowed_intents.length > 0 ? (
              <div className="row row--wrap gap-2 mt-3">
                <span className="text-xs text-subtle">Accepts:</span>
                {space.allowed_intents.map((intent) => (
                  <Label key={intent} mono>
                    {intent.replace("_", " ")}
                  </Label>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <div className="dashboard-grid">
          <div className="stack gap-4">
            {signedIn ? (
              <div className="stack gap-3">
                <p className="section-title" style={{ margin: 0 }}>
                  Start a thread
                </p>
                <Composer spaceSlug={slug} onPosted={() => void load()} />
              </div>
            ) : null}

            <Card>
              <CardHeader
                title="Threads"
                actions={
                  threads ? <span className="text-xs text-muted">{threads.length}</span> : null
                }
              />
              {threads === null ? (
                <CardBody>
                  <div className="stack gap-4">
                    {[0, 1, 2].map((row) => (
                      <div className="stack gap-2" key={row}>
                        <Skeleton width="55%" height={14} />
                        <Skeleton width="90%" height={12} />
                      </div>
                    ))}
                  </div>
                </CardBody>
              ) : threads.length === 0 ? (
                <EmptyState
                  icon={<InboxIcon size={20} />}
                  title="No threads yet"
                  description="Be the first to post here."
                />
              ) : (
                <div>
                  {threads.map((thread) => (
                    <ThreadRow post={thread} topics={topics} key={thread.id} />
                  ))}
                </div>
              )}
            </Card>
          </div>

          <aside className="stack gap-4">
            {signedIn ? null : (
              <div className="sidebar-card">
                <p className="sidebar-card__title">Join the conversation</p>
                <p className="text-sm text-muted">
                  Reading is open to everyone. Posting needs an account, so every voice here can
                  carry the evidence behind it.
                </p>
                <div className="mt-3">
                  <ButtonLink href="/login" variant="primary" block>
                    Sign in to post
                  </ButtonLink>
                </div>
              </div>
            )}

            {topics.length > 0 ? (
              <div className="sidebar-card">
                <p className="sidebar-card__title">Topics</p>
                <p className="text-xs text-muted mb-3">
                  Members with verified claims in these categories are shown as such on their posts.
                </p>
                <div className="row row--wrap gap-2">
                  {topics.map((topic) => (
                    <Label key={topic} mono>
                      <ShieldIcon size={11} />
                      {topic}
                    </Label>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="sidebar-card">
              <p className="sidebar-card__title">How moderation works here</p>
              <ul className="stack gap-3 text-xs text-muted">
                <li>Guardrails run before you post and tell you what they found.</li>
                <li>Strong language about code is fine. Language aimed at a person is not.</li>
                <li>A leaked credential is blocked to protect you, and you are told to rotate it.</li>
                <li>Every decision records the rule and reason, and you can always see yours.</li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </PublicShell>
  );
}
