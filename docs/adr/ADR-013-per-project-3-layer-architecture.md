---
title: Per-project 3-layer architecture — enforced internal structure for all projects
status: Proposed (new)
context: |
  ADR-007 (V3 revision) establishes ml/ and dl/ folders as autonomous project containers.
  However, "autonomous" must be defined concretely: what does an ideal project look like internally?
  
  Without a prescribed internal structure, projects risk inconsistency: one project with
  clear separation of concerns, another with monolithic code, a third with hidden coupling.
  
  V3 success depends on every project following the same clean architecture pattern.
decision: |
  Every project across all four domains (ml/, dl/, nlp/, agentic/) MUST implement this 3-layer pattern:
  
  Examples:
  - ml/ml-iris-knn/
  - dl/dl-lstm-forecast/
  - nlp/nlp-sentiment-classifier/
  - agentic/agentic-task-orchestrator/
  
  1. PRESENTATION-LOGIC (green layer)
     - HTTP API, routes, request/response schemas, middleware
     - Calls application-logic ONLY; never touches db-logic directly
     - Folder: presentation-logic/api/, presentation-logic/errors/
  
  2. APPLICATION-LOGIC (blue layer)
     - Pure ML/DL logic: model architecture, trainers, predictors, pipelines
     - Business logic, no database awareness, no HTTP awareness
     - Calls db-logic ONLY for data access
     - Folder: application-logic/model/, application-logic/pipeline/, application-logic/services/
  
  3. DB-LOGIC (orange layer)
     - Data abstraction: loaders (local/S3/Postgres), transforms, repository pattern
     - Handles all I/O (disk, S3, databases)
     - Called by application-logic only
     - Folder: db-logic/loaders/, db-logic/transforms/, db-logic/repository/
  
  4. SHARED (red layer, cross-cutting)
     - Config, logging, metrics, constants, exceptions, utility functions
     - Used by all three layers; contains NO business logic
     - Folder: shared/
  
  Rationale: This pattern enforces clean architecture and makes every project immediately understandable.
  A portfolio reviewer can immediately map "how data flows" through any project.
alternatives_considered: |
  A. No prescribed structure — rejected because projects become inconsistent (hard to review, scale)
  B. Hexagonal/ports-adapters pattern — too heavy for individual projects at this stage
  C. 3-layer pattern (presentation/application/db) — CHOSEN because:
     - Simple to understand and implement
     - Widely recognized (Django, Spring, ASP.NET patterns)
     - Enforces testability (layers can be tested in isolation)
     - Makes data flow explicit
     - Portfolio viewers immediately understand architecture
consequences: |
  Positive:
  - Every project is immediately readable (data flow is obvious)
  - Testability enforced (layers are independently testable)
  - Consistency across projects (aids portfolio narrative)
  - Scales: 20 projects all follow the same blueprint
  - Coupling is visible (violations are obvious)
  - Refactoring is safer (layer boundaries are clear)
  
  Negative:
  - Adds initial boilerplate per project (~20 files in initial scaffold)
  - Developers must learn the pattern (mitigated by templates)
  - Some projects might feel over-structured initially (e.g., tiny demos)
  
  Mitigations:
  - ADR-014 (templates) provides scaffolding to reduce boilerplate
  - README.md in each project explains the layers
  - Makefile targets help enforce layer boundaries during development
related_adrs: |
  - ADR-007 (V3 revision) — repository layout (projects must follow this internally)
  - ADR-014 — project autonomy and templates (provides scaffolds)
  - ADR-011 — per-service conventions (applies to each layer)
---

# ADR-013 — Per-Project 3-Layer Architecture

**Status:** Proposed (new)  
**Date:** May 2026  
**Author:** Archit Pandya

## Context

ADR-007 (V3 revision) establishes that each project across all four AI domains (ML, DL, NLP, Agentic AI) is a self-contained unit. But "self-contained" without structure leads to chaos: one project might have tight coupling between API and model logic, another might bury data loading in presentation routes.

A portfolio viewer (potential employer, collaborator) needs consistency to evaluate your architecture skills. "Did this person understand clean architecture principles?"

**Without a prescribed internal structure, projects are individually weak.**

## Decision

Every project MUST follow this explicit 3-layer + shared pattern:

### Layer 1: PRESENTATION-LOGIC (Green)
HTTP API layer. Handles requests, responses, validation, error serialization.

```
presentation-logic/
├── api/
│   ├── main.py           (FastAPI app initialization)
│   ├── routes.py         (endpoint definitions)
│   ├── schemas.py        (Pydantic models for validation)
│   ├── middleware.py     (request/response handling)
│   └── dependencies.py   (dependency injection)
└── errors/
    └── handlers.py       (HTTP error handlers)
```

**Invariant:** Calls `application-logic` only. Never touches `db-logic` directly.

### Layer 2: APPLICATION-LOGIC (Blue)
Pure ML/DL logic. Model architecture, training, inference, pipelines.

```
application-logic/
├── model/
│   ├── architecture.py   (model definition)
│   ├── trainer.py        (training logic)
│   └── predictor.py      (inference)
├── pipeline/
│   ├── training_pipeline.py
│   └── inference_pipeline.py
└── services/
    ├── training_service.py
    └── prediction_service.py
```

**Invariant:** No HTTP awareness, no direct database access. Calls `db-logic` to fetch/store data.

### Layer 3: DB-LOGIC (Orange)
Data abstraction. Loaders (local/S3/Postgres), transforms, repository pattern.

```
db-logic/
├── loaders/
│   ├── local_loader.py   (load from NAS disk)
│   ├── s3_loader.py      (load from AWS S3)
│   └── db_loader.py      (load from Postgres)
├── transforms/
│   ├── preprocessor.py
│   ├── augmentor.py
│   └── scaler.py
└── repository/
    ├── base_repository.py
    ├── model_repository.py
    └── prediction_repository.py
```

**Invariant:** Called by `application-logic` only. Abstracts all I/O.

### Layer 4: SHARED (Red, Cross-Cutting)
Utilities, config, logging, metrics. NO business logic.

```
shared/
├── config.py        (environment config loading)
├── logger.py        (logging setup)
├── metrics.py       (performance metrics)
├── constants.py     (project-wide constants)
├── exceptions.py    (custom exception classes)
└── utils.py         (helper functions)
```

**Invariant:** Used by all layers. Contains zero business logic.

### Supporting Folders
```
notebooks/          (development notebooks, gitignored, dev-only)
tests/
  ├── presentation/  (test presentation layer)
  ├── application/   (test application logic)
  └── db/            (test db access)
data/               (gitignored, raw/processed splits)
models/             (gitignored, checkpoints/artifacts)
configs/            (YAML: model.yaml, api.yaml, logging.yaml)
docker/             (Dockerfile, entrypoint.sh, .dockerignore)
```

## Data Flow Example: Iris-KNN Prediction Request

```
1. HTTP POST /predict {"features": [5.1, 3.5, 1.4, 0.2]}
   ↓ (presentation-logic/api/routes.py receives, validates with schemas.py)
   
2. prediction_service = PredictionService()
   ↓ (application-logic/services/prediction_service.py instantiates)
   
3. predictor.predict(features)
   ↓ (application-logic/model/predictor.py calls db-logic for data context)
   
4. repository.get_training_stats()
   ↓ (db-logic/repository/prediction_repository.py fetches from db-logic/loaders/)
   
5. loader.load_from_s3("iris-knn/training-stats")
   ↓ (db-logic/loaders/s3_loader.py fetches from S3)
   
6. [data returned through layers, prediction computed, response formatted]
   ↓
   
7. HTTP 200 {"prediction": "setosa", "confidence": 0.92}
   
Each layer is independent; violations are immediately obvious.
```

## Alternatives Considered

### A. No Prescribed Structure
**Rejected** — Projects become inconsistent; portfolio narrative breaks.

### B. Hexagonal Architecture (Ports & Adapters)
**Rejected** — Overkill for individual projects at this stage; adds complexity without proportional benefit.

### C. 3-Layer Pattern (Presentation / Application / DB)
**Chosen** — Simple, proven, widely recognized, scales well, enforces testability.

## Consequences

### Positive
- **Immediate readability** — Data flow is obvious from folder structure
- **Portfolio strength** — Every project demonstrates clean architecture understanding
- **Testability** — Layers test independently; no coupling surprises
- **Scalability** — Pattern works for 20 projects as well as 2
- **Onboarding** — New developers instantly understand project structure
- **Refactoring safety** — Layer violations are caught early

### Negative
- **Initial boilerplate** — ~20 files to scaffold per project
- **Learning curve** — Developers must internalize the pattern
- **Overhead for tiny projects** — E.g., "hello world" models might feel over-structured

### Mitigations
- ADR-014 (templates) provides auto-generated scaffolds
- README.md explains layer purposes and data flow
- Makefile targets enforce layer boundaries during CI

## Related ADRs

- **ADR-007** (V3 revision) — Repository layout (applies equally to ml/, dl/, nlp/, agentic/)
- **ADR-014** (new) — Project autonomy and templates (provides scaffolds for all four domains)
- **ADR-011** — Per-service conventions (applies to each layer across all domains)
- **ADR-009** — Filesystem and permissions (where projects live on NAS)

---

**Implementation Note:** Iris-KNN (first ML project) will be the reference implementation of this pattern. All subsequent projects across all four domains (ML, DL, NLP, Agentic AI) will follow this 3-layer structure as their foundation.
