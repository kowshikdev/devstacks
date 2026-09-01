"use client";

/**
 * Local record of the most recent GitHub connection.
 *
 * The API deliberately never returns connector tokens, and there is no
 * connector-listing endpoint yet, so the OAuth callback's `connection_id` and
 * `github_login` are kept here to drive the connections surface. This is a
 * display convenience only — every privileged action is still authorized
 * server-side against the caller's own connection.
 */
const STORAGE_KEY = "devstacks-github-connection";

export interface StoredConnection {
  connectionId: string;
  githubLogin: string | null;
  connectedAt: string;
}

export function readConnection(): StoredConnection | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredConnection>;
    if (!parsed.connectionId) return null;
    return {
      connectionId: parsed.connectionId,
      githubLogin: parsed.githubLogin ?? null,
      connectedAt: parsed.connectedAt ?? new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

export function writeConnection(connection: Omit<StoredConnection, "connectedAt">): void {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...connection, connectedAt: new Date().toISOString() })
    );
  } catch {
    // Storage can be unavailable; the connection still exists server-side.
  }
}

export function clearConnection(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to recover from — the next read simply returns null.
  }
}
