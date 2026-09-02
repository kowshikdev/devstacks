"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import AppShell from "../../../components/AppShell";
import { toHeaderUser, useProfile } from "../../../lib/hooks/useProfile";
import {
  ApiError,
  approveClaimRevision,
  editClaimRevision,
  getPendingClaims,
  publishClaimRevision,
  rejectClaimRevision,
  type EvidenceExplanation,
  type PendingClaimRevision,
} from "../../../lib/api/client";
import { Button } from "../../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { Dialog } from "../../../components/ui/Dialog";
import { EmptyState, Flash, Skeleton } from "../../../components/ui/Feedback";
import { TextAreaField } from "../../../components/ui/Field";
import { Label, StateLabel } from "../../../components/ui/Label";
import { ButtonTabs } from "../../../components/ui/Tabs";
import { RelativeTime } from "../../../components/ui/Time";
import { useToast } from "../../../components/ui/Toast";
import {
  CheckIcon,
  GlobeIcon,
  InboxIcon,
  PencilIcon,
  SyncIcon,
  XIcon,
} from "../../../components/ui/Icon";

type Filter = "all" | "verified" | "stale" | "unverified";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "verified", label: "Verified" },
  { value: "unverified", label: "Unverified" },
  { value: "stale", label: "Stale" },
];

function matchesFilter(claim: PendingClaimRevision, filter: Filter): boolean {
  switch (filter) {
    case "verified":
      return claim.latest_verification_status === "verified";
    case "unverified":
      return claim.latest_verification_status !== "verified";
    case "stale":
      return claim.latest_freshness_status === "stale";
    default:
      return true;
  }
}

export default function ReviewPage() {
  const { profile } = useProfile();
  const { toast } = useToast();

  const [claims, setClaims] = useState<PendingClaimRevision[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editText, setEditText] = useState("");

  const load = useCallback(
    (options: { silent?: boolean } = {}) => {
      if (!options.silent) setClaims(null);
      setError(null);
      return getPendingClaims()
        .then((result) => {
          setClaims(result);
          setSelectedId((current) =>
            current && result.some((claim) => claim.claim_revision_id === current)
              ? current
              : (result[0]?.claim_revision_id ?? null)
          );
        })
        .catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 401) {
            window.location.href = "/login";
            return;
          }
          setError(err instanceof ApiError ? err.message : "Could not load pending claims");
          setClaims([]);
        });
    },
    []
  );

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(
    () => (claims ?? []).filter((claim) => matchesFilter(claim, filter)),
    [claims, filter]
  );

  const selected =
    visible.find((claim) => claim.claim_revision_id === selectedId) ?? visible[0] ?? null;

  const runAction = useCallback(
    async (
      claim: PendingClaimRevision,
      name: string,
      action: () => Promise<unknown>,
      success: string
    ) => {
      setBusyAction(`${claim.claim_revision_id}:${name}`);
      try {
        await action();
        toast({ title: success, description: claim.statement, tone: "success" });
        await load({ silent: true });
      } catch (err) {
        toast({
          title: `${name} failed`,
          description: err instanceof ApiError ? err.message : "Unexpected error",
          tone: "danger",
        });
      } finally {
        setBusyAction(null);
      }
    },
    [load, toast]
  );

  const approve = useCallback(
    (claim: PendingClaimRevision) =>
      runAction(claim, "Approve", () => approveClaimRevision(claim.claim_revision_id), "Revision approved"),
    [runAction]
  );

  const reject = useCallback(
    (claim: PendingClaimRevision) =>
      runAction(claim, "Reject", () => rejectClaimRevision(claim.claim_revision_id), "Revision rejected"),
    [runAction]
  );

  const publish = useCallback(
    (claim: PendingClaimRevision) =>
      runAction(claim, "Publish", () => publishClaimRevision(claim.claim_revision_id), "Revision published"),
    [runAction]
  );

  // Keyboard review, the way a triage queue is actually worked: j/k to move,
  // a/r/p to act, e to edit. Ignored while typing into a field.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (
        event.metaKey ||
        event.ctrlKey ||
        editOpen ||
        (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
      ) {
        return;
      }
      if (visible.length === 0) return;

      const index = visible.findIndex((claim) => claim.claim_revision_id === selected?.claim_revision_id);

      switch (event.key) {
        case "j":
          event.preventDefault();
          setSelectedId(visible[Math.min(index + 1, visible.length - 1)].claim_revision_id);
          break;
        case "k":
          event.preventDefault();
          setSelectedId(visible[Math.max(index - 1, 0)].claim_revision_id);
          break;
        case "a":
          if (selected) {
            event.preventDefault();
            void approve(selected);
          }
          break;
        case "r":
          if (selected) {
            event.preventDefault();
            void reject(selected);
          }
          break;
        case "p":
          if (selected) {
            event.preventDefault();
            void publish(selected);
          }
          break;
        case "e":
          if (selected) {
            event.preventDefault();
            setEditText(selected.statement);
            setEditOpen(true);
          }
          break;
        default:
          break;
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [visible, selected, approve, reject, publish, editOpen]);

  async function saveEdit() {
    if (!selected) return;
    setBusyAction(`${selected.claim_revision_id}:edit`);
    try {
      await editClaimRevision(selected.claim_revision_id, {
        claim_id: selected.claim_id,
        category: selected.category,
        statement: editText,
      });
      setEditOpen(false);
      toast({ title: "Revision edited", description: editText, tone: "success" });
      await load({ silent: true });
    } catch (err) {
      toast({
        title: "Edit failed",
        description: err instanceof ApiError ? err.message : "Unexpected error",
        tone: "danger",
      });
    } finally {
      setBusyAction(null);
    }
  }

  const pendingCount = claims?.length ?? 0;

  return (
    <AppShell user={toHeaderUser(profile)} reviewCount={pendingCount || undefined}>
      <div className="page-header">
        <div>
          <span className="eyebrow">Review</span>
          <h1 className="page-header__title mt-1">Claim revisions</h1>
          <p className="page-header__description">
            Each revision carries the evidence that supports it and the evidence that contradicts it.
            Nothing publishes without a decision here.
          </p>
        </div>
        <div className="page-header__actions">
          <ButtonTabs value={filter} onChange={setFilter} options={FILTERS} label="Filter revisions" />
          <Button
            variant="invisible"
            onClick={() => void load({ silent: true })}
            leadingIcon={<SyncIcon size={15} />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <div className="mb-5">
          <Flash tone="danger">{error}</Flash>
        </div>
      ) : null}

      {claims === null ? (
        <ReviewSkeleton />
      ) : claims.length === 0 ? (
        <Card>
          <EmptyState
            icon={<InboxIcon size={20} />}
            title="Your review inbox is empty"
            description="Claim revisions arrive here after a connector sync produces evidence worth interpreting."
          />
        </Card>
      ) : (
        <div className="inbox">
          <div className="inbox__list">
            {visible.length === 0 ? (
              <div style={{ padding: "var(--space-6)" }}>
                <p className="text-sm text-muted">No revision matches this filter.</p>
              </div>
            ) : (
              visible.map((claim) => (
                <button
                  key={claim.claim_revision_id}
                  type="button"
                  className="inbox__item"
                  aria-current={claim.claim_revision_id === selected?.claim_revision_id}
                  onClick={() => setSelectedId(claim.claim_revision_id)}
                >
                  <p className="inbox__item-title">{claim.statement}</p>
                  <p className="inbox__item-meta">
                    <Label mono>{claim.category}</Label>
                    <span>·</span>
                    <span>rev {claim.revision_number}</span>
                    <span>·</span>
                    <RelativeTime value={claim.created_at} />
                  </p>
                </button>
              ))
            )}
          </div>

          {selected ? (
            <RevisionDetail
              claim={selected}
              busyAction={busyAction}
              onApprove={() => void approve(selected)}
              onReject={() => void reject(selected)}
              onPublish={() => void publish(selected)}
              onEdit={() => {
                setEditText(selected.statement);
                setEditOpen(true);
              }}
            />
          ) : null}
        </div>
      )}

      <p className="text-xs text-subtle mt-5">
        Keyboard: <kbd className="kbd">j</kbd> <kbd className="kbd">k</kbd> move ·{" "}
        <kbd className="kbd">a</kbd> approve · <kbd className="kbd">r</kbd> reject ·{" "}
        <kbd className="kbd">e</kbd> edit · <kbd className="kbd">p</kbd> publish
      </p>

      <Dialog
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title="Edit claim statement"
        description="Editing creates a new revision. The previous revision and its evidence stay in the record."
        footer={
          <>
            <Button onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button
              variant="primary"
              onClick={() => void saveEdit()}
              loading={busyAction?.endsWith(":edit")}
              disabled={editText.trim().length === 0}
            >
              Save as new revision
            </Button>
          </>
        }
      >
        <TextAreaField
          label="Statement"
          value={editText}
          onChange={(event) => setEditText(event.target.value)}
          hint="State only what the linked evidence can support."
          rows={5}
        />
      </Dialog>
    </AppShell>
  );
}

function RevisionDetail({
  claim,
  busyAction,
  onApprove,
  onReject,
  onPublish,
  onEdit,
}: {
  claim: PendingClaimRevision;
  busyAction: string | null;
  onApprove: () => void;
  onReject: () => void;
  onPublish: () => void;
  onEdit: () => void;
}) {
  const busy = (name: string) => busyAction === `${claim.claim_revision_id}:${name}`;
  const anyBusy = busyAction?.startsWith(claim.claim_revision_id) ?? false;

  const supports = claim.evidence.filter((item) => item.relation === "supports");
  const contradicts = claim.evidence.filter((item) => item.relation === "contradicts");

  return (
    <div className="stack gap-4">
      <Card>
        <CardBody>
          <div className="row row--wrap gap-2 mb-3">
            <Label mono>{claim.category}</Label>
            <StateLabel status={claim.latest_verification_status}>
              {claim.latest_verification_status ?? "unverified"}
              {claim.latest_verifier_score != null
                ? ` · ${claim.latest_verifier_score.toFixed(2)}`
                : ""}
            </StateLabel>
            {claim.latest_freshness_status ? (
              <Label tone={claim.latest_freshness_status === "stale" ? "attention" : "success"}>
                {claim.latest_freshness_status}
              </Label>
            ) : null}
            {claim.latest_review_status ? (
              <Label tone="info">review: {claim.latest_review_status}</Label>
            ) : null}
          </div>

          <p style={{ fontSize: "1.125rem", fontWeight: 600, lineHeight: "var(--leading-snug)" }}>
            {claim.statement}
          </p>

          <p className="text-xs text-subtle mt-3">
            Revision {claim.revision_number} · proposed <RelativeTime value={claim.created_at} /> ·{" "}
            {supports.length} supporting, {contradicts.length} contradicting
          </p>

          <div className="row row--wrap gap-2 mt-5">
            <Button
              variant="primary"
              onClick={onApprove}
              loading={busy("Approve")}
              disabled={anyBusy && !busy("Approve")}
              leadingIcon={<CheckIcon size={15} />}
            >
              Approve
            </Button>
            <Button
              onClick={onPublish}
              loading={busy("Publish")}
              disabled={anyBusy && !busy("Publish")}
              leadingIcon={<GlobeIcon size={15} />}
            >
              Publish
            </Button>
            <Button onClick={onEdit} disabled={anyBusy} leadingIcon={<PencilIcon size={15} />}>
              Edit
            </Button>
            <Button
              variant="danger"
              onClick={onReject}
              loading={busy("Reject")}
              disabled={anyBusy && !busy("Reject")}
              leadingIcon={<XIcon size={15} />}
            >
              Reject
            </Button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Evidence"
          actions={<span className="text-xs text-muted">{claim.evidence.length} linked</span>}
        />
        {claim.evidence.length === 0 ? (
          <CardBody>
            <p className="text-sm text-muted">
              No evidence is linked to this revision yet, so it cannot be verified.
            </p>
          </CardBody>
        ) : (
          <div>
            {claim.evidence.map((item) => (
              <EvidenceRow key={item.evidence_version_id} item={item} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

const RELATION_MARK: Record<EvidenceExplanation["relation"], string> = {
  supports: "+",
  contradicts: "−",
  context: "~",
};

function EvidenceRow({ item }: { item: EvidenceExplanation }) {
  return (
    <div className="evidence-row">
      <span className={`evidence-row__mark evidence-row__mark--${item.relation}`} aria-hidden="true">
        {RELATION_MARK[item.relation]}
      </span>
      <div className="flex-1">
        <p className="text-sm">
          <span className="font-semibold">{item.relation}</span>
          <span className="text-muted"> · {item.source_type}</span>
        </p>
        <p className="evidence-row__ref mt-1">{item.source_ref}</p>
        <div className="row row--wrap gap-2 mt-2">
          <Label tone={item.assurance_class === "verified" ? "success" : "neutral"}>
            {item.assurance_class}
          </Label>
          <Label tone={item.validity === "current" ? "accent" : "attention"}>{item.validity}</Label>
        </div>
      </div>
      <span className="visually-hidden">Evidence version {item.evidence_version_id}</span>
    </div>
  );
}

function ReviewSkeleton() {
  return (
    <div className="inbox">
      <div className="inbox__list">
        {[0, 1, 2, 3].map((row) => (
          <div className="inbox__item" key={row}>
            <Skeleton width="90%" height={14} />
            <div className="mt-2">
              <Skeleton width="55%" height={10} />
            </div>
          </div>
        ))}
      </div>
      <Card>
        <CardBody>
          <div className="stack gap-3">
            <Skeleton width="35%" height={20} />
            <Skeleton width="100%" height={18} />
            <Skeleton width="75%" height={18} />
            <div className="mt-4">
              <Skeleton width="60%" height={34} />
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
