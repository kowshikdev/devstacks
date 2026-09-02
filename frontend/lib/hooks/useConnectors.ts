"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  getIngestionRun,
  listConnectors,
  TERMINAL_RUN_STATUSES,
  type Connector,
  type IngestionRun,
  type IngestionRunStatus,
} from "../api/client";

const POLL_INTERVAL_MS = 2500;
/** A worker that never picks the job up should not leave the UI polling forever. */
const POLL_TIMEOUT_MS = 120_000;

export function isTerminal(status: IngestionRunStatus): boolean {
  return TERMINAL_RUN_STATUSES.includes(status);
}

export interface ConnectorsState {
  connectors: Connector[] | null;
  error: string | null;
  /** The run this session started, followed until it reaches a terminal status. */
  trackedRun: IngestionRun | null;
  reload: () => Promise<void>;
  trackRun: (runId: string) => void;
}

/**
 * Loads the caller's connectors and, when a sync is queued from this session,
 * follows that run to completion.
 *
 * Ingestion is executed by a separate worker, so the only honest way to show
 * progress is to poll the run the enqueue returned. Polling stops as soon as
 * the run reaches a terminal status, on unmount, and at a hard timeout.
 */
export function useConnectors(enabled: boolean): ConnectorsState {
  const [connectors, setConnectors] = useState<Connector[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [trackedRun, setTrackedRun] = useState<IngestionRun | null>(null);

  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, []);

  const reload = useCallback(async () => {
    try {
      const result = await listConnectors();
      if (mounted.current) {
        setConnectors(result);
        setError(null);
      }
    } catch (err) {
      if (!mounted.current) return;
      if (err instanceof ApiError && err.status === 401) {
        window.location.href = "/login";
        return;
      }
      setConnectors([]);
      setError(err instanceof ApiError ? err.message : "Could not load your connections");
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    void reload();
  }, [enabled, reload]);

  const trackRun = useCallback(
    (runId: string) => {
      const startedAt = Date.now();

      const poll = async () => {
        try {
          const run = await getIngestionRun(runId);
          if (!mounted.current) return;
          setTrackedRun(run);

          if (isTerminal(run.status)) {
            // The run changed what the connector list says about itself.
            await reload();
            return;
          }
        } catch {
          // A transient read failure should not abandon a run that is still
          // progressing; the timeout below is what ends the loop.
          if (!mounted.current) return;
        }

        if (Date.now() - startedAt > POLL_TIMEOUT_MS) return;
        pollTimer.current = setTimeout(() => void poll(), POLL_INTERVAL_MS);
      };

      if (pollTimer.current) clearTimeout(pollTimer.current);
      void poll();
    },
    [reload]
  );

  return { connectors, error, trackedRun, reload, trackRun };
}
