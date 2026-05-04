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

## Stage 1 ADRs

| #   | Title                                                       | Status   |
|-----|-------------------------------------------------------------|----------|
| 001 | Networks isolate by trust boundary, not category            | Accepted |
| 002 | Synology and AWS layouts mirror 1:1 with AZ divergence      | Accepted |
| 003 | URL hierarchy uses four-level progressive disclosure        | Accepted |
| 004 | Level 4 demos named with dataset-algorithm convention       | Accepted |
| 005 | Path-based routing for Stage 1, subdomain hybrid deferred   | Accepted |
| 006 | Custom Nginx replaces DSM reverse proxy on host ports       | Accepted |

## Future stages

Stage 2 onward will add ADRs as new decisions are made. Anticipated future ADRs include:
- Container orchestration (Compose vs Swarm vs K3s)
- Secrets management (env files vs Vault vs cloud secrets)
- TLS strategy (HTTP-01 vs DNS-01 vs wildcard)
- Observability stack composition
- Model artifact storage (MinIO vs S3 vs both)

These are placeholders, not commitments. Each will be decided in its own time, with its own ADR.

---

_Author: Archit Pandya_
_Last updated: April 2026 (Stage 1 lock)_
