# ADR-007: Repository layout follows 3-tier multi-service shape

**Status:** Accepted
**Date:** April 2026
**Stage:** 2 (Synology Implementation)

## Context

Stage 1 locked the architecture but said nothing about how source code is organized. Stage 2 begins implementation and cannot proceed without a concrete answer to: **what does the pandyaHomeLab repository look like, folder by folder?**

A repository layout is not a filing system. It is a coordination contract that dictates what gets versioned together, how CI/CD pipelines wire up in Stage 3, and where the blast radius of a bad commit ends. Get the layout right and Stage 3 becomes a structural diff. Get it wrong and the platform spends Stage 3 refactoring folders while also debugging GitHub Actions.

Two questions had to be separated before this ADR could be written:

- **What shape does the layout take?** (this ADR)
- **How is that shape packaged into one or more Git repositories?** (deferred to ADR-008)

The shape question comes first because the same shape works under any packaging choice. If the shape is wrong, no packaging fixes it.

A second separation also became necessary mid-discussion: the layout described here is the **repository layout**, not the **runtime filesystem layout on the NAS**. Synology's Container Manager has its own conventions about where Docker projects live (`/volume1/docker/...`), and those conventions are a runtime concern, not a repository concern. Forcing the repository to match Synology's filesystem layout would tie the design to one platform — directly contradicting ADR-002, which establishes that the architecture must be platform-agnostic. The runtime layout is its own decision (ADR-009).

The platform itself, despite the "AI/ML" framing, is structurally a **3-tier multi-service web application**: a presentation tier (Nginx + static HTML), an application tier (FastAPI containers serving model demos), and a data tier (Postgres, MinIO, Redis). Cross-cutting observability (MLflow, Prometheus, Grafana) sits alongside, not inside, the tiers. The repository layout should make this shape visible.

The word "microservices" is deliberately avoided. pandyaHomeLab has *services* (plural, containerized, independently deployable) but does not have *microservices* in the architectural-pattern sense — there is no service mesh, no per-service database, no independent teams, no eventual consistency. "Multi-service" is the honest description.

## Decision

**The pandyaHomeLab repository is laid out to mirror the 3-tier multi-service deployment topology. Top-level folders correspond to tiers and cross-cutting concerns. The application tier mirrors the URL hierarchy (ADR-003) and naming convention (ADR-004) one-to-one.**

```
pandyahomelab/
│
├── platform/                          # Cross-cutting infrastructure
│   ├── proxy/                         # Presentation tier — Nginx
│   │   ├── nginx.conf
│   │   ├── conf.d/
│   │   └── Dockerfile
│   ├── data/                          # Data tier — Postgres, MinIO, Redis
│   │   ├── postgres/
│   │   ├── minio/
│   │   └── redis/
│   └── mlops/                         # Observability — MLflow, Prometheus, Grafana
│       ├── mlflow/
│       ├── prometheus/
│       └── grafana/
│
├── site/                              # Presentation tier — L1–L3 static HTML
│   ├── index.html                     # L1: pandyahomelab.com/
│   ├── ml/                            # L2: /ml/
│   │   ├── index.html
│   │   └── classification/index.html  # L3: /ml/classification/
│   ├── dl/
│   ├── nlp/
│   └── agentic/
│
├── services/                          # Application tier — L4 demos
│   ├── ml/
│   │   ├── classification/
│   │   │   └── iris-knn/              # /ml/classification/iris-knn
│   │   │       ├── app/               # FastAPI source
│   │   │       ├── Dockerfile         # Co-located
│   │   │       ├── requirements.txt
│   │   │       └── README.md
│   │   ├── regression/
│   │   └── clustering/
│   ├── dl/
│   ├── nlp/
│   └── agentic/
│
├── compose/                           # docker-compose orchestration
│   ├── docker-compose.platform.yml    # Always-running infrastructure
│   ├── docker-compose.yml             # Demos (independently up/down)
│   └── .env.example
│
├── docs/
│   ├── adr/                           # ADRs (Stage 1 + Stage 2 + ...)
│   ├── stage-1/
│   └── stage-2/
│
└── README.md
```

Three principles govern this layout, and any future change to it must be tested against all three:

1. **Network → folder mapping is 1:1.** Every Docker network defined in ADR-001 has a folder home. `proxy-network` lives under `platform/proxy/`. `data-network` lives under `platform/data/`. `mlops-network` lives under `platform/mlops/`. The four domain networks (`ml-network`, `dl-network`, `nlp-network`, `agentic-network`) live under `services/ml/`, `services/dl/`, `services/nlp/`, `services/agentic/`. Someone reading the folder tree can draw the network diagram.
2. **URL hierarchy → folder hierarchy is 1:1.** ADR-003's four URL levels map directly: L1 to `site/index.html`, L2 to `site/ml/index.html`, L3 to `site/ml/classification/index.html`, L4 to `services/ml/classification/iris-knn/`. ADR-004's `dataset-algorithm` naming propagates from URL to folder name without translation.
3. **Layout is platform-agnostic.** Nothing in the tree mentions Synology, AWS, `/volume1/`, or `docker/`. The same repository works identically on Synology (deployed via docker-compose), on AWS (deployed via Terraform + ECS), or on a developer laptop. ADR-002's mirror principle extends from networks to filesystem.

Three subordinate decisions follow from the same principles:

- **Per-service Dockerfiles are co-located** with the demo source. `services/ml/classification/iris-knn/Dockerfile` sits next to `app/`. Demos are deliberately heterogeneous (different Python dependencies, different model serving libraries, different ports), so DRY across Dockerfiles is not a goal.
- **Compose files are split into platform and demos.** `docker-compose.platform.yml` holds the always-running infrastructure (Nginx, Postgres, MinIO, Redis, MLflow, Prometheus, Grafana). `docker-compose.yml` holds the demo services. The split prevents an accidental `docker compose down` aimed at a demo from taking out the platform alongside it. This mirrors the same trust-boundary thinking as ADR-001: platform services and workloads have different change frequencies and different blast radii.
- **`compose/` is its own folder, not at the repository root.** This keeps the root scannable for documentation (README, docs/) and keeps deployment artifacts grouped together. Future deployment artifacts for AWS (`terraform/`, `aws/`) sit alongside `compose/` at the same level — both are different *implementations* of the same logical layout.

## Alternatives considered

**Layout shaped by Synology conventions (rejected).** The instinct to mirror Synology's `/volume1/docker/<project>/` convention in the repository is intuitive but contaminates the repository with a platform-specific shape. On AWS, where there is no Container Manager and no `docker/` folder, that shape no longer reflects the deployment. ADR-002 establishes platform-agnosticism as a core principle; this rejection is a direct application. The runtime mapping to Synology's filesystem is handled by ADR-009 separately.

**Layout shaped purely by language conventions (rejected).** A standard Python project layout (`src/`, `tests/`, `setup.py`) treats the entire repository as one Python package. pandyaHomeLab is not one Python package — it is multiple independently deployable services plus infrastructure plus static site content. Forcing the platform into Python-package shape would mean infrastructure and static HTML have nowhere natural to live.

**Centralized Dockerfile directory (rejected).** Placing all Dockerfiles in a top-level `dockerfiles/` directory is useful when many services share an identical Dockerfile that benefits from deduplication. pandyaHomeLab demos are deliberately different — different model libraries, different serving patterns. The deduplication benefit doesn't apply, and the indirection (Dockerfile in one place, source code in another) raises the cost of adding a new demo.

**Single combined `docker-compose.yml` (rejected).** One compose file is simpler to type and read. It is also more dangerous: a `docker compose down` aimed at a misbehaving demo brings down the platform with it. Separating platform from demos costs one extra `-f` flag at compose time and removes an entire class of operator mistakes.

**Demos grouped by algorithm rather than technique family (rejected).** A layout like `services/ml/knn/iris/` (algorithm-first) was considered but rejected for the same reason ADR-004 rejected algorithm-first naming: technique families are the stable organizing principle, algorithms are interchangeable within them. Grouping by technique family keeps the folder structure aligned with how users navigate the site (ADR-003) and how data scientists think about problems.

## Consequences

**Positive:**

- The repository is self-documenting. The folder tree, read from top, communicates the architecture without supporting prose. Network names from ADR-001, URL paths from ADR-003, and demo names from ADR-004 are all visible in the tree.
- Adding a new demo is mechanical: create `services/<domain>/<technique>/<dataset>-<algorithm>/`, drop in `app/`, `Dockerfile`, `requirements.txt`, register the service in `docker-compose.yml`, add a route to Nginx. No naming debates, no structural decisions.
- The layout works under any repository packaging (monorepo, hybrid, polyrepo). ADR-008 can choose the packaging without invalidating this layout.
- The layout works on any deployment platform. Synology Compose, AWS ECS, or a laptop all consume the same source — only the deployment artifacts (`compose/`, future `terraform/`) differ.
- Greppability is high. Every demo name appears in exactly the predictable places: its source folder, its compose service name, its Nginx config block, its container name in `docker ps`. Tracing a demo through logs and configs requires no translation.

**Negative:**

- The folder tree is wide near the root (six top-level entries: `platform/`, `site/`, `services/`, `compose/`, `docs/`, `README.md`) and shallow elsewhere. New contributors (including future-self after a long absence) must understand that `platform/` and `services/` are the heavy folders and the rest are light. Mitigated by README and the principles above.
- The 1:1 network-to-folder mapping is a constraint that future ADRs must respect. If a future decision adds a new logical network, it must also add a folder; if it removes one, the folder must be archived. This is acceptable because it is the same discipline already required for the network plan itself.
- The split compose files require slightly longer commands at deployment time (`docker compose -f compose/docker-compose.platform.yml -f compose/docker-compose.yml up`). For a single operator on a single NAS this is a non-issue; for an interactive bring-up workflow it would warrant a wrapper script. Stage 2 may add `make` targets or a shell helper to absorb this.
- Co-located Dockerfiles mean that improvements to a "good" Dockerfile pattern do not automatically propagate to all demos. Each demo's Dockerfile is independently maintained. Mitigated by treating the first stable demo's Dockerfile as a template for new demos and documenting it in the repository's contribution guide.

**Forecloses:**

- A flat repository structure (everything at the root) is foreclosed. New components must find a home under one of the existing top-level folders or motivate adding a new top-level folder via a future ADR.
- A purely language-convention layout (treating the repository as one Python package) is foreclosed. The repository is multi-component by design.
- Tying the repository structure to any single deployment platform is foreclosed. This is enforced by the platform-agnosticism principle above.

## Implementation reference

This ADR governs Stage 2 implementation. Stage 2 work begins by scaffolding the empty folder tree, then populating in this order:

1. `platform/proxy/` — Nginx container with TLS-ready config
2. `platform/data/` — Postgres, MinIO, Redis
3. `platform/mlops/` — MLflow first; Prometheus and Grafana follow
4. `site/index.html` and one domain landing page (e.g., `site/ml/index.html`)
5. `services/ml/classification/iris-knn/` — first end-to-end demo
6. `compose/docker-compose.platform.yml` and `compose/docker-compose.yml`

The Stage 2 definition of done — one ML demo reachable at production URL, tracked by MLflow, artifacts in MinIO, all running through custom Nginx with TLS — is achievable from this layout once steps 1–6 are complete.

## Related ADRs

- **ADR-001** — establishes the network topology this layout mirrors
- **ADR-002** — establishes platform-agnosticism, applied here to filesystem
- **ADR-003** — establishes the URL hierarchy this layout mirrors
- **ADR-004** — establishes the demo naming convention this layout uses
- **ADR-008** (queued) — repository packaging (mono / hybrid / poly), built on this layout
- **ADR-009** (queued) — runtime filesystem layout on Synology, separated from this ADR
- **ADR-010** (queued) — Synology secrets management
