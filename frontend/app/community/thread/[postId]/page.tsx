"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import {
  ApiError,
  getCommunitySpace,
  getCommunityThread,
  type CommunityPost,
} from "../../../../lib/api/client";
import { PublicShell } from "../../../../components/AppShell";
import { Composer } from "../../../../components/community/Composer";
import { AuthorLine } from "../../../../components/community/PostCard";
import { ButtonLink } from "../../../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../../../components/ui/Card";
import { EmptyState, Flash, Skeleton } from "../../../../components/ui/Feedback";
import { Label } from "../../../../components/ui/Label";
import { getAccessToken } from "../../../../lib/supabase/client";
import { ChevronLeftIcon, InboxIcon } from "../../../../components/ui/Icon";

interface PageProps {
  params: Promise<{ postId: string }>;
}

export default function ThreadPage({ params }: PageProps) {
  const { postId } = use(params);

  const [thread, setThread] = useState<CommunityPost | null>(null);
  const [replies, setReplies] = useState<CommunityPost[] | null>(null);
  const [topics, setTopics] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [signedIn, setSignedIn] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await getCommunityThread(postId);
      setThread(result.thread);
      setReplies(result.replies);
      setError(null);
      // Topic categories live on the space, and decide which of an author's
      // verified claims are worth surfacing beside their words.
      const space = await getCommunitySpace(result.thread.space_slug).catch(() => null);
      setTopics(space?.space.topic_categories ?? []);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("This thread does not exist, or it is not published.");
      } else {
        setError(err instanceof ApiError ? err.message : "Could not load this thread");
      }
      setReplies([]);
    }
  }, [postId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void getAccessToken().then((token) => setSignedIn(Boolean(token)));
  }, []);

  return (
    <PublicShell>
      <div className="container container--lg">
        <nav className="breadcrumb mb-4" aria-label="Breadcrumb">
          <Link href="/community" className="row gap-1">
            <ChevronLeftIcon size={14} />
            Community
          </Link>
          {thread ? (
            <>
              <span className="breadcrumb__separator">/</span>
              <Link href={`/community/${thread.space_slug}`}>{thread.space_slug}</Link>
            </>
          ) : null}
        </nav>

        {error ? (
          <div className="mb-5">
            <Flash tone="danger" actions={<ButtonLink href="/community" size="sm">All spaces</ButtonLink>}>
              {error}
            </Flash>
          </div>
        ) : null}

        {thread === null && !error ? (
          <Card>
            <CardBody>
              <div className="stack gap-3">
                <Skeleton width="60%" height={26} />
                <Skeleton width="95%" height={14} />
                <Skeleton width="85%" height={14} />
              </div>
            </CardBody>
          </Card>
        ) : thread ? (
          <>
            <article className="mb-5">
              <h1 style={{ fontSize: "var(--text-h1)" }}>{thread.title}</h1>
              <div className="row row--wrap gap-3 mt-3">
                <AuthorLine author={thread.author} topics={topics} at={thread.created_at} />
                <Label mono>{thread.intent.replace("_", " ")}</Label>
              </div>
              <p className="mt-4 leading-relaxed" style={{ whiteSpace: "pre-wrap" }}>
                {thread.body}
              </p>
            </article>

            <Card className="mb-5">
              <CardHeader
                title="Replies"
                actions={
                  replies ? <span className="text-xs text-muted">{replies.length}</span> : null
                }
              />
              {replies === null ? (
                <CardBody>
                  <Skeleton width="80%" height={14} />
                </CardBody>
              ) : replies.length === 0 ? (
                <EmptyState
                  icon={<InboxIcon size={20} />}
                  title="No replies yet"
                  description="Answer with what you actually know."
                />
              ) : (
                <div>
                  {replies.map((reply) => (
                    <div className="card__row" style={{ alignItems: "flex-start" }} key={reply.id}>
                      <div className="flex-1">
                        <AuthorLine author={reply.author} topics={topics} at={reply.created_at} />
                        <p className="text-sm mt-2" style={{ whiteSpace: "pre-wrap" }}>
                          {reply.body}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {signedIn ? (
              <Composer
                spaceSlug={thread.space_slug}
                parentPostId={thread.id}
                onPosted={() => void load()}
              />
            ) : (
              <Card subtle>
                <CardBody>
                  <p className="text-sm text-muted">
                    Reading is open to everyone. Posting needs an account.
                  </p>
                  <div className="mt-3">
                    <ButtonLink href="/login" variant="primary">
                      Sign in to reply
                    </ButtonLink>
                  </div>
                </CardBody>
              </Card>
            )}
          </>
        ) : null}
      </div>
    </PublicShell>
  );
}
