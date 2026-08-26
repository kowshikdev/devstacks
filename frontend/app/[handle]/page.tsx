import { notFound } from "next/navigation";

import { getPublicProfile } from "../../lib/api/client";

interface PageProps {
  params: Promise<{ handle: string }>;
}

export default async function PublicProfilePage({ params }: PageProps) {
  const { handle } = await params;

  const profile = await getPublicProfile(handle).catch(() => null);
  if (!profile) {
    notFound();
  }

  return (
    <main className="dashboard">
      <section className="intro">
        <p className="eyebrow">Public profile</p>
        <h1>{profile.display_name ?? profile.handle}</h1>
        <p className="muted">@{profile.handle}</p>
      </section>

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
