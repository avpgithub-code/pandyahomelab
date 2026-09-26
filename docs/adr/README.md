# Architecture Decision Records — pandyaHomeLab

## What is this folder

This folder contains **Architecture Decision Records (ADRs)** — short, structured documents that capture significant architectural decisions made during the design and construction of pandyaHomeLab.

Each ADR records:
- **The decision** that was made
- **The context** that led to it (what problem we were solving)
- **The alternatives** that were considered
- **The consequences** — both positive and negative — of the choice
- **The status** — proposed, accepted, deprecated, or superseded

## Why ADRs exist

Decks and diagrams are excellent at communicating *what* an architecture looks like. They are poor at communicating *why* it looks that way. Six months after a decision is made, the rationale evaporates from human memory but the architecture remains. Without ADRs, future maintainers (including future-you) inherit decisions with no context — and either preserve them out of fear or overturn them out of ignorance.

ADRs solve this by capturing the *reasoning* alongside the result. When someone asks "why did we choose path-based routing instead of subdomain-based?", the answer is one grep away.

## When to write a new ADR

Write an ADR when a decision:
- Affects more than one component of the platform
- Is hard or expensive to reverse
- Was non-obvious or had multiple defensible alternatives
- Will be questioned later by someone unfamiliar with the original context

Don't write an ADR for routine choices ("we use Postgres 16.x", "container ports start at 8000"). Those belong in code comments or operational runbooks.

## The format

Each ADR follows this structure:

1. **Title** — short, declarative ("Networks isolate by trust boundary")
2. **Status** — Proposed / Accepted / Deprecated / Superseded by ADR-XXX
3. **Context** — what was the situation that demanded a decision
4. **Decision** — what we chose, stated plainly
5. **Alternatives considered** — what else we looked at, and why we didn't pick them
6. **Consequences** — what this enables, what it costs, what it forecloses

ADRs are immutable. Once accepted, they are not edited. If a decision changes, write a new ADR that supersedes the old one — leaving the original visible preserves the history of thought.

## Current ADRs

### Stage 1 — Conceptual Design (April 2026)

| #   | Title                                                       | Status   |
|-----|-------------------------------------------------------------|----------|
| 001 | Networks isolate by trust boundary, not category            | Accepted |
| 002 | Synology and AWS layouts mirror 1:1 with AZ divergence      | Accepted |
| 003 | URL hierarchy uses four-level progressive disclosure        | Accepted |
| 004 | Level 4 demos named with dataset-algorithm convention       | Accepted |
| 005 | Path-based routing for Stage 1, subdomain hybrid deferred   | Accepted |
| 006 | Custom Nginx replaces DSM reverse proxy on host ports       | Accepted |

### Stage 2 — Synology Implementation (May 2026)

| #   | Title                                                       | Status   |
|-----|-------------------------------------------------------------|----------|
| 007 | Repository layout follows 3-tier multi-service shape        | Superseded by 007 (v3) |
| 008 | Repository packaging is a single monorepo                   | Accepted |
| 009 | Runtime filesystem layout and permissions on Synology NAS   | Accepted |
| 010 | Synology secrets management                                 | Accepted |
| 011 | Per-service conventions                                     | Accepted |
| 012 | Authentication strategy                                     | Accepted (Part 1 superseded for MLflow by 021) |

### V3 Architecture (May 2026, signed off 2026-05-05 before Phase 1a)

| #        | Title                                                       | Status   |
|----------|-------------------------------------------------------------|----------|
| 007 (v3) | [Repository layout — V3 autonomous project architecture](ADR-007-repository-layout-v3.md) | Accepted (supersedes 007) |
| 013      | [Per-project layered architecture](ADR-013-per-project-3-layer-architecture.md) | Accepted |
| 014      | [Project autonomy and templates](ADR-014-project-autonomy-and-templates.md) | Accepted |
| 015      | [Deployment service separation](ADR-015-deployment-service-separation.md) | Accepted |
| 016      | [Domain-level network topology](ADR-016-domain-level-network-topology.md) | Accepted (Amendment 1, 2026-09-23) |
| 017      | [Docker Compose file strategy and build context](ADR-017-docker-compose-file-strategy.md) | Accepted |
| 018      | [Development workflow and Git strategy](ADR-018-development-workflow-git-strategy.md) | Accepted |
| 019      | [Internet access and domain routing](ADR-019-internet-access-domain-routing.md) | Accepted |
| 020      | [Project readiness checklist and phase gates](ADR-020-project-readiness-checklist.md) | Accepted |

### Stage 2 — Operations (September 2026)

| #   | Title                                                       | Status   |
|-----|-------------------------------------------------------------|----------|
| 021 | MLflow is publicly browsable, read-only                     | Accepted |

## Decisions deferred to future stages

These were anticipated during Stage 2 but deliberately deferred. Each will be addressed in its own ADR when the relevant stage begins.

- **CI/CD specifics** — workflow structure, path filters, image promotion strategy. Stage 3.
- **TLS strategy** — HTTP-01 vs DNS-01 vs wildcard, automation mechanism. Stage 5.
- **AWS Secrets Manager integration** — how AWS-side credentials are managed and how secrets shared with the NAS are reconciled. Stage 4.
- **Per-demo database design** — separate databases vs. schemas in a shared Postgres, when a stateful demo first requires it.
- **Audit logging, rate limiting, OAuth, MFA** — deferred per ADR-012 until single-operator scope no longer holds.
- **Authorization (multi-user)** — deferred until a second user is added to the platform.

These are placeholders, not commitments. Each will be decided in its own time, with its own ADR.

## Related documentation

- **`docs/archive/`** — historical artifacts from each completed stage (deliberation memos, visual designs, intermediate drafts). Includes `original-adr-readme.md`, the predecessor of this file written at Stage 1 lock.
- Each ADR cross-references related ADRs in its "Related ADRs" section. Following those links surfaces the connections between decisions.

---

_Author: Archit Pandya_
_Last updated: 2026-09-25 (21 ADRs: Stage 1, Stage 2, V3 architecture, operations)_
