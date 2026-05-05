---
title: Repository layout — V3 autonomous project architecture
status: Proposed (replaces ADR-007)
context: |
  Stage 2 locked a flat repository structure (platform/, site/, services/, compose/, docs/).
  This worked for initial scaffolding but doesn't reflect how projects should be organized:
  each ML/DL project as an independent, professionally-layered unit.
  
  V3 redesign moves from service-oriented to project-autonomous architecture.
decision: |
  Repository root layout follows this 10-folder structure:
  
  ml/              — Machine Learning projects (each project = standalone unit, 3-layer internally)
  dl/              — Deep Learning projects (same pattern)
  nlp/             — Natural Language Processing projects (same pattern)
  agentic/         — Agentic AI projects (same pattern)
  shared/          — Cross-project utilities, datasets, scripts, configs
  deployment/      — Docker Compose, Nginx, environment overrides (dev/staging/prod)
  infra/           — Infrastructure-as-Code (Terraform), CI/CD workflows
  website/         — pandyahomelab.com landing page and static assets
  docs/            — ADRs, runbooks, architecture diagrams
  experiments/     — NAS-only development notebooks (not containerized)
  
  Each project folder (e.g., ml/ml-iris-knn/, ml/ml-linear-regression/) is fully self-contained:
  it houses its own 3-layer architecture, tests, configs, Dockerfile, and Makefile.
  
  Root-level files: README.md, .gitignore, Makefile (top-level tasks), CHANGELOG.md
alternatives_considered: |
  A. Keep Stage 2 flat structure (platform/, services/, compose/) — rejected because:
     - Doesn't highlight project autonomy
     - Hides individual project architecture from portfolio viewers
     - Doesn't scale well with 10+ projects
  
  B. Use services/ subfolder per domain (services/ml/iris-knn/) — rejected because:
     - Still buries projects one level too deep
     - "services" implies API microservices, not self-contained projects
     - Doesn't make internal 3-layer structure obvious
  
  C. V3 autonomous layout (ml/, dl/ at root) — CHOSEN because:
     - Projects are first-class citizens in the repository
     - Portfolio viewers immediately see "ML platform with independent projects"
     - Clear separation: orchestration (deployment/) vs. projects (ml/, dl/)
     - Enables templates (ml/_templates/, dl/_templates/) for consistency
consequences: |
  Positive:
  - Each project is a complete portfolio piece (GitHub viewers see full architecture)
  - Projects are independently deployable and testable
  - Template scaffolding ensures consistency across projects
  - Clear boundaries between infrastructure (deployment/), projects (ml/dl/), and shared code
  - Easier to add new projects without refactoring root structure
  - Mirrors industry patterns (monorepo with independent project directories)
  
  Negative:
  - One-time refactor of existing Stage 2 structure (low cost, zero code changes)
  - Developers must learn new internal 3-layer pattern per project (mitigated by templates)
  - More folders at root level (acceptable trade-off for clarity)
  
  Deferred decisions:
  - How to handle cross-project dependency management (Stage 3 CI/CD concern)
  - Multi-project artifact versioning and promotion (Stage 4 concern)
related_adrs: |
  - ADR-007 (this document) — repository layout
  - ADR-013 — per-project 3-layer architecture (new)
  - ADR-014 — project autonomy and templates (new)
  - ADR-015 — deployment service separation (new)
---

# ADR-007 (Revised) — Repository Layout — V3 Autonomous Project Architecture

**Status:** Proposed (supersedes previous ADR-007)  
**Date:** May 2026  
**Author:** Archit Pandya

## Context

Stage 2 ADR-007 established a flat repository structure optimized for rapid scaffolding:
```
platform/    (proxy, data, mlops)
site/        (landing page)
services/    (project placeholders)
compose/     (orchestration)
docs/        (documentation)
```

This structure was appropriate for the architectural baseline phase. However, it doesn't reflect the desired portfolio presentation: **each ML/DL project should be a self-contained, professionally-architected unit visible at the repository root.**

The current structure hides project completeness. When a portfolio viewer opens GitHub, they see "platform" and "services" folders — implementation details, not achievements.

## Decision

Adopt **V3 autonomous project architecture** with this root layout:

```
ml/              📁 Machine Learning projects (each project self-contained, 3-layer internal structure)
dl/              📁 Deep Learning projects (same pattern)
nlp/             📁 Natural Language Processing projects (same pattern)
agentic/         📁 Agentic AI projects (same pattern)
shared/          📁 Cross-project utilities, datasets, configs, tests
deployment/      📁 Docker Compose, Nginx, environment configs (dev/staging/prod)
infra/           📁 Infrastructure-as-Code, Terraform, CI/CD workflows
website/         📁 pandyahomelab.com landing page and static assets
docs/            📁 ADRs, runbooks, architecture documentation
experiments/     📁 NAS-only development notebooks (outside containers)

README.md        📄 Root documentation
.gitignore       📄 Git ignore patterns
Makefile         📄 Top-level build and deployment tasks
CHANGELOG.md     📄 Release notes
docker-compose.yml  📄 Main orchestration (in root or deployment/)
.env.example     📄 Template secrets
```

### Each Project is Self-Contained

A project folder like `ml/ml-iris-knn/` contains everything needed for that project:

```
ml/ml-iris-knn/
├── presentation-logic/    (API, routes, schemas, middleware)
├── application-logic/     (ML logic, trainers, predictors)
├── db-logic/             (loaders, transforms, repository)
├── shared/               (config, logger, metrics, utils)
├── notebooks/            (development, not containerized)
├── tests/                (presentation/, application/, db/)
├── data/                 (gitignored, on NAS + S3)
├── models/               (gitignored, S3 only)
├── configs/              (YAML: model.yaml, api.yaml, logging.yaml)
├── docker/               (Dockerfile, entrypoint.sh)
├── pyproject.toml        (Python dependencies)
├── Makefile              (project-level tasks)
├── README.md             (project documentation)
└── .env.example          (project secrets template)
```

## Alternatives Considered

### A. Keep Stage 2 Flat Structure
```
platform/
services/ml/classification/iris-knn/
```
**Rejected** — Projects buried, portfolio narrative weak, scales poorly.

### B. Service-Oriented (services/ml/)
```
services/ml/iris-knn/
services/dl/lstm-forecast/
```
**Rejected** — Still nested one level too deep, "services" implies API microservices not projects.

### C. V3 Autonomous (ml/, dl/, nlp/, agentic/ at root) ✅ CHOSEN
```
ml/ml-iris-knn/
dl/dl-lstm-forecast/
nlp/nlp-sentiment-classifier/
agentic/agentic-task-orchestrator/
```
**Chosen** — All four AI domains are first-class portfolio pieces, templates enable consistency across all domains.

## Consequences

### Positive
- **Portfolio strength** — GitHub viewers see independent, professionally-layered projects
- **Autonomy** — Each project independently deployable, testable, reviewable
- **Scalability** — Adding 10+ projects doesn't require root restructuring
- **Templates** — `ml/_templates/`, `dl/_templates/`, `nlp/_templates/`, `agentic/_templates/` ensure consistency across all domains (see ADR-014)
- **Industry standard** — Mirrors successful monorepo patterns (Uber, Airbnb)
- **Clear separation** — Infrastructure (deployment/), projects (ml/dl/), shared code (shared/)

### Negative
- **One-time refactor** — Stage 2 structure → V3 (zero code impact, pure folder moves)
- **Learning curve** — Teams must adopt 3-layer pattern per project (mitigated by templates + ADR-013)
- **More root folders** — 8 folders instead of 4 (acceptable for clarity)

### Deferred
- **Cross-project dependencies** — How to version/promote shared code across projects (Stage 3 CI/CD)
- **Artifact management** — Multi-project model versioning and A/B deployment (Stage 4)

## Related ADRs

- **ADR-013** (new) — Per-project 3-layer architecture (applies to ml/, dl/, nlp/, agentic/ equally)
- **ADR-014** (new) — Project autonomy and templates (four domain templates)
- **ADR-015** (new) — Deployment service separation
- **ADR-008** — Repository packaging (still single monorepo, unchanged)
- **ADR-010** — Secrets management (per-project .env.example files across all domains)

---

**Revision Note:** This ADR supersedes the original ADR-007 (Stage 2). The monorepo decision (ADR-008) remains unchanged; only the internal layout is redesigned for project autonomy.
