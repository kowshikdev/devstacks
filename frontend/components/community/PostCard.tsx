import Link from "next/link";

import type { CommunityPost } from "../../lib/api/client";
import { Avatar } from "../ui/Avatar";
import { Label } from "../ui/Label";
import { RelativeTime } from "../ui/Time";
import { ShieldIcon } from "../ui/Icon";

const INTENT_LABEL: Record<string, string> = {
  help_request: "question",
  job_post: "job",
  showcase: "showcase",
  discussion: "discussion",
  hostile: "flagged",
  unknown: "post",
};

/**
 * Standing here is topic-matched evidence, not a participation score.
 *
 * Showing "verified in domain.distributed-systems" next to an answer tells a
 * reader something a karma number cannot: this person has shipped the thing
 * they are talking about, and DevStacks checked.
 */
export function AuthorLine({
  author,
  topics,
  at,
}: {
  author: CommunityPost["author"];
  topics: string[];
  at: string;
}) {
  const matched = author.verified_categories.filter((category) => topics.includes(category));

  return (
    <div className="row row--wrap gap-2">
      <Avatar name={author.display_name ?? author.handle} size={22} />
      <Link href={`/${author.handle}`} className="text-sm font-semibold">
        {author.display_name ?? author.handle}
      </Link>
      {matched.length > 0 ? (
        <Label tone="success" title={`Verified claims in ${matched.join(", ")}`}>
          <ShieldIcon size={11} />
          verified in {matched[0]}
          {matched.length > 1 ? ` +${matched.length - 1}` : ""}
        </Label>
      ) : author.verified_categories.length > 0 ? (
        <Label>{author.verified_categories.length} verified claims</Label>
      ) : null}
      <span className="text-xs text-subtle">
        <RelativeTime value={at} />
      </span>
    </div>
  );
}

export function ThreadRow({ post, topics }: { post: CommunityPost; topics: string[] }) {
  return (
    <article className="card__row" style={{ alignItems: "flex-start" }}>
      <div className="flex-1">
        <Link href={`/community/thread/${post.id}`} className="text-body font-semibold">
          {post.title}
        </Link>
        <p className="text-sm text-muted mt-1" style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
          {post.body}
        </p>
        <div className="row row--wrap gap-3 mt-3">
          <AuthorLine author={post.author} topics={topics} at={post.created_at} />
          <Label mono>{INTENT_LABEL[post.intent] ?? post.intent}</Label>
        </div>
      </div>
      <div className="text-xs text-subtle shrink-0 tabular">
        {post.reply_count} {post.reply_count === 1 ? "reply" : "replies"}
      </div>
    </article>
  );
}
