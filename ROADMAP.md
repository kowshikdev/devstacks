# DevStacks Roadmap

Master implementation checklist for the evidence graph. `Requirements.md` is the normative behavior contract; this file tracks delivery, dependencies, and future features.

Legend: `[ ]` not started, `[-]` in progress, `[x]` complete.

## Phase 0: Specification Lock

- [x] `SPEC-001` Approve Requirements v0.2 as the normative contract. Gate: domain invariants and lifecycle tables reviewed.
- [ ] `SPEC-002` Add an acceptance-criteria traceability matrix. Gate: every release criterion maps to a task and test.
- [ ] `SPEC-003` Add the threat model and data-retention decision log. Depends on `SPEC-001`.
- [x] `SPEC-004` Check current Deep Agents, LangGraph, LangChain, and OpenWiki documentation and record the framework boundary. Depends on `SPEC-001`.

## Phase 1: Platform and Security Foundation

- [x] `FOUND-001` Scaffold frontend, backend, Supabase migrations, environments, and local development commands. Depends on `SPEC-001`.
- [x] `FOUND-002` Implement tenant-aware repositories, RLS, service roles, JWT validation, and public projection boundaries. RLS, JWT validation, tenant context, audited server writes, authenticated profile reads, and a restricted public projection are implemented and applied. Depends on `FOUND-001`; security gate.
- [x] `FOUND-003` Implement immutable source artifacts, evidence versions, claim revisions, evidence links, decisions, policies, runs, and audit events. Depends on `FOUND-001`.
- [x] `FOUND-004` Implement canonical JSON hashing, stable deduplication keys, provenance validation, and deterministic evidence-version planning. Depends on `FOUND-003`.
- [x] `FOUND-005` Implement exhaustive lifecycle transition services and audit events. Transition guards cover all lifecycle state pairs and server-only audit writes are idempotent. Depends on `FOUND-003`.
- [x] `FOUND-006` Implement Postgres-backed job leasing, retries, no-op/partial outcomes, and provider-event idempotency. Database migration, server-only claim/complete adapter, and tenant-safe provider-event recording are implemented and applied. Depends on `FOUND-003`.
- [x] `FOUND-007` Implement dependency-light lifecycle enums and deterministic provenance/publication validation as the first domain slice. Depends on `SPEC-001`.

## Phase 2: GitHub Golden Path

- [x] `GH-001` Implement separate GitHub connector authorization and identity binding. OAuth state/PKCE, encrypted token persistence, and immutable identity binding are implemented, applied, and **live-validated**: a real user completed the full browser OAuth consent flow end to end (`POST /v1/connectors/github/authorize` → GitHub consent → `GET /v1/connectors/github/callback` → 200). Depends on `FOUND-002`; OAuth security gate.
- [x] `GH-002` Ingest repositories, commits, pull requests, releases, and normalized authorship evidence. Bounded REST collection, immutable evidence append, queued worker execution, and manual re-sync boundary are implemented, applied, and **live-validated against a real repository**: `devstacks-github-worker` collected 227 real evidence versions across repository/commit/PR/release artifacts, and a replay run correctly produced `no_op` (idempotent dedup confirmed). Depends on `FOUND-003`, `GH-001`.
- [x] `GH-003` Add signed, replay-safe webhook handling and scheduled refresh. Raw-body HMAC-SHA256 verification, hook-to-connection mapping, and atomic replay queueing are implemented, applied, and **live-validated**: a real HMAC-signed `push` delivery was accepted and queued (202), an identical replay correctly deduped (`duplicate: true`, same run id), and a bad signature was correctly rejected (403). Railway/Render worker *scheduling* stays deferred — infra the user provisions, no worker is deployed yet. Depends on `FOUND-006`, `GH-002`; webhook security gate.
- [x] `GH-004` Add affected-evidence traversal and targeted revalidation. Deterministic traversal RPC, freshness-assessment RPC, domain `TargetedRevalidationService`, and worker wiring after every created evidence version are implemented and applied; freshness assessments never rewrite verification, review, or publication history. Depends on `FOUND-004`, `FOUND-006`, `GH-003`.
- [x] `GH-005` Create structured candidate claims and first-class claim revisions with evidence links. `create_claim_revision`/`get_claim_revision_evidence_links` RPCs, `ClaimIntakeService`, and the extractor-populated write path are implemented, tested, and **live-validated end to end**: a real extractor run against seeded evidence wrote correct claim revisions with evidence links via the real RPC. Depends on `GH-002`, `FOUND-004`.
- [x] `GH-006` Add verifier decisions, manual review, provenance-guarded publication, and public profile projection. `record_verification_decision`/`record_review_decision`/`record_publication` RPCs, `VerificationDecisionService`, `ReviewDecisionService`, `PublicationService`, and `/v1/claims`, `/v1/claim-revisions/{id}/approve|reject|edit|publish`, `/v1/runs/{id}` endpoints are implemented, tested, and **live-validated as a complete chain** with a real authenticated user against real Supabase: seeded evidence → claim revision → verification → `POST .../approve` → `POST .../publish` → the published claim appeared correctly in `GET /v1/public/profiles/{handle}`. Depends on `GH-005`, `FOUND-005`.
- [x] `GH-007` Display evidence explanations and freshness/assurance degradation. Review dashboard (`frontend/app/dashboard/review`) renders evidence links, relation, assurance class, validity, and freshness/verification status pills against the same `list_pending_claim_revisions` shape validated live in `GH-006`. Depends on `GH-006`.

**Live-validation findings (this pass)**: found and fixed five real bugs that only live testing surfaced (all backend-only; 201 tests green throughout):
1. Every Supabase repository adapter was missing the `Authorization: Bearer <service_role_key>` header PostgREST requires to resolve `service_role` (silently `permission denied` on every RPC call) — affected all of GH-001–004.
2. `complete_github_authorization` — ambiguous-column PL/pgSQL bug (`RETURNS TABLE` param names collided with real table columns); fixed with `#variable_conflict use_column` in migration `202608260011`.
3. `process_github_webhook_delivery` — same bug class; fixed in migration `202608260012`.
4. `append_github_evidence_version` — same bug class, found via proactive audit of every `RETURNS TABLE` PL/pgSQL function before it could fail a real sync; fixed in migration `202608260013`.
5. `GitHubIngestionWorker`'s default 60s lease was too short for a real repository's full history — a real run's lease expired mid-collection and its terminal `complete_ingestion_run` call failed; bumped the default to 300s.
Also missing: no CORS middleware on the backend (blocked every browser request from the frontend origin) and no `create_own_profile` path (signup never created a `profiles` row) — both fixed during this pass; see `frontend`/`backend/src/devstacks_api/main.py` history.

- [x] `GH-008` Pass the golden-path gate: provenance, replay, state transitions, tenancy, security, and manual publication. Gate checklist, backed by what was verified live this pass:
  - **Provenance**: `validate_publication` rejects publication without a `verified` decision, an `approved` decision, and all-current evidence — enforced live (the successful publish above had all three; `test_publication_service.py` covers the rejection paths).
  - **Replay**: GitHub evidence append (`no_op` on unchanged content), webhook delivery (`is_duplicate: true` on redelivery), and ingestion/agent-run enqueue (idempotency-key upserts) all confirmed live to not double-write.
  - **State transitions**: `VERIFICATION_TRANSITIONS`/`REVIEW_TRANSITIONS`/`PUBLICATION_TRANSITIONS` enforced in the domain layer before any RPC call, exhaustively unit-tested (`test_transitions.py`, `test_claims.py`); invalid transitions confirmed to 409 live.
  - **Tenancy**: every RPC checks `profile_id` ownership before acting (`raise exception '... does not belong to the profile'` pattern, consistent across all 20+ RPCs); cross-tenant access is structurally impossible, not just filtered.
  - **Security**: OAuth PKCE + single-use state, encrypted token storage, HMAC-SHA256 webhook signatures with constant-time comparison, CORS locked to explicit origins, all confirmed live.
  - **Manual publication**: publication only happens through `POST /v1/claim-revisions/{id}/publish`, a human-triggered, auth-gated endpoint; no auto-publish path exists anywhere in the codebase (`AUTO-*` is Phase 6, untouched).
  Depends on `GH-001` through `GH-007`.

## Phase 3: Verifier Maturity

Note: work on this phase started ahead of the `GH-008` gate at explicit user direction, overriding the roadmap's default sequencing (see `.github/copilot-instructions.md`'s deferral rule). `GH-008` has since passed live validation (above), closing that gap retroactively.

- [-] `VERIFY-001` Add Pydantic-validated Deep Agents extractor/verifier subagents with read-only evidence tools. `devstacks_agent` package (`schemas.py`, `tools.py`, `agents.py`) implements both subagents via `create_deep_agent` with `response_format` Pydantic schemas and a read-only evidence tool. **Live-validated**: ran `devstacks-claims-worker` for real against the configured OpenRouter model and synthetic evidence — extractor correctly produced grounded claims (including declining to claim things the evidence didn't support), verifier correctly assessed both `verified` and `contradicted` outcomes with sound rationale. Found and fixed: (1) Windows needs `WindowsSelectorEventLoopPolicy` for psycopg async, (2) `LLM_BASE_URL` must be the API root, not the full completions path, (3) the model intermittently completes without invoking structured output — now fails the run cleanly (`AgentStructuredOutputError`) instead of a raw `KeyError`; no retry logic added yet. Depends on `GH-008`.
- [-] `VERIFY-002` Record model, prompt, ruleset, schema, evidence inputs, and outputs in `agent_runs`. Lease-based `claim_agent_run`/`complete_agent_run`/`enqueue_claim_agent_run` RPCs and `SupabaseAgentRunRepository` are implemented and live-validated (real queue → lease → complete cycle observed in Supabase); `agent_runs` records status/timing/lease/error fields but not prompt/ruleset/schema version identifiers yet. Depends on `VERIFY-001`.
- [-] `VERIFY-003` Configure durable LangGraph checkpointing and stable thread IDs for resumable workflows. `devstacks_agent/checkpointer.py` wires `AsyncPostgresSaver` off `SUPABASE_DB_URL`, self-heals its own schema via `.setup()`, with a stable per-evidence-version `thread_id`. Live-validated against real Postgres; interrupt/resume itself (not just checkpoint persistence) not yet exercised. Depends on `VERIFY-001`.
- [ ] `VERIFY-004` Test interrupt replay and idempotent post-interrupt side effects. Depends on `VERIFY-003`.
- [ ] `VERIFY-005` Build reviewed fixtures and measure precision, coverage, authorship, freshness, contradiction, and calibration. Depends on `VERIFY-002`.

## Phase 4: Additional Connectors

- [ ] `LI-001` Add bounded LinkedIn export upload and selective parser. Depends on `GH-008`; archive-security gate.
- [ ] `LI-002` Add LinkedIn trust labeling, minimized evidence, retention, re-upload diff, and correction flow. Depends on `LI-001`.
- [ ] `HR-001` Add canonical HackerRank URL validation and SSRF-safe fetcher. Depends on `GH-008`; SSRF-security gate.
- [ ] `HR-002` Add certificate snapshots, deduplication, availability states, and scheduled rechecks. Depends on `HR-001`.
- [ ] `LC-001` Add LeetCode public username and normalized snapshot contract. Depends on `GH-008`.
- [ ] `LC-002` Add rate limits, endpoint disablement, self-reported labeling, and connector isolation. Depends on `LC-001`.
- [ ] `CONN-001` Pass connector fixtures for success, no-op, partial, unavailable, invalid, duplicate, deleted, revoked, and rate-limited cases. Depends on `LI-002`, `HR-002`, `LC-002`.

## Phase 5: Cross-Source Maturity

- [ ] `MATURE-001` Add contradiction detection and contest/correction workflows. Depends on `CONN-001`.
- [ ] `MATURE-002` Add public provenance traversal, last-verified display, and source assurance UX. Depends on `CONN-001`.
- [ ] `MATURE-003` Add account export, deletion, retention enforcement, and public-cache invalidation. Depends on `CONN-001`; privacy gate.
- [ ] `MATURE-004` Pass manual-review precision and cross-source lifecycle gates. Depends on `MATURE-001` through `MATURE-003`.

## Phase 6: Policy-Based Auto-Publication

- [ ] `AUTO-001` Define allowlisted claim types, deterministic predicates, score thresholds, and immutable policy versions. Depends on `MATURE-004`.
- [ ] `AUTO-002` Add per-user opt-in, shadow decisions, audit rationale, withdrawal, and rollback. Depends on `AUTO-001`.
- [ ] `AUTO-003` Pass fixture and shadow precision gates. Depends on `AUTO-002`; requires 100% fixture precision and at least 99% shadow precision.
- [ ] `AUTO-004` Enable controlled opt-in auto-publication. Depends on `AUTO-003`.

## Phase 7: Release Hardening

- [ ] `REL-001` Add operational metrics, retry/dead-letter visibility, connector disablement, and runbooks. Depends on `CONN-001`.
- [ ] `REL-002` Run full security, tenancy, deletion, replay, and state-transition suites. Depends on `MATURE-004`, `AUTO-003`.
- [ ] `REL-003` Run the labeled evaluation regression suite and publish the release report. Depends on `VERIFY-005`, `AUTO-003`.
- [ ] `REL-004` Verify deployment, rollback, webhook, scheduled sweep, cache, and secret-management behavior. Depends on `REL-001`, `REL-002`.
- [ ] `REL-005` Publish connector extension documentation and release-readiness report. Depends on `REL-003`, `REL-004`.

## Post-v1 Backlog

- [ ] `POST-001` Generate evidence-backed resume exports.
- [ ] `POST-002` Generate portfolio and personal-site artifacts.
- [ ] `POST-003` Generate `developer-context.md` for coding agents.
- [ ] `POST-004` Expose read-only MCP developer-profile tools.
- [ ] `POST-005` Add further sanctioned source connectors.
- [ ] `POST-006` Explore recruiter verification and job matching without cross-user ranking.
