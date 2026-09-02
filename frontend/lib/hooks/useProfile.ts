"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, getProfile, type Profile } from "../api/client";

export interface ProfileState {
  profile: Profile | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Loads the caller's own profile for every signed-in surface.
 *
 * The two auth outcomes are routing decisions rather than errors: no session
 * belongs at /login, and an authenticated subject with no profile row belongs
 * at /onboarding. Everything else is surfaced to the page.
 */
export function useProfile(): ProfileState {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    getProfile()
      .then((result) => {
        if (!cancelled) setProfile(result);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          window.location.href = "/login";
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          window.location.href = "/onboarding";
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load your profile");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  return { profile, loading, error, reload };
}

/** Shapes a profile for the header without leaking API types into the chrome. */
export function toHeaderUser(profile: Profile | null) {
  if (!profile) return null;
  return { handle: profile.handle, displayName: profile.display_name };
}
