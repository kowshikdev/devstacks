# DevStacks Copilot Instructions

## Project

DevStacks is a continuously verified developer evidence graph. The public developer profile is its first projection.

The core model is:

Source → immutable Evidence Version → Claim Revision → Verification/Review → Published Profile

Every published claim revision must be traversable to its verification decision, evidence relationships, immutable evidence versions, source artifact, and acquisition metadata. Complete provenance is a domain invariant enforced by application code.

## Architecture

Frontend:
- Next.js with App Router
- TypeScript

Backend:
- Python
- FastAPI
- deepagents / LangGraph
- Supabase / PostgreSQL

Infrastructure:
- Vercel for frontend
- Railway for backend and workers
- Supabase for database, auth, and storage

## Repository principles

- Keep the architecture simple and incremental.
- Do not introduce infrastructure such as Redis, Kafka, Celery, or additional services unless a concrete requirement justifies it.
- Prefer deterministic code for data extraction, hashing, timestamps, authorship, and state transitions.
- Use LLMs for interpretation, classification, claim generation, and verification, not as the source of truth.
- Do not silently weaken evidence requirements to make a claim pass verification.
- Keep the implementation centered on the GitHub golden path before adding connector breadth.
- Treat security, privacy, and tenancy as prerequisites for every connector, not late release hardening.

## Evidence, claims, and provenance

- Evidence versions and claim revisions are immutable; corrections create superseding records.
- A claim revision may link to multiple evidence versions using `supports`, `contradicts`, or `context` relationships.
- Claims must have explicit provenance references and cannot be published without a complete provenance chain.
- Claims must never be published without passing the configured verification, review, and publication rules.
- Preserve evidence and claim history rather than overwriting previous records.
- Treat stale, invalid, ambiguous, and contradicted evidence differently.
- Prefer "ambiguous" or "unverified" over guessing.
- Never invent developer experience, ownership, leadership, impact, metrics, or skills that cannot be supported by evidence.
- Keep verification, review, publication, freshness, and contest states independent; never collapse them into one status field.
- Keep source assurance explicit: provider-observed, public-page-verified, official-export/user-supplied, self-attested, unavailable, and contradicted are not interchangeable.

## MCP / Documentation

When working with a library, framework, SDK, API, or platform:

1. Use Context7 to retrieve current documentation before implementing unfamiliar or version-sensitive APIs.
2. Prefer documentation matching the version installed in this repository.
3. Prefer official documentation over model memory.
4. Do not assume an API exists based only on prior knowledge.
5. Check the current documentation before introducing a new dependency or changing framework-level behavior.

Use GitHub tools for repository, issue, pull request, commit, and GitHub API information when available.

## Development workflow

Before changing code:

- Inspect the existing implementation and related tests.
- Follow existing project patterns before introducing new abstractions.
- Make the smallest change that solves the problem.

After changing code:

- Run the relevant tests.
- Run lint/type checks where applicable.
- Do not claim something is fixed without validating it.
- Follow `ROADMAP.md` for dependency-ordered implementation and update its task state when scope changes.
- Build and validate the golden path: source event, immutable evidence, claim revision, verification, review, publication, profile projection, and targeted revalidation.
- Do not enable auto-publication until all first-release connectors and manual-review/verifier maturity gates pass. Auto-publication requires per-user opt-in, an immutable allowlisted policy, deterministic predicates, and a verifier threshold; model confidence alone is never authority.

## Trust boundary

Never convert an inference into evidence.

Evidence is produced by connectors and deterministic ingestion. Ingestion must be idempotent, versioned, and capable of explicit no-op, partial, unavailable, and invalid outcomes.

Agents may interpret evidence and propose claims, but must preserve:
- source
- source reference
- fetched timestamp
- observation timestamp
- evidence version/hash
- verification state
- claim revision and policy version

Deep Agents subagents must return schema-validated outputs and use read-only evidence tools. LangGraph workflows that pause for human input require durable checkpointing and a stable `thread_id`; interrupted nodes replay, so side effects happen after interrupts and are idempotent. Dashboard review actions should normally be ordinary audited API transitions.

When evidence is insufficient, return an explicit uncertainty state instead of filling the gap.