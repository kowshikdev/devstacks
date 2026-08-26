"use client";

import { useEffect, useState } from "react";

import AppShell from "../../components/AppShell";
import { ApiError, getProfile, type Profile } from "../../lib/api/client";

export default function DashboardPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getProfile()
      .then(setProfile)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          window.location.href = "/login";
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          window.location.href = "/onboarding";
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load profile");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell>
      <section className="intro">
        <p className="eyebrow">Dashboard</p>
        <h1>
          Your <em>profile</em>
        </h1>
      </section>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error-text">{error}</p>}

      {profile && (
        <section className="panel" style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 18 }}>
          <div
            aria-hidden="true"
            style={{
              width: 52,
              height: 52,
              flexShrink: 0,
              borderRadius: "50%",
              background: "linear-gradient(160deg, var(--accent-strong), var(--accent))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--accent-contrast)",
              fontWeight: 600,
              fontSize: 18,
            }}
          >
            {(profile.display_name ?? profile.handle).slice(0, 2).toUpperCase()}
          </div>
          <div>
            <strong>{profile.display_name ?? profile.handle}</strong>
            <p className="muted" style={{ margin: "2px 0 8px" }}>
              @{profile.handle}
            </p>
            <span className={profile.is_public ? "status-pill status-current" : "status-pill"}>
              {profile.is_public ? "Public" : "Not public yet"}
            </span>
          </div>
        </section>
      )}
    </AppShell>
  );
}
