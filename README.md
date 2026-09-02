# DevStacks

DevStacks is a continuously verified developer evidence graph. It turns source observations into immutable evidence versions, explainable claim revisions, and a reviewable public developer profile.

```text
Source → Evidence → Claim Revision → Verification → Published Profile
```

Deterministic application code owns ingestion, identity binding, hashing, provenance, policy, authorization, and lifecycle transitions. Deep Agents and LangGraph support structured interpretation and durable workflows; they are never the source of truth.

The first release is delivered through a GitHub golden path, then adds LinkedIn export, HackerRank certificate verification, and LeetCode public snapshots. Resume exports and agent-facing profile artifacts are planned for later.

See [Requirements.md](Requirements.md) for the normative contract and [ROADMAP.md](ROADMAP.md) for the implementation checklist.

## Local Development

Backend requirements use Python 3.11 or newer. The existing Python environment must include the project dependencies.

```powershell
Push-Location backend
python -m pytest
uvicorn devstacks_api.main:app --reload --port 8000
```

Frontend requirements use Node.js 22 or newer.

```powershell
Push-Location frontend
npm install
npm run dev
npm run typecheck
```

The frontend runs at `http://localhost:3000`; the API health endpoint is `http://localhost:8000/health`.

## Product Surface

The frontend is a full product application rather than a scaffold. It ships its own design system and component library, and every surface is built to the same standard.

| Surface | Route | What it does |
| --- | --- | --- |
| Marketing | `/` | Lifecycle, assurance model, and FAQ, with the live-preview call to action. |
| Live preview | `/try`, `/try/{username}` | Public GitHub facts, unsaved and unpublished, for a visitor with no account. |
| Authentication | `/login` | GitHub OAuth and email/password, in one split-screen surface. |
| Onboarding | `/onboarding` | Handle claim and first connector, as a progressed wizard. |
| Overview | `/dashboard` | Evidence and review counters, setup checklist, and the claim lifecycle. |
| Review inbox | `/dashboard/review` | List-and-detail triage with keyboard shortcuts, evidence provenance, and approve, edit, reject, or publish. |
| Connections | `/dashboard/connections` | Live connector state, manual sync followed to completion, and the planned connectors. |
| Settings | `/dashboard/settings` | Identity, visibility, appearance, and session. |
| Public profile | `/{handle}` | Published claims with assurance and freshness, an embeddable badge, and structured data. |
| Evidence trail | `/{handle}/claims/{id}` | The chain behind one published claim: every linked observation, its content hash, and the verification decision. |
| Community | `/community`, `/community/{slug}`, `/community/thread/{id}` | Spaces for help, architecture, showcase, and jobs, with a composer that checks a draft before it is sent. |

### Community

Spaces for getting unstuck, arguing about architecture, showing work, and hiring. Three things make it different from a forum with a profanity filter bolted on.

**Voice is earned by evidence.** A post carries the author's verified, topic-matched claims rather than a karma score. A space declares the claim categories it is about, and a member holding a verified claim in one of them is shown as such beside their words. Standing comes from what someone shipped and DevStacks checked, not from how long they have been posting.

**The composer is a linter, not a trapdoor.** `POST /v1/community/preflight` judges a draft without storing it, so the composer warns while the author can still fix the problem. Every warning names the rule that fired and says what to do about it.

**Moderation shows its work.** A post is written together with the verdict that admitted it, and the individual signals are stored alongside. An author can always see why their own post was actioned; nobody is moderated in secret.

The guardrails themselves live in `devstacks_domain/moderation.py` and are deterministic, in keeping with the rule that application code owns policy. Three judgements shape them:

- **Profanity is not abuse.** "This fucking build is broken" is frustration at a machine and is allowed. "You're a fucking idiot" is aimed at a person and is held. Conflating the two drives out candour and keeps the cruelty, because cruel people simply stop swearing.
- **A leaked credential is an emergency, not an offence.** GitHub tokens, AWS keys, private keys, JWTs, and credentials in connection strings are blocked at the highest severity, the excerpt is redacted before it is ever echoed back, and the author is told to rotate it. The block protects the person who wrote the post.
- **A model never decides.** An `AdvisorySignal` from a classifier is recorded and can raise a post to human review, but is capped below `block` in code — nothing is removed from this community on a model's say-so alone.

Matching is anchored to whole words after Unicode, leetspeak, zero-width, repeated-character, and spaced-letter folding, so `f.u.c.k` is caught while Scunthorpe, "assess", and "classic" are not. The default lexicon ships ordinary profanity and insults only; hate terms are supplied by the operator at deployment rather than committed to a public repository.

### Evidence trails

Any reader can open the chain behind a published claim without an account. `GET /v1/public/profiles/{handle}/claims/{claim_revision_id}` projects every linked observation — its relation to the claim, source type, content hash, connector version, assurance class, and validity — alongside the verification decision that let the claim publish. Contradicting evidence is shown next to supporting evidence, because concealing it would make the rest worth nothing.

Two things stay private by construction: the observed payload, and the source reference. A reference can name a private repository, so publishing it would disclose repository names the owner never chose to reveal. The content hash carries the property that matters instead — it proves the observation is fixed, and it changes if the observation changes — without that disclosure. A migration-contract test asserts the projection cannot select either column.

Connector state is read from `GET /v1/connectors`, which projects the caller's own source connections and each one's latest ingestion run. Credential material is never part of that projection: encrypted tokens live in a table the read does not touch. A queued sync is followed through `GET /v1/ingestion-runs/{run_id}` until it reaches a terminal status, so the interface reports what the worker actually did rather than what was requested.

Light and dark themes are both first-class and applied before first paint. Navigation is available from anywhere with `Ctrl-K` (`⌘K` on macOS), and the review queue is fully keyboard-operable. See [frontend/README.md](frontend/README.md) for the design-system rules and the conventions a new surface must follow.

## Supabase Project

The Supabase project has been created. Copy the provided environment templates, obtain the publishable and server-only keys from the project API settings, and follow the migration dry-run procedure in [supabase/README.md](supabase/README.md). Do not commit local environment files or expose the service-role key to the frontend.

## GitHub Connector Setup

Create a GitHub OAuth App and configure its callback URL to exactly match `GITHUB_OAUTH_REDIRECT_URI` in `backend/.env`. Keep wildcard callback matching disabled. The initial connector requests only GitHub's `read:user` scope; repository access is added later with an explicit, separate authorization step.

Set `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, and a server-only `DEVSTACKS_ENCRYPTION_KEY` in `backend/.env`. Generate a local Fernet key with:

```powershell
Push-Location backend
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The encryption key is required to decrypt connector tokens later. Rotate it only through a deliberate credential re-encryption process; losing it makes existing connector tokens unusable.

After authorization, DevStacks queues an initial GitHub evidence sync. Run one queued job locally or from a Railway cron/worker process with:

```powershell
Push-Location backend
devstacks-github-worker
```

Manual refreshes use `POST /v1/connectors/github/{connection_id}/sync` with a valid bearer token and an `Idempotency-Key` header. The worker records `succeeded`, `partial`, `no_op`, or `failed` on the leased ingestion run; it never returns connector tokens to the caller.

## GitHub Webhooks

For each repository that should trigger a refresh, create a GitHub repository webhook with JSON content, TLS verification enabled, the public `POST /v1/webhooks/github` URL, and the value of server-only `GITHUB_WEBHOOK_SECRET`. Subscribe to `push`, `pull_request`, and `release` events. Do not place the secret in frontend configuration.

After GitHub returns the hook ID, the connected user registers its mapping through `POST /v1/connectors/github/{connection_id}/webhooks` with `github_repository_id` and `github_hook_id` query parameters. The API validates the user owns the active connection; incoming deliveries are accepted only after HMAC-SHA256 verification and are replay-safe by their GitHub delivery ID.

Schedule `devstacks-github-worker` as a Railway cron or worker process after creating a Railway service. The repository intentionally has no Railway project identifiers or deployment configuration, so infrastructure provisioning remains an explicit operational step.