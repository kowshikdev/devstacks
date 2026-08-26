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

- [x] `GH-001` Implement separate GitHub connector authorization and identity binding. OAuth state/PKCE, encrypted token persistence, and immutable identity binding are implemented and applied. Depends on `FOUND-002`; OAuth security gate.
- [-] `GH-002` Ingest repositories, commits, pull requests, releases, and normalized authorship evidence. Bounded REST collection, immutable evidence append, queued worker execution, and manual re-sync boundary are implemented and applied; live connector configuration and smoke validation remain. Depends on `FOUND-003`, `GH-001`.
- [-] `GH-003` Add signed, replay-safe webhook handling and scheduled refresh. Raw-body HMAC-SHA256 verification, hook-to-connection mapping, and atomic replay queueing are implemented and applied; Railway scheduling and live webhook validation remain. Depends on `FOUND-006`, `GH-002`; webhook security gate.
- [x] `GH-004` Add affected-evidence traversal and targeted revalidation. Deterministic traversal RPC, freshness-assessment RPC, domain `TargetedRevalidationService`, and worker wiring after every created evidence version are implemented and applied; freshness assessments never rewrite verification, review, or publication history. Depends on `FOUND-004`, `FOUND-006`, `GH-003`.
- [ ] `GH-005` Create structured candidate claims and first-class claim revisions with evidence links. Depends on `GH-002`, `FOUND-004`.
- [ ] `GH-006` Add verifier decisions, manual review, provenance-guarded publication, and public profile projection. Depends on `GH-005`, `FOUND-005`.
- [ ] `GH-007` Display evidence explanations and freshness/assurance degradation. Depends on `GH-006`.
- [ ] `GH-008` Pass the golden-path gate: provenance, replay, state transitions, tenancy, security, and manual publication. Depends on `GH-001` through `GH-007`.

## Phase 3: Verifier Maturity

- [ ] `VERIFY-001` Add Pydantic-validated Deep Agents extractor/verifier subagents with read-only evidence tools. Depends on `GH-008`.
- [ ] `VERIFY-002` Record model, prompt, ruleset, schema, evidence inputs, and outputs in `agent_runs`. Depends on `VERIFY-001`.
- [ ] `VERIFY-003` Configure durable LangGraph checkpointing and stable thread IDs for resumable workflows. Depends on `VERIFY-001`.
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
