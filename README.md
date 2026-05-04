# pandyaHomeLab

**A personal AI/ML portfolio platform** demonstrating Machine Learning, Deep Learning, Natural Language Processing, and Agentic AI techniques — built on a Synology NAS with cloud-mirrored deployment to AWS, all designed and documented as production-grade infrastructure.

Live at: **[pandyahomelab.com](https://pandyahomelab.com)** _(NAS-served, primary)_ and **[aws.pandyahomelab.com](https://aws.pandyahomelab.com)** _(AWS-served, minimal serving subset)_

---

## What this is

pandyaHomeLab is the platform behind the live site. It hosts hands-on demos across four AI domains, each accessible through a structured URL hierarchy:

- `/ml/` — Machine Learning (classification, regression, clustering)
- `/dl/` — Deep Learning (CNNs, RNNs, transformers)
- `/nlp/` — Natural Language Processing
- `/agentic/` — Agentic AI

The platform itself — its network topology, service layout, deployment model, and operational discipline — is **the portfolio artifact**. The live site is what audiences interact with; this repository is the source of truth for how it works.

## Repository layout

```
pandya-homelab/
├── platform/                  # Platform services (proxy, data, mlops)
│   ├── proxy/                 # Nginx reverse proxy + TLS termination
│   ├── data/                  # Postgres, MinIO, Redis
│   └── mlops/                 # MLflow, Grafana, Prometheus, Loki
├── site/                      # Static L1-L3 content (apex landing + domain pages)
│   ├── apex/
│   ├── ml/, dl/, nlp/, agentic/
├── services/                  # Per-domain demos (L4 endpoints)
│   ├── ml/, dl/, nlp/, agentic/
├── compose/                   # Docker Compose files (platform + demos, dev-nas + prod-nas)
└── docs/
    ├── adr/                   # Active architecture decision records
    └── archive/               # Historical artifacts (deliberation memos, designs)
```

The layout is established by **[ADR-007](docs/adr/ADR-007-repository-layout.md)**. Each top-level folder corresponds to a logical tier of the architecture.

## Architecture decisions

All significant architectural decisions are recorded as **ADRs** in `docs/adr/`. Start with **[docs/adr/README.md](docs/adr/README.md)** for an overview.

The current platform is built on twelve accepted ADRs covering:

**Stage 1 — Conceptual Design** (ADRs 001–006)
- Network isolation by trust boundary
- AWS / Synology mirror principle
- URL hierarchy (four-level progressive disclosure)
- Demo naming convention
- Path-based routing strategy
- Custom Nginx replacing DSM proxy

**Stage 2 — Synology Implementation** (ADRs 007–012)
- Repository layout (this structure)
- Repository packaging (single monorepo)
- Runtime filesystem and permissions
- Secrets management
- Per-service conventions (the platform contract)
- Authentication strategy

## Deliberation history

The reasoning that produced each ADR is preserved in **`docs/archive/stages/`**, organized by stage. This includes:

- Working memos from each stage
- Visual designs and infographics
- Network planning iterations (XLSX versions)
- Architectural diagrams (cross-platform deployment, source flow)
- Stage-closure summaries

Future stages will accumulate similar archives as their deliberation completes.

## Working environment

Development happens directly on the NAS via VS Code Remote-SSH (Mode B-prime per the Stage 2 Working Environment memo). Two stacks coexist:

- **`dev-nas`** — feature branches, eager rebuilds, LAN-only on alternate ports
- **`prod-nas`** — main branch only, explicit rebuilds, public traffic on standard ports

A future **`prod-aws`** stack mirrors a stateless serving subset on AWS for cloud-architecture demonstration.

## Stages roadmap

| Stage | Focus | Status |
|-------|-------|--------|
| 1 | Conceptual architecture and design | Complete (April 2026) |
| 2 | Synology implementation | Complete — implementation begins May 2026 |
| 3 | CI/CD pipelines | Future |
| 4 | AWS deployment | Future |
| 5 | TLS automation, observability hardening | Future |

## License and contributing

This is a personal portfolio platform. The architecture, decisions, and code are open for reference and learning. Contributions are not expected at this stage — single-operator scope is part of the architectural premise.

---

**Author:** Archit Pandya
**Brand:** pandyaHomeLab
**Last updated:** May 2026 (Stage 2 lock — twelve ADRs accepted, implementation underway)
