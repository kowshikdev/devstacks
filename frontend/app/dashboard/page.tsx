"use client";

import { useEffect, useState } from "react";

import AppShell from "../../components/AppShell";
import { toHeaderUser, useProfile } from "../../lib/hooks/useProfile";
import { ApiError, getPendingClaims, type PendingClaimRevision } from "../../lib/api/client";
import { Avatar } from "../../components/ui/Avatar";
import { ButtonLink } from "../../components/ui/Button";
import { Card, CardBody, CardFooter, CardHeader } from "../../components/ui/Card";
import { CopyButton } from "../../components/ui/CopyButton";
import { EmptyState, Flash, Skeleton } from "../../components/ui/Feedback";
import { Label, StateLabel } from "../../components/ui/Label";
import { RelativeTime } from "../../components/ui/Time";
import {
  ArrowRightIcon,
  CheckIcon,
  ClockIcon,
  GitHubIcon,
  GlobeIcon,
  GraphIcon,
  InboxIcon,
  LockIcon,
  PlugIcon,
  ShieldIcon,
  SparkIcon,
} from "../../components/ui/Icon";

const LIFECYCLE = [
  {
    icon: <PlugIcon size={13} />,
    title: "A connector observes",
    body: "Commits, pull requests, and releases are read and content-hashed into immutable evidence versions.",
  },
  {
    icon: <GraphIcon size={13} />,
    title: "A revision is proposed",
    body: "Interpretation is structured over that evidence and arrives here as a proposal — never as a published fact.",
  },
  {
    icon: <ShieldIcon size={13} />,
    title: "Verification runs",
    body: "Supporting and contradicting evidence are scored, and a freshness signal is attached.",
  },
  {
    icon: <GlobeIcon size={13} />,
    title: "You decide",
    body: "Approve, edit, or reject. Only an explicit publish puts a claim on your public profile.",
  },
];

export default function DashboardPage() {
  const { profile, loading: profileLoading, error: profileError } = useProfile();
  const [claims, setClaims] = useState<PendingClaimRevision[] | null>(null);
  const [claimsError, setClaimsError] = useState<string | null>(null);

  useEffect(() => {
    if (!profile) return;
    let cancelled = false;
    getPendingClaims()
      .then((result) => {
        if (!cancelled) setClaims(result);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setClaimsError(err instanceof ApiError ? err.message : "Could not load pending claims");
        setClaims([]);
      });
    return () => {
      cancelled = true;
    };
  }, [profile]);

  const pendingCount = claims?.length ?? 0;
  const verifiedCount =
    claims?.filter((claim) => claim.latest_verification_status === "verified").length ?? 0;
  const evidenceCount = claims?.reduce((total, claim) => total + claim.evidence.length, 0) ?? 0;
  const staleCount = claims?.filter((claim) => claim.latest_freshness_status === "stale").length ?? 0;

  const profileUrl =
    typeof window !== "undefined" && profile ? `${window.location.origin}/${profile.handle}` : "";

  const setupSteps = [
    {
      done: Boolean(profile),
      title: "Create your profile",
      description: "Your handle reserves your public URL.",
      action: null,
    },
    {
      done: (claims?.length ?? 0) > 0 || evidenceCount > 0,
      title: "Connect a source",
      description: "GitHub is the golden path — commits, pull requests, and releases.",
      action: { href: "/dashboard/connect/github", label: "Connect GitHub" },
    },
    {
      done: pendingCount === 0 && (claims?.length ?? 0) === 0 && Boolean(profile?.is_public),
      title: "Review proposed claims",
      description: "Approve, edit, or reject each revision before it can publish.",
      action: { href: "/dashboard/review", label: "Open review" },
    },
    {
      done: Boolean(profile?.is_public),
      title: "Publish your profile",
      description: "Publishing is deliberate — a claim reaches the public page only when you say so.",
      action: { href: "/dashboard/review", label: "Publish a claim" },
    },
  ];

  const completed = setupSteps.filter((step) => step.done).length;

  return (
    <AppShell user={toHeaderUser(profile)} reviewCount={pendingCount || undefined}>
      <div className="page-header">
        <div>
          <span className="eyebrow">Overview</span>
          <h1 className="page-header__title mt-1">
            {profileLoading ? "Loading…" : `Welcome back, ${profile?.display_name ?? profile?.handle ?? ""}`}
          </h1>
          <p className="page-header__description">
            Everything DevStacks has observed, what it proposes, and what you have chosen to publish.
          </p>
        </div>
        <div className="page-header__actions">
          {profile ? (
            <ButtonLink href={`/${profile.handle}`} leadingIcon={<GlobeIcon size={15} />}>
              View public profile
            </ButtonLink>
          ) : null}
          <ButtonLink
            href="/dashboard/review"
            variant="primary"
            leadingIcon={<InboxIcon size={15} />}
          >
            Review queue
          </ButtonLink>
        </div>
      </div>

      {profileError ? (
        <div className="mb-5">
          <Flash tone="danger">{profileError}</Flash>
        </div>
      ) : null}

      <div className="stat-grid mb-5">
        <StatTile
          icon={<InboxIcon size={14} />}
          label="Pending review"
          value={claims === null ? null : pendingCount}
          note={pendingCount > 0 ? "Waiting on your decision" : "Inbox is clear"}
        />
        <StatTile
          icon={<ShieldIcon size={14} />}
          label="Verified revisions"
          value={claims === null ? null : verifiedCount}
          note="Passed a verification run"
        />
        <StatTile
          icon={<GraphIcon size={14} />}
          label="Evidence linked"
          value={claims === null ? null : evidenceCount}
          note="Immutable versions in play"
        />
        <StatTile
          icon={<ClockIcon size={14} />}
          label="Stale"
          value={claims === null ? null : staleCount}
          note={staleCount > 0 ? "Evidence has aged out" : "All evidence current"}
        />
      </div>

      <div className="dashboard-grid">
        {/* ---------- Main column ---------- */}
        <div className="stack gap-5">
          <Card>
            <CardHeader
              title="Pending claim revisions"
              actions={
                <ButtonLink
                  href="/dashboard/review"
                  size="sm"
                  variant="invisible"
                  trailingIcon={<ArrowRightIcon size={14} />}
                >
                  Open review
                </ButtonLink>
              }
            />
            {claims === null ? (
              <CardBody>
                <div className="stack gap-4">
                  {[0, 1, 2].map((row) => (
                    <div className="stack gap-2" key={row}>
                      <Skeleton width="30%" height={10} />
                      <Skeleton width="85%" height={14} />
                    </div>
                  ))}
                </div>
              </CardBody>
            ) : claimsError ? (
              <CardBody>
                <Flash tone="danger">{claimsError}</Flash>
              </CardBody>
            ) : claims.length === 0 ? (
              <EmptyState
                icon={<CheckIcon size={20} />}
                title="Nothing waiting on you"
                description="New claim revisions appear here as soon as a connector observes something worth interpreting."
                action={
                  <ButtonLink href="/dashboard/connections" leadingIcon={<PlugIcon size={15} />}>
                    Manage connections
                  </ButtonLink>
                }
              />
            ) : (
              <>
                {claims.slice(0, 5).map((claim) => (
                  <div className="card__row" key={claim.claim_revision_id}>
                    <div className="flex-1">
                      <div className="row row--wrap gap-2 mb-2">
                        <Label mono>{claim.category}</Label>
                        <StateLabel status={claim.latest_verification_status} />
                        {claim.latest_freshness_status ? (
                          <Label
                            tone={claim.latest_freshness_status === "stale" ? "attention" : "neutral"}
                          >
                            {claim.latest_freshness_status}
                          </Label>
                        ) : null}
                      </div>
                      <p className="text-sm font-semibold">{claim.statement}</p>
                      <p className="text-xs text-subtle mt-1">
                        revision {claim.revision_number} · {claim.evidence.length} evidence
                        {claim.evidence.length === 1 ? "" : " versions"} ·{" "}
                        <RelativeTime value={claim.created_at} />
                      </p>
                    </div>
                  </div>
                ))}
                {claims.length > 5 ? (
                  <CardFooter>
                    <span className="text-xs text-muted">
                      {claims.length - 5} more waiting in the review inbox.
                    </span>
                  </CardFooter>
                ) : null}
              </>
            )}
          </Card>

          <Card>
            <CardHeader title="Where a claim goes from here" />
            <CardBody>
              <ol className="timeline">
                {LIFECYCLE.map((stage) => (
                  <li className="timeline__item" key={stage.title}>
                    <span className="timeline__marker">{stage.icon}</span>
                    <p className="text-sm font-semibold">{stage.title}</p>
                    <p className="text-xs text-muted mt-1" style={{ maxWidth: "62ch" }}>
                      {stage.body}
                    </p>
                  </li>
                ))}
              </ol>
            </CardBody>
          </Card>
        </div>

        {/* ---------- Sidebar ---------- */}
        <div className="stack gap-5">
          <Card>
            <CardBody>
              {profileLoading ? (
                <div className="row gap-3">
                  <Skeleton width={48} height={48} radius={999} />
                  <div className="flex-1 stack gap-2">
                    <Skeleton width="60%" height={14} />
                    <Skeleton width="40%" height={10} />
                  </div>
                </div>
              ) : profile ? (
                <>
                  <div className="row gap-3">
                    <Avatar name={profile.display_name ?? profile.handle} size={48} />
                    <div className="flex-1">
                      <p className="font-semibold truncate">
                        {profile.display_name ?? profile.handle}
                      </p>
                      <p className="text-xs text-muted font-mono">@{profile.handle}</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    {profile.is_public ? (
                      <Label tone="success">
                        <GlobeIcon size={12} />
                        Public
                      </Label>
                    ) : (
                      <Label tone="attention">
                        <LockIcon size={12} />
                        Not published yet
                      </Label>
                    )}
                  </div>
                  {profileUrl ? (
                    <div className="embed-box mt-4">
                      <code className="embed-box__code">{profileUrl}</code>
                      <CopyButton value={profileUrl} label="Copy" variant="invisible" />
                    </div>
                  ) : null}
                </>
              ) : null}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Setup"
              actions={
                <span className="text-xs text-muted tabular">
                  {completed}/{setupSteps.length}
                </span>
              }
            />
            <div>
              {setupSteps.map((step) => (
                <div className="checklist__item" key={step.title}>
                  <span
                    className={["checklist__mark", step.done ? "checklist__mark--done" : ""]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    {step.done ? <CheckIcon size={12} /> : null}
                  </span>
                  <div className="flex-1">
                    <p className="checklist__title">{step.title}</p>
                    <p className="checklist__description">{step.description}</p>
                    {!step.done && step.action ? (
                      <ButtonLink href={step.action.href} size="sm" className="mt-2">
                        {step.action.label}
                      </ButtonLink>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card subtle>
            <CardBody>
              <div className="row gap-2 mb-2">
                <SparkIcon size={15} className="text-accent" />
                <p className="text-sm font-semibold">Add another source</p>
              </div>
              <p className="text-xs text-muted">
                GitHub is live today. LinkedIn export, HackerRank certificates, and LeetCode
                snapshots follow the same evidence contract.
              </p>
              <div className="mt-3">
                <ButtonLink
                  href="/dashboard/connections"
                  size="sm"
                  leadingIcon={<GitHubIcon size={14} />}
                >
                  Manage connections
                </ButtonLink>
              </div>
            </CardBody>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

function StatTile({
  icon,
  label,
  value,
  note,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | null;
  note: string;
}) {
  return (
    <div className="stat-tile">
      <p className="stat-tile__label">
        {icon}
        {label}
      </p>
      {value === null ? (
        <div className="mt-2">
          <Skeleton width={48} height={26} />
        </div>
      ) : (
        <p className="stat-tile__value">{value}</p>
      )}
      <p className="stat-tile__note">{note}</p>
    </div>
  );
}
