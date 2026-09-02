import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { getPublicClaimTrail, type PublishedEvidence } from "../../../../lib/api/client";
import { PublicShell } from "../../../../components/AppShell";
import { ButtonLink } from "../../../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../../../components/ui/Card";
import { CopyButton } from "../../../../components/ui/CopyButton";
import { EmptyState } from "../../../../components/ui/Feedback";
import { Label } from "../../../../components/ui/Label";
import { RelativeTime } from "../../../../components/ui/Time";
import { formatAbsolute } from "../../../../lib/format/time";
import {
  ChevronLeftIcon,
  ClockIcon,
  FingerprintIcon,
  GraphIcon,
  LockIcon,
  ShieldIcon,
} from "../../../../components/ui/Icon";

/** Publication state changes independently of any deploy. */
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ handle: string; claimId: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { handle, claimId } = await params;
  const trail = await getPublicClaimTrail(handle, claimId).catch(() => null);
  if (!trail) {
    return {
      title: "Evidence trail not found",
      // See the note on the profile page: a missing claim can render as a soft
      // 404, so it must not be indexed.
      robots: { index: false, follow: false },
    };
  }
  const supporting = trail.evidence.filter((item) => item.relation === "supports").length;
  return {
    title: `Evidence for a claim by @${handle}`,
    description: `${trail.statement} — ${supporting} supporting evidence version${supporting === 1 ? "" : "s"}, ${trail.verification_status}.`,
    alternates: { canonical: `/${handle}/claims/${claimId}` },
  };
}

const RELATION_ORDER: PublishedEvidence["relation"][] = ["supports", "contradicts", "context"];

const RELATION_COPY: Record<PublishedEvidence["relation"], { title: string; note: string }> = {
  supports: {
    title: "Supporting evidence",
    note: "Observations consistent with the claim.",
  },
  contradicts: {
    title: "Contradicting evidence",
    note: "Observations that argue against the claim. They are shown because hiding them would make the rest worthless.",
  },
  context: {
    title: "Context",
    note: "Observations that inform the claim without arguing either way.",
  },
};

export default async function ClaimEvidencePage({ params }: PageProps) {
  const { handle, claimId } = await params;

  const trail = await getPublicClaimTrail(handle, claimId).catch(() => null);
  if (!trail) {
    notFound();
  }

  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "localhost:3000";
  const protocol = host.startsWith("localhost") ? "http" : "https";
  const pageUrl = `${protocol}://${host}/${trail.handle}/claims/${trail.claim_revision_id}`;

  const verified = trail.verification_status === "verified";
  const stale = trail.freshness_status !== null && trail.freshness_status !== "current";
  const grouped = RELATION_ORDER.map((relation) => ({
    relation,
    items: trail.evidence.filter((item) => item.relation === relation),
  })).filter((group) => group.items.length > 0);

  return (
    <PublicShell>
      <div className="container container--lg">
        <nav className="breadcrumb mb-4" aria-label="Breadcrumb">
          <Link href={`/${trail.handle}`} className="row gap-1">
            <ChevronLeftIcon size={14} />
            {trail.display_name ?? `@${trail.handle}`}
          </Link>
          <span className="breadcrumb__separator">/</span>
          <span>Evidence trail</span>
        </nav>

        <header className="mb-6">
          <span className="eyebrow">Evidence trail</span>
          <h1 className="mt-2" style={{ fontSize: "var(--text-h1)" }}>
            {trail.statement}
          </h1>

          <div className="row row--wrap gap-2 mt-4">
            <Label mono>{trail.category}</Label>
            <Label tone={verified ? "success" : "attention"}>
              <ShieldIcon size={12} />
              {trail.verification_status}
              {trail.verifier_score !== null ? ` · ${trail.verifier_score.toFixed(2)}` : ""}
            </Label>
            {trail.freshness_status ? (
              <Label tone={stale ? "attention" : "success"}>{trail.freshness_status}</Label>
            ) : null}
            <Label>
              <GraphIcon size={12} />
              {trail.evidence.length} evidence version
              {trail.evidence.length === 1 ? "" : "s"}
            </Label>
          </div>

          <p className="text-sm text-muted mt-4" style={{ maxWidth: "72ch" }}>
            Every published claim on DevStacks rests on observations that were content-hashed when
            they were collected. This page is that chain. A hash changes if the observation
            changes, so the record cannot be quietly rewritten after the fact.
          </p>
        </header>

        <div className="profile-layout" style={{ paddingTop: 0 }}>
          <div className="stack gap-4">
            {grouped.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<GraphIcon size={20} />}
                  title="No evidence is linked to this claim"
                  description="A published claim with no linked evidence cannot be independently checked. Treat it as unsupported."
                />
              </Card>
            ) : (
              grouped.map((group) => (
                <section key={group.relation}>
                  <Card>
                    <CardHeader
                      title={RELATION_COPY[group.relation].title}
                      actions={<span className="text-xs text-muted">{group.items.length}</span>}
                    />
                    <CardBody>
                      <p className="text-xs text-muted mb-4">{RELATION_COPY[group.relation].note}</p>
                      <div className="stack gap-3">
                        {group.items.map((item) => (
                          <EvidenceCard item={item} key={item.evidence_version_id} />
                        ))}
                      </div>
                    </CardBody>
                  </Card>
                </section>
              ))
            )}
          </div>

          <aside className="stack gap-4">
            <div className="sidebar-card">
              <p className="sidebar-card__title">Verification</p>
              <dl className="stack gap-3">
                <TrailFact label="Status" value={trail.verification_status} />
                <TrailFact
                  label="Score"
                  value={trail.verifier_score !== null ? trail.verifier_score.toFixed(3) : "not scored"}
                />
                <TrailFact label="Decided" value={formatAbsolute(trail.verified_at)} />
                {trail.published_at ? (
                  <TrailFact label="Published" value={formatAbsolute(trail.published_at)} />
                ) : null}
              </dl>
            </div>

            <div className="sidebar-card">
              <p className="sidebar-card__title">What is not here</p>
              <ul className="stack gap-3">
                <li className="row row--start gap-2 text-xs text-muted">
                  <LockIcon size={14} className="shrink-0" />
                  <span>
                    The observed payload itself stays private. You see that an observation exists
                    and is fixed, not its contents.
                  </span>
                </li>
                <li className="row row--start gap-2 text-xs text-muted">
                  <LockIcon size={14} className="shrink-0" />
                  <span>
                    Source references are withheld, because one can name a private repository. The
                    hash proves integrity without that disclosure.
                  </span>
                </li>
              </ul>
            </div>

            <div className="sidebar-card">
              <p className="sidebar-card__title">Cite this trail</p>
              <div className="embed-box">
                <code className="embed-box__code">{pageUrl}</code>
              </div>
              <div className="mt-2">
                <CopyButton value={pageUrl} label="Copy link" />
              </div>
              <div className="mt-4">
                <ButtonLink href={`/${trail.handle}`} block>
                  All published claims
                </ButtonLink>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </PublicShell>
  );
}

function TrailFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="row row--between gap-3">
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="text-xs font-semibold" style={{ margin: 0, textAlign: "right" }}>
        {value}
      </dd>
    </div>
  );
}

function EvidenceCard({ item }: { item: PublishedEvidence }) {
  const current = item.validity === "current";

  return (
    <article className="card card--subtle">
      <CardBody>
        <div className="row row--between row--wrap gap-3">
          <div className="row gap-2">
            <FingerprintIcon size={15} className="text-subtle" />
            <span className="text-sm font-semibold font-mono">{item.source_type}</span>
          </div>
          <div className="row row--wrap gap-2">
            <Label tone={item.assurance_class === "verified" ? "success" : "neutral"}>
              {item.assurance_class}
            </Label>
            <Label tone={current ? "accent" : "attention"}>{item.validity}</Label>
          </div>
        </div>

        <div className="embed-box mt-3">
          <code className="embed-box__code" title={item.content_hash}>
            {item.content_hash}
          </code>
          <CopyButton value={item.content_hash} label="Copy hash" variant="invisible" />
        </div>

        <div className="row row--wrap gap-4 mt-3 text-xs text-subtle">
          <span>version {item.version_number}</span>
          <span className="font-mono">{item.connector_version}</span>
          {item.observed_at ? (
            <span className="row gap-1">
              <ClockIcon size={12} />
              observed <RelativeTime value={item.observed_at} />
            </span>
          ) : null}
        </div>
      </CardBody>
    </article>
  );
}
