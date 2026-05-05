---
name: V3 Architecture Redesign Plan
description: Structural pivot from Stage 2 flat layout to V3 project-autonomous 3-layer design
status: Planning phase — awaiting approval before execution
---

# pandyaHomeLab V3 Architectural Redesign Plan

**Date:** May 2026  
**Status:** Planning (no changes applied yet)  
**Scope:** Folder structure redesign + ADR updates  
**Impact:** Zero code changes. Pure structure. One-commit refactor.

---

## 1. Context: Why V3

**Stage 2 structure (current):**
```
platform/    ← infrastructure services (proxy, data, mlops)
site/        ← landing page
services/ml/classification/iris-knn/  ← projects too deep
compose/     ← orchestration
docs/adr/    ← locked decisions
```

**Problem:** Projects are not autonomous. No per-project architecture visible. Doesn't communicate "I built a platform."

**V3 structure (proposed):**
```
ml/          ← ML projects, each with 3-layer internal structure
dl/          ← DL projects, same pattern
shared/      ← cross-project utilities, datasets, configs
deployment/  ← docker-compose, nginx configs, env overrides
infra/       ← IaC, CI/CD workflows, Terraform
website/     ← pandyahomelab.com landing page
docs/        ← ADRs, runbooks, architecture
experiments/ ← NAS-only development notebooks
```

**Benefit:** Each project is self-contained, professionally layered, portfolio-ready.

---

## 2. Current vs. Proposed Structure (Detailed Mapping)

### Current Files → V3 Location

| Current Path | V3 Path | Notes |
|---|---|---|
| `platform/proxy/` | `deployment/nginx/` | Nginx config + Dockerfile |
| `platform/data/` | `deployment/services/postgres/`, `minio/`, `redis/` | Backend services |
| `platform/mlops/` | `deployment/services/mlflow/` | MLflow service |
| `compose/docker-compose.yml` | `deployment/docker-compose.yml` | Main orchestration |
| `site/index.html` | `website/index.html` | Landing page |
| (none yet) | `ml/_templates/` | Template for new ML projects |
| (none yet) | `dl/_templates/` | Template for new DL projects |
| `docs/adr/` | `docs/adr/` | Keep as-is |

### Iris-KNN Placement (New)

**Current:** `services/ml/classification/iris-knn/`  
**V3:** `ml/ml-iris-knn/` (flat under `ml/`, top-level project)

**Internal structure (3-layer pattern):**
```
ml/ml-iris-knn/
├── presentation-logic/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── middleware.py
│   └── errors/
│       └── handlers.py
├── application-logic/
│   ├── model/
│   │   ├── classifier.py
│   │   └── predictor.py
│   ├── pipeline/
│   │   └── inference_pipeline.py
│   └── services/
│       └── prediction_service.py
├── db-logic/
│   ├── loaders/
│   │   ├── local_loader.py
│   │   └── s3_loader.py
│   ├── transforms/
│   │   └── preprocessor.py
│   └── repository/
│       └── prediction_repository.py
├── shared/
│   ├── config.py
│   ├── logger.py
│   ├── metrics.py
│   └── utils.py
├── notebooks/
│   └── 01_eda_iris.ipynb
├── tests/
│   ├── presentation/
│   ├── application/
│   └── db/
├── data/
│   └── (gitignored, raw/processed)
├── models/
│   └── (gitignored, checkpoints)
├── configs/
│   ├── model.yaml
│   ├── api.yaml
│   └── logging.yaml
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   ├── entrypoint.sh
│   └── .dockerignore
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── Makefile
├── .env.example
└── README.md
```

---

## 3. ADR Implications

### Current ADRs (no changes needed)
- **ADR-001 to ADR-006** (Stage 1): Still hold. Trust boundary, URL hierarchy, etc. unaffected.
- **ADR-007** (Repository layout): **NEEDS UPDATE** — we're changing the folder structure significantly.
- **ADR-008 to ADR-012** (Stage 2): Still hold. Secrets, auth, per-service conventions apply to each project layer.

### New ADRs Required

| ADR # | Title | Why | Proposed Decision |
|---|---|---|---|
| **013** | Per-project 3-layer architecture | Locks the presentation/application/db separation within EVERY project | All ML/DL projects MUST follow P/A/D layers |
| **014** | Project autonomy and templates | Locks template scaffolding pattern | New projects scaffold from `ml/_templates/` or `dl/_templates/` |
| **015** | Deployment service separation | Separates deployment orchestration from project code | `deployment/` folder houses all compose/Nginx/env configs |

### Updated ADR

**ADR-007 (Repository layout)** — Change from:
```
platform/, site/, services/, compose/, docs/
```
To:
```
ml/, dl/, shared/, deployment/, infra/, website/, docs/, experiments/
```

---

## 4. Change Breakdown (Structural Refactor Only)

### Phase 1: Create New Top-Level Folders
```bash
mkdir -p ml/_templates/
mkdir -p dl/_templates/
mkdir -p nlp/_templates/
mkdir -p agentic/_templates/
mkdir -p shared/{datasets,utils,scripts,configs,tests}
mkdir -p deployment/{nginx,services/{postgres,minio,redis,mlflow},envs}
mkdir -p infra/{terraform,ci-cd}
mkdir -p website/
mkdir -p experiments/
```

### Phase 2: Move Existing Files
1. **Nginx** → `platform/proxy/*` → `deployment/nginx/`
2. **Data services** → `platform/data/*` → `deployment/services/{postgres,minio,redis}/`
3. **MLflow** → `platform/mlops/*` → `deployment/services/mlflow/`
4. **Compose** → `compose/docker-compose.yml` → `deployment/docker-compose.yml`
5. **Landing page** → `site/index.html` → `website/index.html`
6. **ADRs/docs** → `docs/` → stays, but update ADR-007

### Phase 3: Create Templates
Create `ml/_templates/ml-project-template/` with full 3-layer skeleton (for copy-paste scaffolding).  
Create `dl/_templates/dl-project-template/` with full 3-layer skeleton.  
Create `nlp/_templates/nlp-project-template/` with full 3-layer skeleton.  
Create `agentic/_templates/agentic-project-template/` with full 3-layer skeleton.

### Phase 4: Update Documentation
- Update ADR-007 with new structure including all four domains (ml/, dl/, nlp/, agentic/)
- Create ADR-013, 014, 015 with patterns applying to all four domains
- Update `docs/stage-2/` memos to reference v3 migration
- Update `docs/stage-2/` memos to reference v3 migration
- Create `docs/v3-migration-summary.md`

### Phase 5: Update Landing Page
Adapt `website/index.html` to reference new folder structure (links remain `/ml/ml-iris-knn`, `/dl/...`, etc.).

### Phase 6: Update Main Compose
Update `deployment/docker-compose.yml` to reference new service paths.

### Phase 7: Git Commit (Single Commit)
```
message: "Refactor: apply v3 architecture — project-autonomous 3-layer design

- Migrate platform/ → deployment/ (separate orchestration from projects)
- Establish ml/, dl/ as top-level project folders
- Create shared/, infra/, website/ for cross-cutting concerns
- Add project templates for consistent scaffolding
- Update ADR-007 (repository layout)
- Add ADR-013, 014, 015 (3-layer pattern, autonomy, deployment separation)
- Zero code changes; pure structural refactor
"
```

---

## 5. Iris-KNN Implementation (After Refactor)

Once refactored, iris-knn is built at `ml/ml-iris-knn/` with full 3-layer internal structure.

**Route:** `/ml/iris-knn` (per ADR-003 URL hierarchy)  
**Container:** `ml-iris-knn` service in compose  
**Portfolio narrative:** "Self-contained ML classifier with clean separation of concerns"

---

## 6. Rollback Risk

**Risk level:** MINIMAL
- No code written yet (iris-knn doesn't exist)
- Only one Git commit in history
- If needed: `git reset --soft HEAD~1` and restore old folder structure

---

## 7. Step-by-Step Execution Plan (Post-Approval)

1. ✅ **Approval** — User reviews this plan, approves
2. **Local NAS refactor** — Apply all Phase 1-7 changes locally
3. **Verification** — Check folder structure, configs point correctly
4. **Git commit** — Single refactor commit as shown above
5. **Build iris-knn** — Create full 3-layer project under `ml/ml-iris-knn/`
6. **Test end-to-end** — Verify landing page links work, compose runs

---

## 8. Files Affected

**Files to move (no content change):**
- `platform/proxy/*` → `deployment/nginx/`
- `platform/data/*` → `deployment/services/`
- `platform/mlops/*` → `deployment/services/mlflow/`
- `compose/docker-compose.yml` → `deployment/docker-compose.yml`
- `site/index.html` → `website/index.html`

**Files to update (content change):**
- `docs/adr/ADR-007-repository-layout.md` — Rewrite with v3 structure
- `docs/adr/README.md` — Add ADR-013, 014, 015
- `deployment/docker-compose.yml` — Update service paths
- `website/index.html` — Ensure routes match new structure

**Files to create:**
- `docs/adr/ADR-013-per-project-3-layer-architecture.md`
- `docs/adr/ADR-014-project-autonomy-and-templates.md`
- `docs/adr/ADR-015-deployment-service-separation.md`
- `ml/_templates/ml-project-template/` (skeleton)
- `dl/_templates/dl-project-template/` (skeleton)
- `nlp/_templates/nlp-project-template/` (skeleton)
- `agentic/_templates/agentic-project-template/` (skeleton)
- `docs/v3-migration-summary.md`

---

## 9. Success Criteria

✅ All folders exist per v3 layout  
✅ All existing files moved to new locations  
✅ ADRs updated (007) and new ADRs created (013-015)  
✅ `deployment/docker-compose.yml` runs without error  
✅ Landing page accessible, links route correctly  
✅ Git history shows one clean refactor commit  
✅ Ready to build iris-knn with 3-layer structure  

---

## Approval Gates

**Before proceeding to execution:**
1. User confirms plan aligns with v3 vision ✋
2. User approves timeline (expect ~2 hours to refactor + verify)
3. User ready to build iris-knn after (expects full 3-layer project)

**Proceed?**
