import type { Metadata } from "next";
import Link from "next/link";

import { listCommunitySpaces } from "../../lib/api/client";
import { PublicShell } from "../../components/AppShell";
import { Card, CardBody } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/Feedback";
import { Label } from "../../components/ui/Label";
import {
  ArrowRightIcon,
  FingerprintIcon,
  ShieldIcon,
  SparkIcon,
  UserIcon,
} from "../../components/ui/Icon";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Community",
  description:
    "Developer spaces where standing comes from verified evidence, every post is checked before it lands, and every moderation decision shows its reasoning.",
};

const PRINCIPLES = [
  {
    icon: <ShieldIcon size={18} />,
    title: "Voice is earned by evidence",
    body: "An answer carries the author's verified, topic-matched claims — not a karma score. Reputation here is something you shipped, and DevStacks checked it.",
  },
  {
    icon: <SparkIcon size={18} />,
    title: "The composer is a linter",
    body: "Guardrails run before you post and explain themselves. Leaked credentials, hostility aimed at a person, and link dumps are caught while you can still fix them.",
  },
  {
    icon: <FingerprintIcon size={18} />,
    title: "Moderation shows its work",
    body: "Every decision records the rule that fired, the policy version, and the reason. Nobody is moderated in secret; an author can always see why.",
  },
];

export default async function CommunityPage() {
  const spaces = await listCommunitySpaces().catch(() => null);

  return (
    <PublicShell>
      <div className="container">
        <div className="page-header">
          <div>
            <span className="eyebrow">Community</span>
            <h1 className="page-header__title mt-1">Spaces</h1>
            <p className="page-header__description">
              Somewhere to get unstuck, argue about architecture, show what you built, or hire.
              Criticise the code as harshly as you like — not the person.
            </p>
          </div>
        </div>

        <div className="feature-grid mb-6">
          {PRINCIPLES.map((principle) => (
            <article className="feature" key={principle.title}>
              <span className="feature__icon">{principle.icon}</span>
              <h2 className="feature__title">{principle.title}</h2>
              <p className="feature__body">{principle.body}</p>
            </article>
          ))}
        </div>

        {spaces === null ? (
          <Card>
            <EmptyState
              icon={<UserIcon size={20} />}
              title="Community is unavailable"
              description="The community service could not be reached. Try again shortly."
            />
          </Card>
        ) : spaces.length === 0 ? (
          <Card>
            <EmptyState
              icon={<UserIcon size={20} />}
              title="No spaces yet"
              description="Spaces appear here once they are created."
            />
          </Card>
        ) : (
          <div className="stack gap-3">
            {spaces.map((space) => (
              <Link key={space.slug} href={`/community/${space.slug}`} style={{ textDecoration: "none" }}>
                <Card interactive>
                  <CardBody>
                    <div className="row row--between row--wrap gap-3">
                      <div className="flex-1">
                        <p className="text-body font-semibold">{space.name}</p>
                        <p className="text-sm text-muted mt-1">{space.description}</p>
                        <div className="row row--wrap gap-2 mt-3">
                          {space.allowed_intents.map((intent) => (
                            <Label key={intent} mono>
                              {intent.replace("_", " ")}
                            </Label>
                          ))}
                        </div>
                      </div>
                      <ArrowRightIcon size={16} className="text-subtle shrink-0" />
                    </div>
                  </CardBody>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </PublicShell>
  );
}
