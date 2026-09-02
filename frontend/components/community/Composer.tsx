"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  createCommunityPost,
  preflightPost,
  type GuardrailVerdict,
} from "../../lib/api/client";
import { Button } from "../ui/Button";
import { Card, CardBody } from "../ui/Card";
import { TextAreaField, TextField } from "../ui/Field";
import { Flash } from "../ui/Feedback";
import { useToast } from "../ui/Toast";
import { GuardrailNotice } from "./GuardrailNotice";

/** Long enough to stop typing, short enough to feel live. */
const PREFLIGHT_DEBOUNCE_MS = 550;
const MIN_BODY_FOR_PREFLIGHT = 12;

export function Composer({
  spaceSlug,
  parentPostId,
  onPosted,
}: {
  spaceSlug: string;
  parentPostId?: string;
  onPosted: () => void;
}) {
  const isReply = Boolean(parentPostId);
  const { toast } = useToast();

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [verdict, setVerdict] = useState<GuardrailVerdict | null>(null);
  const [checking, setChecking] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestDraft = useRef("");

  const draft = isReply ? body : `${title}\n\n${body}`;

  // Lint the draft as it settles. This check is advisory: the same engine runs
  // again server-side on submit, so a warning here is never the only thing
  // standing between a post and the community.
  const runPreflight = useCallback(async (text: string) => {
    latestDraft.current = text;
    setChecking(true);
    try {
      const result = await preflightPost(text);
      // Ignore a response a newer keystroke has already superseded.
      if (latestDraft.current === text) {
        setVerdict(result);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        window.location.href = "/login";
        return;
      }
      // A failed check must not block writing; submit re-checks server-side.
      setVerdict(null);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (draft.trim().length < MIN_BODY_FOR_PREFLIGHT) {
      setVerdict(null);
      return;
    }
    timer.current = setTimeout(() => void runPreflight(draft), PREFLIGHT_DEBOUNCE_MS);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [draft, runPreflight]);

  const blocked = verdict?.action === "block";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await createCommunityPost(spaceSlug, {
        body,
        title: isReply ? undefined : title,
        parentPostId,
      });

      if (result.published) {
        toast({ title: isReply ? "Reply posted" : "Thread posted", tone: "success" });
        setTitle("");
        setBody("");
        setVerdict(null);
        onPosted();
        return;
      }

      // Not an error: the post exists, and its reason is attached to it.
      setVerdict(result.verdict);
      toast({
        title:
          result.verdict.action === "block"
            ? "Post stopped by a guardrail"
            : "Post sent for review",
        description: result.verdict.rationale,
        tone: result.verdict.action === "block" ? "danger" : "neutral",
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not post");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardBody>
        <form className="stack gap-4" onSubmit={submit}>
          {!isReply ? (
            <TextField
              label="Title"
              placeholder="What is this about?"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={160}
              required
            />
          ) : null}

          <TextAreaField
            label={isReply ? "Your reply" : "Your post"}
            placeholder={
              isReply
                ? "Answer with what you actually know."
                : "Bring the error, the versions, and what you already tried."
            }
            value={body}
            onChange={(event) => setBody(event.target.value)}
            rows={isReply ? 4 : 8}
            required
          />

          <div aria-live="polite" className="stack gap-2">
            {checking && !verdict ? (
              <p className="text-xs text-subtle">Checking…</p>
            ) : verdict ? (
              <GuardrailNotice verdict={verdict} />
            ) : null}
          </div>

          {error ? <Flash tone="danger">{error}</Flash> : null}

          <div className="row row--between row--wrap gap-3">
            <p className="text-xs text-subtle">
              Criticise the code as harshly as you like. Not the person.
            </p>
            <Button
              type="submit"
              variant="primary"
              loading={submitting}
              disabled={blocked || body.trim().length === 0 || (!isReply && !title.trim())}
            >
              {isReply ? "Reply" : "Post thread"}
            </Button>
          </div>

          {blocked ? (
            <p className="text-xs text-danger">Fix the issue above to enable posting.</p>
          ) : null}
        </form>
      </CardBody>
    </Card>
  );
}
