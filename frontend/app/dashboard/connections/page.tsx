"use client";

import { useState } from "react";

import AppShell from "../../../components/AppShell";
import { toHeaderUser, useProfile } from "../../../lib/hooks/useProfile";
import { isTerminal, useConnectors } from "../../../lib/hooks/useConnectors";
import {
  ApiError,
  beginGithubAuth,
  syncGithubConnection,
  type Connector,
  type ConnectionStatus,
  type IngestionRun,
} from "../../../lib/api/client";
import { Button, ButtonLink } from "../../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { Flash, Skeleton, Spinner } from "../../../components/ui/Feedback";
import { Label, type LabelTone } from "../../../components/ui/Label";
import { RelativeTime } from "../../../components/ui/Time";
import { useToast } from "../../../components/ui/Toast";
import {
  ArrowUpRightIcon,
  CheckCircleIcon,
  ClockIcon,
  GitHubIcon,
  GlobeIcon,
  LockIcon,
  PlugIcon,
  ShieldIcon,
  SyncIcon,
  XCircleIcon,
} from "../../../components/ui/Icon";

const CONNECTION_TONE: Record<ConnectionStatus, LabelTone> = {
  active: "success",
  pending: "attention",
  degraded: "attention",
  revoked: "danger",
  disconnected: "neutral",
};

const RUN_TONE: Record<IngestionRun["status"], LabelTone> = {
  queued: "neutral",
  running: "info",
  succeeded: "success",
  partial: "attention",
  failed: "danger",
  no_op: "neutral",
};

const RUN_LABEL: Record<IngestionRun["status"], string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Succeeded",
  partial: "Partially succeeded",
  failed: "Failed",
  no_op: "Nothing new",
};

const PLANNED = [
  {
    id: "linkedin",
    name: "LinkedIn export",
    description:
      "Positions and dates from your own data export, kept as self-attested evidence and never presented as independently verified.",
    icon: <GlobeIcon size={18} />,
    assurance: "Self-attested",
  },
  {
    id: "hackerrank",
    name: "HackerRank certificates",
    description:
      "Certificate identifiers are checked against HackerRank's public verification endpoint before any claim is proposed.",
    icon: <ShieldIcon size={18} />,
    assurance: "Verified",
  },
  {
    id: "leetcode",
    name: "LeetCode snapshots",
    description:
      "Public profile snapshots taken on a schedule, hashed like every other observation so history stays comparable.",
    icon: <ClockIcon size={18} />,
    assurance: "Verified",
  },
];

export default function ConnectionsPage() {
  const { profile } = useProfile();
  const { toast } = useToast();
  const { connectors, error, trackedRun, reload, trackRun } = useConnectors(Boolean(profile));

  const [connecting, setConnecting] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);

  const github = connectors?.find((connector) => connector.platform === "github") ?? null;

  async function connect() {
    setAuthError(null);
    setConnecting(true);
    try {
      const authorizationUrl = await beginGithubAuth();
      window.location.href = authorizationUrl;
    } catch (err) {
      setAuthError(err instanceof ApiError ? err.message : "Could not start GitHub authorization");
      setConnecting(false);
    }
  }

  async function sync(connector: Connector) {
    setSyncingId(connector.id);
    try {
      const { run_id: runId } = await syncGithubConnection(connector.id);
      trackRun(runId);
      toast({
        title: "Sync queued",
        description: "Evidence collection is running; this page follows the run.",
        tone: "success",
      });
    } catch (err) {
      toast({
        title: "Could not queue a sync",
        description: err instanceof ApiError ? err.message : "Unexpected error",
        tone: "danger",
      });
    } finally {
      setSyncingId(null);
    }
  }

  return (
    <AppShell user={toHeaderUser(profile)}>
      <div className="page-header">
        <div>
          <span className="eyebrow">Connections</span>
          <h1 className="page-header__title mt-1">Sources of evidence</h1>
          <p className="page-header__description">
            A connector observes; it never asserts. Each one requests the narrowest scope that lets
            it do its job, and tokens are encrypted server-side and never returned to the browser.
          </p>
        </div>
        <div className="page-header__actions">
          <Button
            variant="invisible"
            onClick={() => void reload()}
            leadingIcon={<SyncIcon size={15} />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {authError ? (
        <div className="mb-5">
          <Flash tone="danger">{authError}</Flash>
        </div>
      ) : null}
      {error ? (
        <div className="mb-5">
          <Flash tone="danger">{error}</Flash>
        </div>
      ) : null}

      <Card className="mb-5">
        <CardHeader
          title={
            <span className="row gap-2">
              <GitHubIcon size={18} />
              GitHub
            </span>
          }
          actions={
            connectors === null ? (
              <Skeleton width={88} height={20} radius={999} />
            ) : github ? (
              <Label tone={CONNECTION_TONE[github.connection_status]}>
                <CheckCircleIcon size={12} />
                {github.connection_status}
              </Label>
            ) : (
              <Label tone="attention">Not connected</Label>
            )
          }
        />
        <CardBody>
          <p className="text-sm text-muted" style={{ maxWidth: "70ch" }}>
            The golden path. DevStacks reads commits, pull requests, and releases, hashes each
            observation into an immutable evidence version, and proposes claim revisions for your
            review. Repository access is a separate authorization from sign-in.
          </p>

          <div className="row row--wrap gap-2 mt-4">
            <Label tone="info">
              <LockIcon size={12} />
              read:user at first authorization
            </Label>
            <Label>Webhook-driven refresh</Label>
            <Label>Idempotent replay</Label>
          </div>

          {connectors === null ? (
            <div className="card mt-5">
              <div className="card__row">
                <div className="flex-1 stack gap-2">
                  <Skeleton width="30%" height={14} />
                  <Skeleton width="55%" height={10} />
                </div>
              </div>
            </div>
          ) : github ? (
            <>
              <div className="card mt-5">
                <div className="card__row">
                  <div className="flex-1">
                    <p className="text-sm font-semibold">
                      {github.external_subject ? `@${github.external_subject}` : "GitHub account"}
                    </p>
                    <p className="text-xs text-subtle mt-1">
                      {github.connected_at ? (
                        <>
                          Authorized <RelativeTime value={github.connected_at} />
                        </>
                      ) : (
                        "Authorization pending"
                      )}
                      {github.last_synced_at ? (
                        <>
                          {" · last synced "}
                          <RelativeTime value={github.last_synced_at} />
                        </>
                      ) : (
                        " · never synced"
                      )}
                    </p>
                  </div>
                  <Button
                    onClick={() => void sync(github)}
                    loading={syncingId === github.id}
                    leadingIcon={<SyncIcon size={15} />}
                  >
                    Sync now
                  </Button>
                </div>

                <RunRow run={trackedRun ?? github.latest_run} live={Boolean(trackedRun)} />
              </div>

              <div className="row row--wrap gap-2 mt-4">
                <ButtonLink href="/dashboard/review">Review proposed claims</ButtonLink>
                <Button variant="invisible" onClick={() => void connect()} loading={connecting}>
                  Re-authorize
                </Button>
              </div>
            </>
          ) : (
            <div className="mt-5">
              <Button
                variant="primary"
                size="lg"
                onClick={() => void connect()}
                loading={connecting}
                leadingIcon={<GitHubIcon size={16} />}
              >
                Connect GitHub
              </Button>
            </div>
          )}
        </CardBody>
      </Card>

      <h2 className="section-title">On the roadmap</h2>
      <div className="feature-grid">
        {PLANNED.map((connector) => (
          <article className="feature" key={connector.id}>
            <span className="feature__icon">{connector.icon}</span>
            <div className="row row--between gap-2 mb-2">
              <h3 className="feature__title" style={{ margin: 0 }}>
                {connector.name}
              </h3>
              <Label>{connector.assurance}</Label>
            </div>
            <p className="feature__body">{connector.description}</p>
            <p className="row gap-2 text-xs text-subtle mt-3">
              <PlugIcon size={12} />
              Not yet available
            </p>
          </article>
        ))}
      </div>

      <Card subtle className="mt-5">
        <CardBody>
          <p className="text-sm font-semibold">Webhooks</p>
          <p className="text-sm text-muted mt-2" style={{ maxWidth: "72ch" }}>
            Repository webhooks keep evidence current between scheduled runs. Deliveries are accepted
            only after HMAC-SHA256 verification and are replay-safe by their GitHub delivery ID.
          </p>
          <div className="mt-3">
            <ButtonLink
              href="https://github.com/kowshikdev/devstacks#github-webhooks"
              size="sm"
              trailingIcon={<ArrowUpRightIcon size={14} />}
            >
              Webhook setup guide
            </ButtonLink>
          </div>
        </CardBody>
      </Card>
    </AppShell>
  );
}

/** The last thing the connector actually did, or is doing right now. */
function RunRow({ run, live }: { run: IngestionRun | null; live: boolean }) {
  if (!run) {
    return (
      <div className="card__row">
        <p className="text-xs text-subtle">
          No ingestion run yet. Queue one to collect the first evidence versions.
        </p>
      </div>
    );
  }

  const settled = isTerminal(run.status);

  return (
    <div className="card__row">
      <div className="flex-1">
        <div className="row row--wrap gap-2">
          <Label tone={RUN_TONE[run.status]}>
            {run.status === "failed" ? (
              <XCircleIcon size={12} />
            ) : settled ? (
              <CheckCircleIcon size={12} />
            ) : (
              <ClockIcon size={12} />
            )}
            {RUN_LABEL[run.status]}
          </Label>
          <Label mono>{run.trigger_type}</Label>
          {live && !settled ? (
            <span className="row gap-2 text-xs text-muted" aria-live="polite">
              <Spinner label="Following the ingestion run" />
              following this run
            </span>
          ) : null}
        </div>
        <p className="text-xs text-subtle mt-2">
          Started <RelativeTime value={run.started_at ?? run.created_at} />
          {run.completed_at ? (
            <>
              {" · finished "}
              <RelativeTime value={run.completed_at} />
            </>
          ) : null}
        </p>
        {run.error_summary ? (
          <p className="text-xs text-danger mt-2 break-anywhere">{run.error_summary}</p>
        ) : null}
      </div>
    </div>
  );
}
