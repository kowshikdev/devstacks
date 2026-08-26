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
        <h1>Your profile</h1>
      </section>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error-text">{error}</p>}

      {profile && (
        <section className="panel">
          <p>
            <strong>{profile.display_name ?? profile.handle}</strong>
          </p>
          <p className="muted">@{profile.handle}</p>
          <p className="muted">{profile.is_public ? "Public" : "Not public yet"}</p>
        </section>
      )}
    </AppShell>
  );
}
