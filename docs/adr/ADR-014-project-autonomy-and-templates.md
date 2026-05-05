---
title: Project autonomy and templates — consistent scaffolding for rapid project creation
status: Proposed (new)
context: |
  ADR-013 locks the 3-layer pattern for every project. However, starting a new project
  with ~20 required folders and files is friction: copy/paste errors, forgotten structure elements.
  
  Without a template system, the 3-layer pattern becomes a guideline that's easy to violate.
  With templates, it becomes a guarantee.
decision: |
  Maintain four template projects, one for each AI domain:
  
  - ml/_templates/ml-project-template/        Full 3-layer scaffold for Machine Learning projects
  - dl/_templates/dl-project-template/        Full 3-layer scaffold for Deep Learning projects
  - nlp/_templates/nlp-project-template/      Full 3-layer scaffold for NLP projects
  - agentic/_templates/agentic-project-template/  Full 3-layer scaffold for Agentic AI projects
  
  New project workflow:
  1. cp -r ml/_templates/ml-project-template/ ml/ml-my-new-project/
  2. cd ml/ml-my-new-project/
  3. Edit Makefile, pyproject.toml, .env.example with project specifics
  4. Start implementing per ADR-013 layers
  
  Templates include:
  - Full folder structure (presentation-logic/, application-logic/, db-logic/, shared/)
  - Placeholder files in each layer with docstrings explaining purpose
  - conftest.py, fixtures/ for testing
  - pyproject.toml with baseline dependencies (fastapi, sklearn/torch, pytest)
  - Makefile with targets: make test, make lint, make docker-build, make docker-run
  - README.md explaining the layer structure
  - Dockerfile with multi-stage build
  - .env.example with placeholders
  - .gitignore for data/, models/, notebooks/
  
  Templates are versioned: as ADR-013 evolves, templates are updated. All new projects use current template.
  Existing projects only update on explicit migration.
alternatives_considered: |
  A. No templates, rely on documentation — rejected because violation is easy, friction is high
  B. Cookiecutter/copier plugins — over-engineered for current project count
  C. Git template repositories — rejected, simpler to use folder copy
  D. Template folders in repo (chosen) — low friction, easy to evolve, version with code
consequences: |
  Positive:
  - Zero friction to create new projects (one cp command)
  - Consistency guaranteed (every new project has identical structure)
  - Quality baseline (Dockerfile, Makefile, tests/ pre-built)
  - Easy to evolve (update template once, new projects inherit changes)
  - Scales: 50 projects all follow same pattern with minimal cognitive load
  
  Negative:
  - Template maintenance (as best practices evolve, templates must be updated)
  - Projects created from old template might drift from current pattern
  
  Mitigations:
  - Document template version in project README
  - ADR revision policy: template templates updated when ADR-013/014/015 change
  - Makefile target: make scaffold-validate (checks folder structure compliance)
related_adrs: |
  - ADR-013 — per-project 3-layer architecture (templates enforce this)
  - ADR-013 — Per-project 3-layer architecture (templates enforce this across all domains)
  - ADR-007 (V3 revision) — Repository layout (templates live at ml/_, dl/_, nlp/_, agentic/_)
  - ADR-008 — Repository packaging (single monorepo, templates within it)
---

# ADR-014 — Project Autonomy and Templates

**Status:** Proposed (new)  
**Date:** May 2026  
**Author:** Archit Pandya

## Context

ADR-013 establishes that every project across all four AI domains (ML, DL, NLP, Agentic AI) must follow a 3-layer pattern. Good decision, strong architecture.

**Problem:** Without scaffolding per domain, developers face friction every time they start a new project. ~20 folders to create, 15 files to set up, easy to miss something. The pattern becomes a guideline that can be violated.

**Solution:** Template projects per domain that developers copy-paste, then specialize.

## Decision

Maintain four template projects in the repository, one per domain:

### ml/_templates/ml-project-template/

Complete scaffold for Machine Learning projects (scikit-learn, PyTorch, classical algorithms).

```
ml/_templates/ml-project-template/
├── presentation-logic/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py           (FastAPI app, routes factory)
│   │   ├── routes.py         (GET /health, GET /predict, POST /train)
│   │   ├── schemas.py        (Pydantic models)
│   │   ├── middleware.py     (request_id, logging)
│   │   └── dependencies.py   (service injection)
│   └── errors/
│       ├── __init__.py
│       └── handlers.py       (HTTP error formatters)
├── application-logic/
│   ├── __init__.py
│   ├── model/
│   │   ├── __init__.py
│   │   ├── classifier.py     (Model class, architecture)
│   │   ├── trainer.py        (Training logic)
│   │   └── predictor.py      (Prediction logic)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── training_pipeline.py
│   │   └── inference_pipeline.py
│   └── services/
│       ├── __init__.py
│       └── prediction_service.py
├── db-logic/
│   ├── __init__.py
│   ├── loaders/
│   │   ├── __init__.py
│   │   ├── local_loader.py
│   │   ├── s3_loader.py
│   │   └── db_loader.py
│   ├── transforms/
│   │   ├── __init__.py
│   │   └── preprocessor.py
│   └── repository/
│       ├── __init__.py
│       └── prediction_repository.py
├── shared/
│   ├── __init__.py
│   ├── config.py
│   ├── logger.py
│   ├── metrics.py
│   ├── constants.py
│   ├── exceptions.py
│   └── utils.py
├── notebooks/
│   └── .gitkeep
├── tests/
│   ├── conftest.py           (pytest fixtures)
│   ├── fixtures/
│   │   ├── __init__.py
│   │   └── sample_data.py
│   ├── presentation/
│   │   ├── test_routes.py
│   │   └── test_schemas.py
│   ├── application/
│   │   ├── test_classifier.py
│   │   └── test_trainer.py
│   └── db/
│       └── test_loaders.py
├── data/
│   ├── .gitkeep
│   ├── raw/
│   ├── processed/
│   └── splits/
├── models/
│   └── .gitkeep
├── configs/
│   ├── model.yaml         (model hyperparameters)
│   ├── api.yaml           (API config: port, debug, etc.)
│   └── logging.yaml       (logging levels)
├── docker/
│   ├── Dockerfile         (multi-stage: build → runtime)
│   ├── Dockerfile.dev
│   ├── entrypoint.sh      (startup script)
│   └── .dockerignore
├── pyproject.toml         (dependencies, project metadata)
├── requirements.txt       (fastapi, scikit-learn, torch, pytest, etc.)
├── requirements-dev.txt   (black, flake8, mypy, pytest-cov)
├── Makefile               (test, lint, docker-build, docker-run, etc.)
├── README.md              (explains project structure, how to run)
├── .env.example           (template: MODEL_PATH, API_PORT, LOG_LEVEL)
├── .gitignore             (data/, models/, notebooks/, __pycache__)
└── CHANGELOG.md           (project-specific release notes)
```

### dl/_templates/dl-project-template/

Identical structure, with TensorFlow/PyTorch-specific examples in docstrings.

### nlp/_templates/nlp-project-template/

Identical 3-layer structure, with Hugging Face Transformers, spaCy, and NLTK examples in docstrings.

### agentic/_templates/agentic-project-template/

Identical 3-layer structure, with LLM orchestration patterns, tool calling, and agent framework examples in docstrings.

## New Project Workflow

```bash
# 1. Copy template for your domain
cp -r ml/_templates/ml-project-template/ ml/ml-my-classifier/
# OR
cp -r nlp/_templates/nlp-project-template/ nlp/nlp-my-classifier/
# OR
cp -r agentic/_templates/agentic-project-template/ agentic/agentic-my-agent/

# 2. Edit project metadata
cd ml/ml-my-classifier/
sed -i 's/my-classifier/my-classifier/g' pyproject.toml Makefile README.md

# 3. Implement per ADR-013
# - Write model logic in application-logic/model/
# - Add loaders in db-logic/loaders/
# - Wire routes in presentation-logic/api/routes.py
# - Dockerfile and Makefile are already set up

# 4. Test and run
make test
make docker-build
make docker-run
```

## Template Maintenance Policy

- **When to update templates:**
  - ADR-013 changes (layer structure changes)
  - Best practices evolve (e.g., new testing strategy)
  - Dependency security updates
  
- **How to update:**
  - Edit `ml/_templates/ml-project-template/` directly
  - New projects automatically use updated template
  - Existing projects pinned to their created template version (documented in project README)

- **Version tracking:**
  - Template version stored in template Makefile: `TEMPLATE_VERSION := 1.0`
  - New projects inherit version, document it in README.md
  - If template evolves to v1.1, new projects use v1.1; old projects remain at v1.0 until explicit migration

## Example: Iris-KNN Uses Template

First project (iris-knn) is created by:
1. Copying `ml/_templates/ml-project-template/` to `ml/ml-iris-knn/`
2. Implementing business logic within that structure
3. Becomes the reference implementation; future projects follow iris-knn's pattern

## Alternatives Considered

### A. No Templates, Rely on Documentation
**Rejected** — High friction, easy to miss structure elements, pattern violated.

### B. Cookiecutter / Copier Automation
**Rejected** — Overkill for current project count; `cp` is sufficient.

### C. Template Repositories (GitHub template repos)
**Rejected** — More overhead than in-repo templates; less convenient to evolve.

### D. In-Repo Template Folders
**Chosen** — Low friction (one `cp` command), easy to maintain and evolve, version with code.

## Consequences

### Positive
- **Zero friction** to start new projects (one-line copy)
- **Consistency guaranteed** — all projects identical structure baseline
- **Quality baseline** — Dockerfile, Makefile, tests/ pre-built
- **Easy to evolve** — Update template once, new projects inherit
- **Scales well** — 50 projects created from one source-of-truth

### Negative
- **Template maintenance burden** — Must keep templates current as best practices evolve
- **Version fragmentation** — Old projects might diverge from new template
  - *Mitigation:* Migration guide in docs when template changes significantly

## Related ADRs

- **ADR-013** — Per-project 3-layer architecture (templates enforce this)
- **ADR-007** (V3 revision) — Repository layout (templates live at `ml/_templates/`, `dl/_templates/`)
- **ADR-008** — Repository packaging (templates within monorepo)

---

**First Implementation:** Iris-KNN will be registered as a project under `ml/ml-iris-knn/`, created by copying and customizing the ML template. All subsequent projects across all four domains (DL, NLP, Agentic) will follow the same template-based approach.
