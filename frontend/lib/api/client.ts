import { getAccessToken } from "../supabase/client";

function getApiBaseUrl(): string {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_URL is required");
  }
  return apiBaseUrl;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");

  if (authenticated) {
    const accessToken = await getAccessToken();
    if (!accessToken) {
      throw new ApiError(401, "No active session");
    }
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export interface Profile {
  id: string;
  handle: string;
  display_name: string | null;
  is_public: boolean;
}

export interface PublishedClaim {
  id: string;
  category: string;
  statement: string;
  assurance_class: string | null;
  freshness_status: string | null;
  last_verified_at: string;
}

export interface PublishedProfile {
  id: string;
  handle: string;
  display_name: string | null;
  claims: PublishedClaim[];
}

export interface EvidenceExplanation {
  evidence_version_id: string;
  relation: "supports" | "contradicts" | "context";
  source_type: string;
  source_ref: string;
  assurance_class: string;
  validity: string;
}

export interface PendingClaimRevision {
  claim_revision_id: string;
  claim_id: string;
  category: string;
  statement: string;
  revision_number: number;
  created_at: string;
  latest_verification_status: string | null;
  latest_verifier_score: number | null;
  latest_review_status: string | null;
  latest_freshness_status: string | null;
  evidence: EvidenceExplanation[];
}

export function getProfile(): Promise<Profile> {
  return request<Profile>("/v1/profile");
}

export function createProfile(handle: string, displayName?: string): Promise<Profile> {
  return request<Profile>("/v1/profile", {
    method: "POST",
    body: JSON.stringify({ handle, display_name: displayName ?? null }),
  });
}

export function getPublicProfile(handle: string): Promise<PublishedProfile> {
  return request<PublishedProfile>(`/v1/public/profiles/${encodeURIComponent(handle)}`, {}, false);
}

export interface DemoRepository {
  name: string;
  html_url: string;
  description: string | null;
  language: string | null;
  stargazers_count: number;
  pushed_at: string | null;
}

export interface DemoCommit {
  repository: string;
  sha: string;
  message: string;
  html_url: string;
  authored_at: string | null;
}

export interface DemoPreview {
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  public_repos: number;
  top_languages: string[];
  repositories: DemoRepository[];
  recent_commits: DemoCommit[];
  is_preview: true;
}

export function getGithubDemoPreview(githubUsername: string): Promise<DemoPreview> {
  return request<DemoPreview>(
    "/v1/demo/github-preview",
    { method: "POST", body: JSON.stringify({ github_username: githubUsername }) },
    false
  );
}

export async function beginGithubAuth(): Promise<string> {
  const result = await request<{ authorization_url: string }>(
    "/v1/connectors/github/authorize",
    { method: "POST" }
  );
  return result.authorization_url;
}

export async function syncGithubConnection(connectionId: string): Promise<{ run_id: string }> {
  return request(`/v1/connectors/github/${encodeURIComponent(connectionId)}/sync`, {
    method: "POST",
    headers: { "Idempotency-Key": `${connectionId}-${Date.now()}` },
  });
}

export async function getPendingClaims(): Promise<PendingClaimRevision[]> {
  const result = await request<{ claims: PendingClaimRevision[] }>("/v1/claims?review=pending");
  return result.claims;
}

export function approveClaimRevision(claimRevisionId: string, note?: string): Promise<{ review_decision_id: string }> {
  return request(`/v1/claim-revisions/${encodeURIComponent(claimRevisionId)}/approve`, {
    method: "POST",
    body: JSON.stringify({ note: note ?? null }),
  });
}

export function rejectClaimRevision(claimRevisionId: string, note?: string): Promise<{ review_decision_id: string }> {
  return request(`/v1/claim-revisions/${encodeURIComponent(claimRevisionId)}/reject`, {
    method: "POST",
    body: JSON.stringify({ note: note ?? null }),
  });
}

export function editClaimRevision(
  claimRevisionId: string,
  body: { claim_id: string; category: string; statement: string }
): Promise<{ claim_id: string; claim_revision_id: string; revision_number: number }> {
  return request(`/v1/claim-revisions/${encodeURIComponent(claimRevisionId)}/edit`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function publishClaimRevision(claimRevisionId: string): Promise<{ publication_id: string }> {
  return request(`/v1/claim-revisions/${encodeURIComponent(claimRevisionId)}/publish`, {
    method: "POST",
  });
}
