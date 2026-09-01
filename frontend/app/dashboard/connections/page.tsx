"use client";

import { useEffect, useState } from "react";

import AppShell from "../../../components/AppShell";
import { toHeaderUser, useProfile } from "../../../lib/hooks/useProfile";
import { ApiError, beginGithubAuth, syncGithubConnection } from "../../../lib/api/client";
import { readConnection, type StoredConnection } from "../../../lib/connections";
import { Button, ButtonLink } from "../../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { Flash } from "../../../components/ui/Feedback";
import { Label } from "../../../components/ui/Label";
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
} from "../../../components/ui/Icon";

interface PlannedConnector {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  assurance: string;
}

const PLANNED: PlannedConnector[] = [
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

  const [connection, setConnection] = useState<StoredConnection | null>(null);
  const [ready, setReady] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setConnection(readConnection());
    setReady(true);
  }, []);

  async function connect() {
    setError(null);
    setConnecting(true);
    try {
      const authorizationUrl = await beginGithubAuth();
      window.location.href = authorizationUrl;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start GitHub authorization");
      setConnecting(false);
    }
  }

  async function sync() {
    if (!connection) return;
    setSyncing(true);
    try {
      await syncGithubConnection(connection.connectionId);
      toast({
        title: "Sync queued",
        description: "Evidence collection runs in the background; new revisions land in review.",
        tone: "success",
      });
    } catch (err) {
      toast({
        title: "Could not queue a sync",
        description: err instanceof ApiError ? err.message : "Unexpected error",
        tone: "danger",
      });
    } finally {
      setSyncing(false);
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
      </div>

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
            ready && connection ? (
              <Label tone="success">
                <CheckCircleIcon size={12} />
                Connected
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

          {ready && connection ? (
            <>
              <div className="card mt-5">
                <div className="card__row">
                  <div className="flex-1">
                    <p className="text-sm font-semibold">
                      {connection.githubLogin ? `@${connection.githubLogin}` : "GitHub account"}
                    </p>
                    <p className="text-xs text-subtle mt-1 font-mono break-anywhere">
                      connection {connection.connectionId}
                    </p>
                    <p className="text-xs text-subtle mt-1">
                      Authorized <RelativeTime value={connection.connectedAt} />
                    </p>
                  </div>
                  <Button
                    onClick={() => void sync()}
                    loading={syncing}
                    leadingIcon={<SyncIcon size={15} />}
                  >
                    Sync now
                  </Button>
                </div>
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
