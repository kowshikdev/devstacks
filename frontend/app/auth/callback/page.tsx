"use client";

import { useEffect, useState } from "react";

import { ApiError, getProfile } from "../../../lib/api/client";
import { getAccessToken } from "../../../lib/supabase/client";
import { ButtonLink } from "../../../components/ui/Button";
import { Card, CardBody } from "../../../components/ui/Card";
import { Flash, Spinner } from "../../../components/ui/Feedback";
import { DevStacksMark } from "../../../components/ui/Icon";

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
    void resolve();
  }, []);

  return (
    <div className="app-frame">
      <main
        className="container container--sm"
        id="main"
        style={{ display: "flex", alignItems: "center", minHeight: "100dvh" }}
      >
        <Card className="w-full">
          <CardBody>
            <DevStacksMark size={32} className="mb-4" />
            {error ? (
              <>
                <h1 style={{ fontSize: "var(--text-h3)" }}>Sign-in could not complete</h1>
                <div className="mt-4">
                  <Flash tone="danger">{error}</Flash>
                </div>
                <div className="mt-4">
                  <ButtonLink href="/login" variant="primary">
                    Back to sign in
                  </ButtonLink>
                </div>
              </>
            ) : (
              <>
                <h1 style={{ fontSize: "var(--text-h3)" }}>Completing sign-in…</h1>
                <p className="text-sm text-muted mt-2">
                  Establishing your session and locating your profile.
                </p>
                <div className="mt-4">
                  <Spinner label="Completing sign-in" />
                </div>
              </>
            )}
          </CardBody>
        </Card>
      </main>
    </div>
  );
}
