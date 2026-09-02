import type { GuardrailVerdict, ModerationActionKind } from "../../lib/api/client";
import { Label } from "../ui/Label";
import { AlertIcon, CheckCircleIcon, InfoIcon, LockIcon, XCircleIcon } from "../ui/Icon";

const TONE: Record<ModerationActionKind, "success" | "info" | "attention" | "danger"> = {
  allow: "success",
  allow_with_notice: "info",
  hold_for_review: "attention",
  block: "danger",
};

const HEADLINE: Record<ModerationActionKind, string> = {
  allow: "Ready to post",
  allow_with_notice: "Fine to post — one thing to know",
  hold_for_review: "This will go to a moderator before it appears",
  block: "This cannot be posted",
};

const ICON: Record<ModerationActionKind, React.ReactNode> = {
  allow: <CheckCircleIcon size={15} />,
  allow_with_notice: <InfoIcon size={15} />,
  hold_for_review: <AlertIcon size={15} />,
  block: <XCircleIcon size={15} />,
};

/**
 * Shows what the guardrails found and why, before the post is sent.
 *
 * The point is that a person can act on it: every signal names the rule that
 * fired and says what to do about it, rather than announcing a violation.
 */
export function GuardrailNotice({ verdict }: { verdict: GuardrailVerdict }) {
  if (verdict.action === "allow" && verdict.signals.length === 0) {
    return (
      <p className="row gap-2 text-xs text-success" role="status">
        <CheckCircleIcon size={14} />
        Ready to post.
      </p>
    );
  }

  const tone = TONE[verdict.action];

  return (
    <div className={`flash flash--${tone}`} role={verdict.action === "block" ? "alert" : "status"}>
      <span className="shrink-0" style={{ marginTop: 2 }}>
        {ICON[verdict.action]}
      </span>
      <div className="flash__body">
        <p className="text-sm font-semibold">{HEADLINE[verdict.action]}</p>

        <ul className="stack gap-2 mt-2">
          {verdict.signals.map((signal) => (
            <li key={`${signal.rule_id}-${signal.excerpt ?? ""}`} className="text-xs">
              <span className="row row--wrap gap-2">
                <Label mono>{signal.rule_id}</Label>
                {signal.excerpt ? (
                  <code className="text-subtle font-mono">{signal.excerpt}</code>
                ) : null}
              </span>
              <p className="mt-1">{signal.explanation}</p>
            </li>
          ))}
        </ul>

        <p className="row gap-2 text-xs text-subtle mt-3">
          <LockIcon size={12} />
          Checked against {verdict.policy_version}. Nothing is stored until you post.
        </p>
      </div>
    </div>
  );
}
