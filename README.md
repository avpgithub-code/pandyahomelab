# pandyaHomeLab

**A personal AI/ML portfolio platform** demonstrating Machine Learning, Deep Learning, Natural Language Processing, and Agentic AI techniques — built on a Synology NAS, designed so it can later be mirrored to AWS, and documented as production-grade infrastructure.

Live at: **[pandyahomelab.com](https://pandyahomelab.com)** _(served from the NAS through a Cloudflare Tunnel)_. An AWS mirror is planned for Phase 6 and is not live yet.

---

## What this is

pandyaHomeLab is the platform behind the live site. It hosts hands-on demos across four AI domains, each accessible through a structured URL hierarchy:

- `/ml/` — Machine Learning (classification, regression, AutoML)
- `/dl/` — Deep Learning (CNN image classification, LSTM forecasting)
- `/nlp/` — Natural Language Processing (classical NLP: engineered features, text representations, word embeddings)
- `/agentic/` — Agentic AI (planned)

The platform itself — its network topology, service layout, deployment model, and operational discipline — is **the portfolio artifact**. The live site is what audiences interact with; this repository is the source of truth for how it works.

## Live demos

| Domain | Demo | Route | What it shows |
|---|---|---|---|
| ML | ml-iris-knn | `/ml/iris-knn/` | K-nearest neighbours, multi-class classification |
| ML | ml-housing-linear | `/ml/housing-linear/` | Linear regression on California housing |
| ML | ml-titanic-automl | `/ml/titanic-automl/` | PyCaret AutoML on imbalanced data |
| DL | dl-mnist-cnn | `/dl/mnist-cnn/` | PyTorch CNN, draw-a-digit UI |
| DL | dl-lstm-forecast | `/dl/lstm-forecast/` | LSTM 14-day bike-share forecast with an uncertainty band |
| NLP | nlp-quora-randomforest | `/nlp/quora-randomforest/` | Duplicate question pairs: 22 engineered features + bag-of-words → Random Forest |
| NLP | nlp-imdb-textrep | `/nlp/imdb-textrep/` | Preprocessing, stems vs lemmas, one-hot / BoW / n-grams / TF-IDF compared on IMDB |
| NLP | nlp-text8-word2vec | `/nlp/text8-word2vec/` | Word2Vec CBOW vs skip-gram vs fastText, with GloVe as reference |

Every training run is logged to its domain's MLflow tracker, each publicly browsable and read-only:
[`/mlflow/`](https://pandyahomelab.com/mlflow/) (ML), [`mlflow-dl`](https://mlflow-dl.pandyahomelab.com/) (DL)
and [`mlflow-nlp`](https://mlflow-nlp.pandyahomelab.com/) (NLP).

## Repository layout

```
pandya-homelab/
├── ml/                        # Machine Learning demos, one self-contained project each
│   ├── ml-iris-knn/  ml-housing-linear/  ml-titanic-automl/
│   ├── admin-portal/  analytics-ingester/   # platform services (feedback admin, analytics)
│   └── _templates/            # ML project template
├── dl/                        # Deep Learning demos: dl-mnist-cnn/  dl-lstm-forecast/
├── nlp/                       # NLP demos: nlp-quora-randomforest/  nlp-imdb-textrep/  nlp-text8-word2vec/
│   └── _templates/            # NLP project template + new-nlp-project.sh scaffold script
├── deployment/                # Docker Compose per domain (ml/, dl/, nlp/), nginx/, cloudflared/
├── website/                   # Live landing page + platform About content (served by Nginx)
├── site/                      # Unserved copy of the landing page for the planned static-site layout
├── services/                  # Legacy Stage 2 placeholders (empty)
├── backups/                   # Backup notes (image backups live outside git)
└── docs/
    ├── adr/                   # Architecture decision records
    ├── archive/               # Historical artifacts (deliberation memos, designs)
    └── *.md                   # Phase plans, NETWORK_CIDR_SUMMARY, DEVELOPMENT_RUNBOOK, walkthroughs
```

Every demo folder follows the same four-layer structure (`presentation-logic/`, `application-logic/`,
`db-logic/`, `shared/`, per ADR-013) with its own Dockerfile, tests and README. The layout is
established by **[ADR-007 (v3)](docs/adr/ADR-007-repository-layout-v3.md)**, which replaced the
Stage 2 layout in [ADR-007](docs/adr/ADR-007-repository-layout.md).

## Architecture decisions

All significant architectural decisions are recorded as **ADRs** in `docs/adr/`. Start with **[docs/adr/README.md](docs/adr/README.md)** for an overview.

The current platform is built on **21 ADRs** (ADR-007 has a v3 revision that supersedes the original):

**Stage 1 — Conceptual Design** (ADRs 001–006)
- Network isolation by trust boundary
- AWS / Synology mirror principle
- URL hierarchy (four-level progressive disclosure)
- Demo naming convention
- Path-based routing strategy
- Custom Nginx replacing DSM proxy

**Stage 2 — Synology Implementation** (ADRs 007–012)
- Repository layout (original; superseded by ADR-007 v3)
- Repository packaging (single monorepo)
- Runtime filesystem and permissions
- Secrets management
- Per-service conventions (the platform contract)
- Authentication strategy

**V3 Architecture** (ADR-007 v3, ADRs 013–020; signed off 2026-05-05)
- Domain-autonomous repository layout
- Per-project layered architecture and project templates
- Deployment separated from project code; Docker Compose file strategy
- Domain-level network topology (per-domain networks, IP and port allocation)
- Development workflow and Git strategy
- Internet access and domain routing
- Project readiness checklist and phase gates

**Operations** (ADR-021)
- MLflow is publicly browsable, read-only

## Deliberation history

The reasoning that produced each ADR is preserved in **`docs/archive/stages/`**, organized by stage. This includes:

- Working memos from each stage
- Visual designs and infographics
- Network planning iterations (XLSX versions)
- Architectural diagrams (cross-platform deployment, source flow)
- Stage-closure summaries

Future stages will accumulate similar archives as their deliberation completes.

## Working environment

Development happens directly on the NAS via VS Code Remote-SSH. There is one NAS stack:

- **Per domain,** `deployment/<domain>/docker-compose.yml` runs the shared infrastructure (for NLP, only the
  MLflow tracker) and `docker-compose.dev.yml` adds that domain's demo containers.
- **Nginx and the Cloudflare Tunnel** run from `deployment/nginx/`. Public traffic reaches the NAS only
  through the tunnel; demo host ports bind to `127.0.0.1`.
- **Each sub-phase** is built on its own branch, merged into `main` with `--no-ff`, and tagged
  `v.<project>-1.0.0` when it ships. Day-to-day commands and known pitfalls are in
  [docs/DEVELOPMENT_RUNBOOK.md](docs/DEVELOPMENT_RUNBOOK.md); every address and port is in
  [docs/NETWORK_CIDR_SUMMARY.md](docs/NETWORK_CIDR_SUMMARY.md).

A **`prod-aws`** stack that mirrors a serving subset on AWS is planned for Phase 6.

## Roadmap

Demos are built in phases, one domain at a time:

| Phase | Domain | Status |
|-------|--------|--------|
| 1 | Machine Learning | Complete: 3 demos + MLflow (May 2026) |
| 2 | Deep Learning | 2 of 3 live (May 2026); object detection not started |
| 3 | Natural Language Processing | 3 of 4 live (September 2026); HMM part-of-speech tagger next |
| 4 | Agentic AI | Planned |
| 6 | AWS mirror | Planned |

Platform stages:

| Stage | Focus | Status |
|-------|-------|--------|
| 1 | Conceptual architecture and design | Complete (April 2026) |
| 2 | Synology implementation | Complete (May 2026) |
| 3 | CI/CD pipelines | Future |
| 4 | AWS deployment | Future |
| 5 | TLS automation, observability hardening | Future |

## License and contributing

This is a personal portfolio platform. The architecture, decisions, and code are open for reference and learning. Contributions are not expected at this stage — single-operator scope is part of the architectural premise.

---

**Author:** Archit Pandya
**Brand:** pandyaHomeLab
**Last updated:** 2026-09-25 (8 live demos across ML, DL and NLP; 21 ADRs)
