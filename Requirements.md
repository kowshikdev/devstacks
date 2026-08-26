# DevStacks — Technical Requirements & Architecture Spec

Version 0.2 · Normative product and implementation contract

---

## 1. Vision & Problem Statement

An open-source, self-hostable **continuously verified developer evidence graph**. It turns source observations into explainable, reviewable developer claims and exposes a public profile as the first projection of that graph.

Core differentiator: immutable evidence versions, first-class claim revisions, explicit provenance, independent verification/review/publication/freshness states, and targeted revalidation.

The canonical flow is:

```
Source → immutable evidence version → claim revision → verification/review → publication → profile projection
```

The publication service must reject incomplete provenance. Models may interpret evidence and propose claims, but may not create evidence, bind identity, authorize publication, bypass policy, or mutate history.

---

## 2. Goals & Non-Goals (v1)

**In scope (first public release):**
- GitHub as the primary, fully-automated data source (official OAuth + API).
- LinkedIn via user-uploaded official data export (`.zip`/CSV) — no scraping, no live sync.
- LeetCode via user-supplied public username (best-effort public stats only).
- HackerRank via certificate verification URLs (`hackerrank.com/certificates/{hash}`) the user pastes in.
- Claims engine: every generated profile line traces to an evidence record with a timestamp.
- Staleness detection: re-check evidence on GitHub webhook events + scheduled sweep; flag affected claims.
- A review/approval step before any claim is marked "published" on the public profile.
- A minimal eval set to measure claim accuracy (precision: is the claim actually supported; coverage: did we catch what's really there).
- A review dashboard, evidence explanations, freshness/assurance labels, and a public profile projection.
- Opt-in policy-based auto-publication only after all four connectors and manual-review/verifier maturity pass; shadow mode comes first.

**Explicitly out of scope (first public release):**
- LinkedIn live connector / automated scraping.
- LeetCode/HackerRank session-cookie automation (fragile, ToS gray zone, risks the user's account).
- Ranking or cross-user comparison of any kind.
- "Impact"/soft-skill claims that can't be tied to hard evidence.
- Managed Deep Agents (LangSmith Cloud) — self-host the harness instead; revisit later if infra ops become the bottleneck.
- Resume generation/export, MCP developer-profile tools, and additional infrastructure without a measured requirement.

---

## 3. Data Access Strategy (recap of platform decisions)

| Platform | Access method | Automation level | Notes |
|---|---|---|---|
| GitHub | OAuth App + REST/GraphQL API | Fully automated, webhook-driven | Green — sanctioned, reliable, real evidence (diffs, commits) |
| LinkedIn | OAuth (thin profile only) + user-uploaded data export | Manual upload for real content | Red for scraping — export is the only compliant path to positions/skills/certs |
| LeetCode | Public username, unofficial GraphQL, called server-side on user request only | Semi-manual, best-effort | No OAuth exists. Never store session cookies. Label as self-reported. |
| HackerRank | User-pasted certificate URL, verified by fetching the public cert page | Manual entry | No consumer API. Certificate hash is the durable evidence anchor. |

---

## 4. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | Next.js (App Router), deployed on Vercel | Matches your stated plan; good fit for auth UX, dashboards, review UI |
| Backend / agent runtime | FastAPI (Python), deployed on Railway | Matches your existing stack (Python/FastAPI/LangGraph); Railway gives a persistent process for webhooks, schedulers, and long-running agent runs |
| Agent framework | `deepagents` (open source Python package) | Direct dependency — subagents, planning, virtual filesystem, HITL interrupts, all reusable as-is |
| Claims/evidence engine | Custom (own Supabase schema) | **Not** a dependency on `openwiki` itself — openwiki is built for codebase docs, not external multi-platform profiles. Borrow the *pattern* (claim → evidence → version → staleness), implement it in your own tables (Section 6). Optionally emit an OKF-like JSON export for portability later. |
| Production agent hosting | Self-hosted `deepagents` on Railway | Managed Deep Agents (LangSmith Cloud) is a valid *future* migration if you want offloaded sandboxes/durable execution, but it's beta, CLI-first, US-region-only, and adds a hosting dependency you don't need for v1. |
| Evals | Lightweight custom harness (pytest + labeled fixtures), optionally logged to LangSmith | Full Harbor/ReviewBench-style infra is overkill for v1; borrow their *method* (curate real examples, score coverage + precision) without the tooling overhead. |
| Database / Auth / Storage | Supabase (Postgres + Auth + Storage) | As planned. Supabase Auth also cleanly handles the GitHub/LinkedIn OAuth flows via its provider integrations. |
| Background jobs | Railway cron / worker process | Nightly staleness sweep, token refresh, webhook queue processing |

---

## 5. System Architecture (high level)

```
┌─────────────────────┐        ┌──────────────────────────┐        ┌────────────────────┐
│   Next.js (Vercel)   │──API──▶│   FastAPI (Railway)      │──────▶│   Supabase          │
│  - Auth UI           │        │  - deepagents runtime    │        │  - Postgres (claims,│
│  - Profile dashboard │◀──────│  - Claims/evidence engine │◀──────│    evidence, users) │
│  - Review/approve UI │        │  - Connector adapters     │        │  - Auth (OAuth)     │
│  - Public profile page│       │  - Scheduler / worker     │        │  - Storage (uploads)│
└─────────────────────┘        └──────────────────────────┘        └────────────────────┘
        ▲                              ▲        ▲
        │                              │        │
   User browses,                GitHub webhook   Scheduled staleness
   uploads LinkedIn              (push, release,  sweep (cron)
   export, reviews               PR merged)
   pending claims
```

- **Next.js**: owns the UI and session handling. Talks to the internet-facing FastAPI API using validated Supabase JWTs; neither service boundary is implicitly trusted.
- **FastAPI on Railway**: owns everything stateful/long-running — the deepagents subagent graph, GitHub webhook receiver, connector calls, scheduler.
- **Supabase**: source of truth for claims, evidence, connector tokens (encrypted), and file storage for uploaded LinkedIn exports.

---

## 6. Data Model (Supabase / Postgres)

```sql
-- Users are handled by Supabase Auth; reference auth.users(id)

create table connectors (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  platform text not null check (platform in ('github','linkedin','leetcode','hackerrank')),
  external_username text,
  oauth_access_token_encrypted text,   -- null for manual-entry platforms
  oauth_refresh_token_encrypted text,
  connected_at timestamptz default now(),
  last_synced_at timestamptz
);

create table evidence (
  id uuid primary key default gen_random_uuid(),
  connector_id uuid references connectors(id),
  source_type text not null,
  source_ref text not null,
  created_at timestamptz default now()
);

create table evidence_versions (
  id uuid primary key default gen_random_uuid(),
  evidence_id uuid references evidence(id) not null,
  raw_payload jsonb not null,
  content_hash text not null,
  fetched_at timestamptz default now(),
  observed_at timestamptz,
  connector_version text not null,
  assurance_class text not null,
  validity text not null default 'current'
    check (validity in ('current','stale','unavailable','invalid','superseded')),
  unique (evidence_id, content_hash)
);

create table claims (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  category text not null,
  created_at timestamptz default now()
);

create table claim_revisions (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid references claims(id) not null,
  statement text not null,
  revision_number integer not null,
  valid_from timestamptz,
  valid_until timestamptz,
  created_at timestamptz default now(),
  unique (claim_id, revision_number)
);

create table claim_evidence_links (
  claim_revision_id uuid references claim_revisions(id) not null,
  evidence_version_id uuid references evidence_versions(id) not null,
  relation text not null check (relation in ('supports','contradicts','context')),
  created_at timestamptz default now(),
  primary key (claim_revision_id, evidence_version_id)
);

create table verification_decisions (
  id uuid primary key default gen_random_uuid(),
  claim_revision_id uuid references claim_revisions(id) not null,
  status text not null check (status in ('unverified','verified','ambiguous','unsupported','contradicted')),
  score numeric check (score >= 0 and score <= 1),
  agent_run_id uuid,
  created_at timestamptz default now()
);

create table review_decisions (
  id uuid primary key default gen_random_uuid(),
  claim_revision_id uuid references claim_revisions(id) not null,
  action text not null check (action in ('approve','edit','reject')),
  actor_user_id uuid references auth.users(id),
  note text,
  created_at timestamptz default now()
);

create table publications (
  id uuid primary key default gen_random_uuid(),
  claim_revision_id uuid references claim_revisions(id) not null,
  status text not null check (status in ('unpublished','published','withdrawn')),
  policy_version text,
  published_at timestamptz,
  withdrawn_at timestamptz
);
```

Row-Level Security: every table scoped to `user_id = auth.uid()` except service-role writes from the FastAPI backend.

**Staleness check logic:** on webhook/sweep, re-fetch affected evidence, canonicalize and recompute `content_hash`, and create a new immutable evidence version when changed. Traverse `claim_evidence_links` to affected claim revisions and create a freshness assessment. A freshness change never rewrites verification, review, or publication history; it is surfaced in the review UI and may trigger withdrawal through an explicit transition.

---

## 7. Agent Architecture (Deep Agents and LangGraph)

Subagents, mirroring the `deep-agent-template` shape:

- **`extractor` subagent** — receives normalized evidence and proposes schema-validated claim revisions with claim-evidence links. It is read-only and never writes publication state.
- **`verifier` subagent** — assesses semantic support, authorship ambiguity, contradictions, and confidence. It returns structured output; deterministic policy and application services decide state transitions.
- **Review and publication** — dashboard approval is an audited API transition. Auto-publication is disabled until all connectors and verifier maturity pass, then requires per-user opt-in, an immutable allowlisted policy, deterministic predicates, current evidence, and a verifier threshold.
- **LangGraph interrupts** — if an agent workflow pauses for human input, it requires a durable checkpointer and stable `thread_id`. Because interrupted nodes replay, side effects occur after the interrupt and are idempotent.

Project layout (adapted from Managed Deep Agents' shape, run as a plain FastAPI service instead of on LangSmith Cloud):

```
backend/
  agent/
    graph.py            # deepagents graph: extractor -> verifier -> HITL gate
    subagents/
      extractor.py
      verifier.py
  connectors/
    github.py            # OAuth + REST/GraphQL client, webhook handler
    linkedin.py           # OAuth (thin) + export-file parser
    leetcode.py           # public GraphQL client, no auth stored
    hackerrank.py          # cert URL fetch/verify
  claims/
    engine.py            # claim CRUD, staleness comparison logic
  api/
    routes/              # FastAPI routers called by Next.js
    webhooks/             # GitHub webhook receiver
  scheduler/
    staleness_sweep.py    # Railway cron entrypoint
  evals/
    fixtures/             # hand-labeled repo -> expected-claims examples
    run_eval.py
```

---

## 8. API Surface (FastAPI, called by Next.js)

- `POST /connectors/github/callback` — OAuth exchange, store encrypted token
- `POST /connectors/linkedin/export` — accept uploaded export file, parse, create evidence rows
- `POST /connectors/leetcode` — store username, trigger one-off fetch
- `POST /connectors/hackerrank/certificate` — accept cert URL, verify, create evidence row
- `POST /webhooks/github` — receive push/PR/release events, trigger extractor run + staleness check
- `GET /claims?review=pending` — for the review UI, returning claim revisions and provenance
- `POST /claim-revisions/{id}/approve` / `/reject` / `/edit`
- `POST /claim-revisions/{id}/contest` — record contradictory or disputed evidence
- `GET /runs/{id}` — expose ingestion/agent progress, partial failures, and no-op results
- `GET /profile/{username}` — public read-only rendered profile (published claims only)

---

## 9. Background Jobs

- **Nightly freshness sweep** (Railway cron): re-fetch evidence tied to active connectors, create immutable changed versions, and reverify only affected claim revisions.
- **GitHub webhook processing**: near-real-time, queued (simple Postgres-backed queue or Railway's own job runner is enough at this scale — no need for Redis/Celery in v1).
- **OAuth token refresh**: GitHub tokens as needed; LinkedIn thin-scope token refresh.

---

## 10. Auth, Security, and Privacy

- Separate Supabase login identity from GitHub connector authorization. Validate OAuth state/CSRF, use minimum scopes, and support token encryption, rotation, and revocation.
- The Vercel-to-Railway API is internet-facing. Validate JWT issuer, audience, expiry, subject, and resource ownership on every authenticated request.
- Enforce tenant isolation in queries, service methods, RLS, storage policies, public projections, and least-privilege service-role boundaries.
- Validate GitHub webhook signatures, delivery IDs, and replay windows before queueing work.
- LinkedIn exports require archive size, decompression, path traversal, file-type, and retention limits. Parse only approved fields, then delete raw files on the configured schedule.
- HackerRank fetches require hostname/path allowlisting, redirect controls, private-address blocking, response limits, and timeouts to prevent SSRF.
- Never log or persist LeetCode session cookies. Apply consent, visibility, minimization, retention, account export, and account deletion controls to all user data.

---

## 11. Evals Strategy

Small, real, hand-labeled set > large synthetic set:
1. Pick 10–15 real repos (yours + volunteers').
2. For each, hand-write the claims a careful human would extract, with evidence.
3. Run the `extractor` + `verifier` pipeline, score:
   - **Coverage**: did it find the claims a human would (same method as ReviewBench).
   - **Precision**: of the claims it made, how many are actually supported.
4. Track this as a regression suite — rerun whenever you change the extraction prompt.

Release gates are at least 95% claim precision, 80% labeled-set coverage/recall, 100% published-revision provenance, zero policy-bypassing publications, zero duplicate replay effects, and complete rule/branch coverage for deterministic lifecycle transitions. Auto-publication additionally requires 100% fixture precision and at least 99% precision in a documented shadow sample.

Skip LangSmith/Harbor infra for v1; a `pytest` + fixtures script logging a coverage/precision table is enough to make real decisions.

---

## 12. Deployment Topology

- **Vercel**: Next.js frontend, preview deployments per PR.
- **Railway**: FastAPI service (web process) + separate worker process for scheduler/webhook queue, same repo/monorepo, two Railway services.
- **Supabase**: managed Postgres + Auth + Storage, single project, separate dev/prod projects recommended once you have real users.

---

## 13. Open Questions / Risks

- Ambiguous authorship (squash-merged group PRs, pair programming) — `verifier` must default to `confidence: ambiguous` rather than guess; needs a UI affordance for the user to clarify/self-attest.
- LeetCode/HackerRank endpoint stability is genuinely unconfirmed long-term — build the connector interface so a platform can be disabled without breaking the rest of the system.
- Public profile page (`/profile/{username}`) needs a clear "last verified" timestamp per claim so a *viewer* (recruiter, etc.) can trust the freshness, not just the profile owner.

---

## 14. Milestones

The complete dependency-ordered checklist is maintained in `ROADMAP.md`.

- **Phase 0**: specification, acceptance traceability, threat model, and version pinning.
- **Phase 1**: domain schema, immutable provenance, security/tenancy, lifecycle services, and Postgres-backed jobs.
- **Phase 2**: GitHub golden path with manual review, public projection, freshness, and targeted revalidation.
- **Phase 3**: Deep Agents/LangGraph verifier maturity and labeled evaluations.
- **Phase 4**: LinkedIn export, HackerRank certificate, and LeetCode public snapshot connectors.
- **Phase 5**: cross-source contests, privacy operations, and manual-review maturity.
- **Phase 6**: shadow-mode, then opt-in policy-based auto-publication.
- **Phase 7**: release hardening and post-v1 artifacts.