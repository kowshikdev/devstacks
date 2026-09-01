import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { getPublicProfile, type PublishedClaim } from "../../lib/api/client";
import { PublicShell } from "../../components/AppShell";
import { Avatar } from "../../components/ui/Avatar";
import { ButtonLink } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { CopyButton } from "../../components/ui/CopyButton";
import { EmptyState } from "../../components/ui/Feedback";
import { Label } from "../../components/ui/Label";
import { RelativeTime } from "../../components/ui/Time";
import { formatAbsolute } from "../../lib/format/time";
import {
  CheckCircleIcon,
  ClockIcon,
  FingerprintIcon,
  GlobeIcon,
  GraphIcon,
  ShieldIcon,
  SparkIcon,
} from "../../components/ui/Icon";

/** The profile reflects live publication state, so it is never cached at build time. */
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ handle: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { handle } = await params;
  const profile = await getPublicProfile(handle).catch(() => null);
  const displayName = profile?.display_name ?? profile?.handle ?? handle;
  const claimCount = profile?.claims.length ?? 0;
  const description = profile
    ? `${claimCount} evidence-backed claim${claimCount === 1 ? "" : "s"}, verified against real source data.`
    : "Continuously verified developer evidence graph.";

  return {
    title: `${displayName} (@${handle})`,
    description,
    alternates: { canonical: `/${handle}` },
    openGraph: {
      title: `${displayName} (@${handle}) · DevStacks`,
      description,
      type: "profile",
    },
    twitter: {
      card: "summary_large_image",
      title: `${displayName} (@${handle}) · DevStacks`,
      description,
    },
  };
}

function assuranceTone(assurance: string | null) {
  switch (assurance) {
    case "verified":
      return "success" as const;
    case "self_attested":
    case "self-attested":
      return "attention" as const;
    case "inferred":
      return "info" as const;
    default:
      return "neutral" as const;
  }
}

export default async function PublicProfilePage({ params }: PageProps) {
  const { handle } = await params;

  const profile = await getPublicProfile(handle).catch(() => null);
  if (!profile) {
    notFound();
  }

  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "localhost:3000";
  const protocol = host.startsWith("localhost") ? "http" : "https";
  const profileUrl = `${protocol}://${host}/${profile.handle}`;
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
  const badgeUrl = `${apiBaseUrl}/v1/public/profiles/${encodeURIComponent(profile.handle)}/badge.svg`;
  const badgeMarkdown = `[![DevStacks](${badgeUrl})](${profileUrl})`;

  const displayName = profile.display_name ?? profile.handle;
  const verifiedClaims = profile.claims.filter((claim) => claim.assurance_class === "verified");
  const currentClaims = profile.claims.filter((claim) => claim.freshness_status === "current");
  const categories = Array.from(new Set(profile.claims.map((claim) => claim.category)));
  const lastVerified = profile.claims
    .map((claim) => claim.last_verified_at)
    .filter(Boolean)
    .sort()
    .at(-1);

  // Structured data so search engines and agents read the same facts as a human.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ProfilePage",
    dateModified: lastVerified,
    mainEntity: {
      "@type": "Person",
      name: displayName,
      alternateName: profile.handle,
      url: profileUrl,
    },
  };

  return (
    <PublicShell bare>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="profile-cover" />

      <div className="container">
        <header className="profile-head">
          <Avatar
            name={displayName}
            size={104}
            className="profile-head__avatar"
          />

          <div className="profile-head__row">
            <div>
              <h1 className="profile-head__name">{displayName}</h1>
              <p className="profile-head__handle">@{profile.handle}</p>
            </div>

            <div className="row row--wrap gap-2">
              <CopyButton value={profileUrl} label="Copy link" />
              <ButtonLink href="/try" variant="primary">
                Build your own
              </ButtonLink>
            </div>
          </div>

          <div className="profile-head__meta">
            <span className="row gap-2">
              <ShieldIcon size={15} className="text-success" />
              {verifiedClaims.length} verified
            </span>
            <span className="row gap-2">
              <GraphIcon size={15} />
              {profile.claims.length} published claim{profile.claims.length === 1 ? "" : "s"}
            </span>
            {lastVerified ? (
              <span className="row gap-2">
                <ClockIcon size={15} />
                Last verified <RelativeTime value={lastVerified} />
              </span>
            ) : null}
            <span className="row gap-2">
              <GlobeIcon size={15} />
              Public profile
            </span>
          </div>
        </header>

        <div className="profile-layout">
          {/* ---------- Claims ---------- */}
          <div className="stack gap-4">
            <div className="section-title">
              <h2 style={{ fontSize: "var(--text-h3)" }}>Published claims</h2>
              <span className="text-xs text-muted">
                {currentClaims.length} current · {profile.claims.length - currentClaims.length} aged
              </span>
            </div>

            {profile.claims.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<SparkIcon size={20} />}
                  title="No claims published yet"
                  description="This profile exists, but its owner has not published a claim revision. Nothing is shown until they do."
                />
              </Card>
            ) : (
              profile.claims.map((claim) => <ClaimCard claim={claim} key={claim.id} />)
            )}
          </div>

          {/* ---------- Sidebar ---------- */}
          <aside className="stack gap-4">
            <div className="sidebar-card">
              <p className="sidebar-card__title">Assurance</p>
              <div className="stack gap-3">
                <SidebarStat
                  label="Verified"
                  value={verifiedClaims.length}
                  hint="Observed directly by a connector"
                />
                <SidebarStat
                  label="Current"
                  value={currentClaims.length}
                  hint="Evidence has not aged out"
                />
                <SidebarStat
                  label="Categories"
                  value={categories.length}
                  hint="Distinct claim categories"
                />
              </div>
            </div>

            {categories.length > 0 ? (
              <div className="sidebar-card">
                <p className="sidebar-card__title">Categories</p>
                <div className="row row--wrap gap-2">
                  {categories.map((category) => (
                    <Label mono key={category}>
                      {category}
                    </Label>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="sidebar-card">
              <p className="sidebar-card__title">Embed</p>
              <p className="text-xs text-muted mb-3">
                Drop the badge into a README. It reflects the live verified-claim count.
              </p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={badgeUrl} alt={`DevStacks verified claim count for ${profile.handle}`} />
              <div className="embed-box mt-3">
                <code className="embed-box__code">{badgeMarkdown}</code>
              </div>
              <div className="mt-2">
                <CopyButton value={badgeMarkdown} label="Copy markdown" />
              </div>
            </div>

            <div className="sidebar-card">
              <p className="sidebar-card__title">How to read this</p>
              <ul className="stack gap-3">
                <li className="row row--start gap-2 text-xs text-muted">
                  <CheckCircleIcon size={14} className="text-success shrink-0" />
                  <span>
                    <strong>Verified</strong> claims come from a source DevStacks observed directly.
                  </span>
                </li>
                <li className="row row--start gap-2 text-xs text-muted">
                  <FingerprintIcon size={14} className="shrink-0" />
                  <span>
                    Every claim traces back to content-hashed, immutable evidence versions.
                  </span>
                </li>
                <li className="row row--start gap-2 text-xs text-muted">
                  <ClockIcon size={14} className="shrink-0" />
                  <span>
                    Freshness decays. An aged claim is labelled, not quietly presented as current.
                  </span>
                </li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </PublicShell>
  );
}

function ClaimCard({ claim }: { claim: PublishedClaim }) {
  const stale = claim.freshness_status !== null && claim.freshness_status !== "current";

  return (
    <article className="claim-card">
      <div className="claim-card__top">
        <Label mono>{claim.category}</Label>
        {claim.assurance_class ? (
          <Label tone={assuranceTone(claim.assurance_class)}>
            <ShieldIcon size={12} />
            {claim.assurance_class}
          </Label>
        ) : null}
        {claim.freshness_status ? (
          <Label tone={stale ? "attention" : "success"}>{claim.freshness_status}</Label>
        ) : null}
      </div>

      <p className="claim-card__statement">{claim.statement}</p>

      <div className="claim-card__meta">
        <span className="row gap-2">
          <ClockIcon size={13} />
          Verified <RelativeTime value={claim.last_verified_at} />
        </span>
        <span className="font-mono">{formatAbsolute(claim.last_verified_at)} UTC</span>
      </div>
    </article>
  );
}

function SidebarStat({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <div className="row row--between gap-3">
      <div>
        <p className="text-sm font-semibold">{label}</p>
        <p className="text-xs text-subtle">{hint}</p>
      </div>
      <span className="text-body font-bold tabular">{value}</span>
    </div>
  );
}
