"use client";

import { useEffect, useState } from "react";

import AppShell from "../../../components/AppShell";
import {
  ApiError,
  approveClaimRevision,
  editClaimRevision,
  getPendingClaims,
  publishClaimRevision,
  rejectClaimRevision,
  type PendingClaimRevision,
} from "../../../lib/api/client";

export default function ReviewDashboardPage() {
  const [claims, setClaims] = useState<PendingClaimRevision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  function load() {
    setLoading(true);
    getPendingClaims()
      .then(setClaims)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Could not load pending claims");
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function withBusy(id: string, action: () => Promise<unknown>) {
    setBusyId(id);
    setError(null);
    try {
      await action();
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <AppShell>
      <section className="intro">
        <p className="eyebrow">Review</p>
        <h1>Pending claim revisions</h1>
      </section>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error-text">{error}</p>}
      {!loading && claims.length === 0 && <p className="muted">Nothing pending review.</p>}

      <ul className="claim-list">
        {claims.map((claim) => (
          <li key={claim.claim_revision_id} className="review-card">
            <p className="claim-category">{claim.category}</p>
            <p className="claim-statement">{claim.statement}</p>

            <div className="status-pills">
              {claim.latest_verification_status && (
                <span className={`status-pill status-${claim.latest_verification_status}`}>
                  verification: {claim.latest_verification_status}
                  {claim.latest_verifier_score != null && ` (${claim.latest_verifier_score.toFixed(2)})`}
                </span>
              )}
              {claim.latest_freshness_status && (
                <span className={`status-pill status-${claim.latest_freshness_status}`}>
                  freshness: {claim.latest_freshness_status}
                </span>
              )}
            </div>

            <ul className="evidence-list">
              {claim.evidence.map((item) => (
                <li key={item.evidence_version_id}>
                  <span className={`status-pill status-${item.relation}`}>{item.relation}</span>{" "}
                  {item.source_type} · {item.source_ref} · {item.assurance_class} · {item.validity}
                </li>
              ))}
            </ul>

            {editingId === claim.claim_revision_id ? (
              <div className="review-actions">
                <textarea value={editText} onChange={(event) => setEditText(event.target.value)} />
                <button
                  disabled={busyId === claim.claim_revision_id}
                  onClick={() =>
                    withBusy(claim.claim_revision_id, () =>
                      editClaimRevision(claim.claim_revision_id, {
                        claim_id: claim.claim_id,
                        category: claim.category,
                        statement: editText,
                      })
                    ).then(() => setEditingId(null))
                  }
                >
                  Save edit
                </button>
                <button onClick={() => setEditingId(null)}>Cancel</button>
              </div>
            ) : (
              <div className="review-actions">
                <button
                  disabled={busyId === claim.claim_revision_id}
                  onClick={() => withBusy(claim.claim_revision_id, () => approveClaimRevision(claim.claim_revision_id))}
                >
                  Approve
                </button>
                <button
                  disabled={busyId === claim.claim_revision_id}
                  onClick={() => withBusy(claim.claim_revision_id, () => rejectClaimRevision(claim.claim_revision_id))}
                >
                  Reject
                </button>
                <button
                  disabled={busyId === claim.claim_revision_id}
                  onClick={() => {
                    setEditingId(claim.claim_revision_id);
                    setEditText(claim.statement);
                  }}
                >
                  Edit
                </button>
                <button
                  disabled={busyId === claim.claim_revision_id}
                  onClick={() => withBusy(claim.claim_revision_id, () => publishClaimRevision(claim.claim_revision_id))}
                >
                  Publish
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
