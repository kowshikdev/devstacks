"use client";

import { useEffect, useState } from "react";

import { ApiError, getProfile } from "../../../lib/api/client";
import { getAccessToken } from "../../../lib/supabase/client";

export default function AuthCallbackPage() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // supabase-js's detectSessionInUrl (default true) parses the OAuth
    // redirect and establishes the session client-side before this runs.
    async function resolve() {
      const token = await getAccessToken();
      if (!token) {
        setError("Sign-in did not complete. Try again.");
        return;
      }
      try {
        await getProfile();
        window.location.href = "/dashboard";
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          window.location.href = "/onboarding";
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load your profile");
      }
    }
    resolve();
  }, []);

  return (
    <main className="dashboard">
      <section className="intro">
        <p className="eyebrow">Signing in</p>
        <h1>One moment…</h1>
      </section>
      {error && <p className="error-text">{error}</p>}
    </main>
  );
}
