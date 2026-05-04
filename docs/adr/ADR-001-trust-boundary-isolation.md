# ADR-001: Networks isolate by trust boundary, not category

**Status:** Accepted
**Date:** April 2026
**Stage:** 1 (Conceptual Design)

## Context

pandyaHomeLab hosts four AI domains (ML, DL, NLP, Agentic AI), each with multiple sub-domains. The initial design instinct was to give every sub-domain its own isolated Docker network — eleven networks total — for "maximum isolation" between components.

This raised a question that needed an explicit answer: **what is a network boundary actually for?**

Two competing models emerged:

- **Per sub-domain (eleven networks):** maximum isolation. Each ML technique (classification, regression, clustering) lives on its own Docker network.
- **Per domain plus shared tiers (six networks):** isolation by function. ML, DL, NLP, Agentic each get one network. Shared services (proxy, data, mlops) get their own networks.

## Decision

**Networks isolate components that don't trust each other. Sub-domains under the same parent domain share the same trust level and therefore share a network.**

The final layout uses six logical Docker networks:

- `proxy-network` — reverse proxy and TLS termination (faces the internet)
- `data-network` — Postgres, MinIO, Redis (no internet egress)
- `mlops-network` — MLflow, Prometheus, Grafana (cross-domain observability)
- `ml-network` — all classical ML sub-domains
- `dl-network` — all deep learning sub-domains
- `nlp-network` — all NLP sub-domains
- `agentic-network` — all agentic AI sub-domains

Sub-domain identity is preserved at the **application layer** — through container names, FastAPI service hostnames, and URL paths — not at the network layer.

## Alternatives considered

**Per sub-domain (rejected).** Eleven networks is operationally heavy for a single-operator platform. Shared services like MLflow would either need to attach to all eleven networks (a Compose file from hell) or be duplicated eleven times (~33 GB of RAM consumed by infrastructure services that are doing the same job repeatedly). The isolation has no security payoff because all sub-domains under one domain share the same operator, the same data sources, and the same threat surface.

**One flat network (rejected).** No isolation at all. A compromise of any container would expose everything else, including the database. Violates the principle of defense in depth.

## Consequences

**Positive:**

- Network boundaries match real trust boundaries — a security compromise in `dl-network` cannot directly reach `data-network` or `proxy-network`.
- Shared services (MLflow, Postgres) attach to a small number of networks (3-4 each), keeping the Compose file readable.
- Operational footprint stays low: one MLflow, one Postgres, one MinIO instead of one per sub-domain.
- The model maps cleanly onto AWS — see ADR-002 for how the mirror works.

**Negative:**

- Sub-domains within a domain can communicate directly with each other without going through any explicit boundary. If `ml-classification` is ever compromised, `ml-regression` and `ml-clustering` are reachable. This is acceptable because they share an operator and data trust level, but it would not be acceptable in a multi-tenant SaaS context.
- If a sub-domain ever needs stronger isolation (e.g. a project handling sensitive data), it cannot be promoted to its own network without revisiting the Compose topology.

**Forecloses:**

- The "every project is its own walled garden" model is no longer available without architectural rework.

## Implementation reference

See `docs/stage-1/network-plan-v3.xlsx` for the complete CIDR allocation and multi-attach matrix.
