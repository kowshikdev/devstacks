import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { getPublicProfile } from "../../lib/api/client";

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
    title: `${displayName} (@${handle}) · DevStacks`,
    description,
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

  return (
    <main className="dashboard dashboard--wide">
      <section className="intro">
        <p className="eyebrow">Public profile</p>
        <h1>{profile.display_name ?? profile.handle}</h1>
        <p className="muted">@{profile.handle}</p>
      </section>

      <div className="terminal glass">
        <div className="terminal-bar">
          <span />
          <span />
          <span />
          <span className="terminal-file">README.md</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "12px 16px" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem", color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {badgeMarkdown}
          </span>
          <img src={badgeUrl} alt={`${profile.handle} verified claim badge`} height={20} style={{ flexShrink: 0 }} />
        </div>
      </div>

      <ul className="claim-list">
        {profile.claims.map((claim) => (
          <li key={claim.id} className="review-card">
            <p className="claim-category">{claim.category}</p>
            <p className="claim-statement">{claim.statement}</p>
            <div className="status-pills">
              {claim.assurance_class && <span className="status-pill">{claim.assurance_class}</span>}
              {claim.freshness_status && (
                <span className={`status-pill status-${claim.freshness_status}`}>
                  {claim.freshness_status}
                </span>
              )}
              <span className="status-pill">last verified {claim.last_verified_at}</span>
            </div>
          </li>
        ))}
      </ul>

      {profile.claims.length === 0 && <p className="muted">No published claims yet.</p>}
    </main>
  );
}
