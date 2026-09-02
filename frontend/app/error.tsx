"use client";

import { useEffect } from "react";

import { Button, ButtonLink } from "../components/ui/Button";
import { Card, CardBody } from "../components/ui/Card";
import { AlertIcon, DevStacksMark } from "../components/ui/Icon";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // The digest is the only safe correlation handle to show a user; the
    // message itself may carry internals and stays in the server log.
    console.error("Unhandled application error", error.digest ?? error.message);
  }, [error]);

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
            <p className="row gap-2 text-danger text-sm font-semibold">
              <AlertIcon size={15} />
              Something broke on our side
            </p>
            <h1 className="mt-2" style={{ fontSize: "var(--text-h3)" }}>
              This page could not be rendered
            </h1>
            <p className="text-sm text-muted mt-2">
              Nothing was published or changed. Retrying is safe — every write in DevStacks is
              idempotent.
            </p>
            {error.digest ? (
              <p className="text-xs text-subtle font-mono mt-3">reference {error.digest}</p>
            ) : null}
            <div className="row gap-2 mt-5">
              <Button variant="primary" onClick={reset}>
                Try again
              </Button>
              <ButtonLink href="/">Back to home</ButtonLink>
            </div>
          </CardBody>
        </Card>
      </main>
    </div>
  );
}
