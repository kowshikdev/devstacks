"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import AppShell from "../../../../components/AppShell";
import { toHeaderUser, useProfile } from "../../../../lib/hooks/useProfile";
import { ApiError, beginGithubAuth, syncGithubConnection } from "../../../../lib/api/client";
import { writeConnection } from "../../../../lib/connections";
import { Button, ButtonLink } from "../../../../components/ui/Button";
import { Card, CardBody } from "../../../../components/ui/Card";
import { Flash, Spinner } from "../../../../components/ui/Feedback";
import { Label } from "../../../../components/ui/Label";
import { useToast } from "../../../../components/ui/Toast";
import {
  CheckCircleIcon,
  GitHubIcon,
  InboxIcon,
  PlugIcon,
  SyncIcon,
} from "../../../../components/ui/Icon";

const ERROR_MESSAGES: Record<string, string> = {
  denied: "You declined the GitHub authorization request.",
  invalid: "GitHub authorization could not be completed — the request may have expired.",
  unavailable: "The GitHub connector service is temporarily unavailable.",
};

export default function ConnectGithubPage() {
  return (
    <Suspense fallback={<ConnectFallback />}>
      <ConnectGithubContent />
    </Suspense>
  );
}

function ConnectFallback() {
  return (
    <AppShell>
      <div className="page-header">
        <div>
          <span className="eyebrow">Connect GitHub</span>
          <h1 className="page-header__title mt-1">Preparing authorization…</h1>
        </div>
      </div>
      <Card>
        <CardBody>
          <Spinner label="Preparing GitHub authorization" />
        </CardBody>
      </Card>
    </AppShell>
  );
}

function ConnectGithubContent() {
  const searchParams = useSearchParams();
  const { profile } = useProfile();
  const { toast } = useToast();

  const connected = searchParams.get("connected") === "1";
  const errorCode = searchParams.get("error");
  const githubLogin = searchParams.get("github_login");
  const connectionId = searchParams.get("connection_id");

  const [error, setError] = useState<string | null>(
    errorCode ? (ERROR_MESSAGES[errorCode] ?? "GitHub authorization failed.") : null
  );
  const [syncing, setSyncing] = useState(false);
  const [syncQueued, setSyncQueued] = useState(false);

  // Remember the connection so the connections surface can offer a manual sync
  // without asking the user to hold on to an opaque identifier.
  useEffect(() => {
    if (connected && connectionId) {
      writeConnection({ connectionId, githubLogin });
    }
  }, [connected, connectionId, githubLogin]);

  // Arriving with no result at all means the flow has not started yet: begin it.
  useEffect(() => {
    if (connected || errorCode) return;
    beginGithubAuth()
      .then((authorizationUrl) => {
        window.location.href = authorizationUrl;
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Could not start GitHub authorization");
      });
  }, [connected, errorCode]);

  async function handleSync() {
    if (!connectionId) return;
    setSyncing(true);
    try {
      await syncGithubConnection(connectionId);
      setSyncQueued(true);
      toast({
        title: "Sync queued",
        description: "Evidence collection is running in the background.",
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

  if (connected) {
    return (
      <AppShell user={toHeaderUser(profile)}>
        <div className="page-header">
          <div>
            <span className="eyebrow">Connect GitHub</span>
            <h1 className="page-header__title mt-1">
              Connected{githubLogin ? ` as @${githubLogin}` : ""}
            </h1>
            <p className="page-header__description">
              Your GitHub identity is bound to this profile. Queue the first evidence sync, then
              review whatever it proposes.
            </p>
          </div>
        </div>

        <Card className="mb-5">
          <CardBody>
            <div className="row row--wrap gap-2 mb-4">
              <Label tone="success">
                <CheckCircleIcon size={12} />
                Identity bound
              </Label>
              <Label tone={syncQueued ? "success" : "neutral"}>
                {syncQueued ? "Sync queued" : "No sync queued yet"}
              </Label>
            </div>

            <div className="window">
              <div className="window__bar">
                <span className="window__dot" />
                <span className="window__dot" />
                <span className="window__dot" />
                <span className="window__title">devstacks — connector</span>
              </div>
              <div className="window__body">
                <p className="window__line window__line--ok">
                  <CheckCircleIcon size={14} />
                  GitHub identity bound
                </p>
                <p className="window__prompt">
                  devstacks sync github
                  {syncQueued ? "" : <span className="cursor" />}
                </p>
                {syncQueued ? (
                  <p className="window__line window__line--ok">
                    <CheckCircleIcon size={14} />
                    ingestion run leased — evidence collection in progress
                  </p>
                ) : null}
              </div>
            </div>

            <div className="row row--wrap gap-2 mt-5">
              <Button
                variant="primary"
                onClick={() => void handleSync()}
                loading={syncing}
                disabled={!connectionId}
                leadingIcon={<SyncIcon size={15} />}
              >
                Sync evidence now
              </Button>
              <ButtonLink href="/dashboard/review" leadingIcon={<InboxIcon size={15} />}>
                Go to review
              </ButtonLink>
              <ButtonLink
                href="/dashboard/connections"
                variant="invisible"
                leadingIcon={<PlugIcon size={15} />}
              >
                All connections
              </ButtonLink>
            </div>
          </CardBody>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell user={toHeaderUser(profile)}>
      <div className="page-header">
        <div>
          <span className="eyebrow">Connect GitHub</span>
          <h1 className="page-header__title mt-1">
            {error ? "Couldn't connect" : "Redirecting to GitHub…"}
          </h1>
        </div>
      </div>

      <Card>
        <CardBody>
          {error ? (
            <>
              <Flash tone="danger">{error}</Flash>
              <div className="row gap-2 mt-4">
                <Button
                  variant="primary"
                  onClick={() => {
                    setError(null);
                    beginGithubAuth()
                      .then((url) => {
                        window.location.href = url;
                      })
                      .catch((err: unknown) => {
                        setError(
                          err instanceof ApiError ? err.message : "Could not start authorization"
                        );
                      });
                  }}
                  leadingIcon={<GitHubIcon size={15} />}
                >
                  Try again
                </Button>
                <ButtonLink href="/dashboard/connections">Back to connections</ButtonLink>
              </div>
            </>
          ) : (
            <div className="row gap-3">
              <Spinner label="Redirecting to GitHub" />
              <p className="text-sm text-muted">
                Sending you to GitHub to authorize the connector.
              </p>
            </div>
          )}
        </CardBody>
      </Card>
    </AppShell>
  );
}
