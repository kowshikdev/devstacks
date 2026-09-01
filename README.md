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