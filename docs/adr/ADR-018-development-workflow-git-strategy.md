---
title: Development Workflow & Git Strategy
status: Proposed (new)
context: |
  Phase 1a begins actual implementation of ml-iris-knn. Without explicit development workflow
  and git strategy, individual developers make ad-hoc decisions leading to inconsistency:
  
  1. Branch naming — feature/ml-iris-knn? or ml-iris-knn/classifier? or something else?
  2. Commit messages — no standard format, hard to review history
  3. Testing cadence — when to test locally before pushing?
  4. Code review — PR process, who approves, merge criteria?
  5. Release/tagging — when/how to tag versions?
  
  Need explicit guardrails so all developers follow same workflow across all phases.
decision: |
  Establish lightweight, pragmatic development workflow:
  
  1. Branch naming: {domain}-{project}/{feature} (e.g., ml-iris-knn/classifier, ml-iris-knn/api-routes)
  2. Commit messages: Conventional commits (feat:, fix:, refactor:, docs:)
  3. Local development: Work on feature branch, test locally (TIER 1 → TIER 2 → TIER 3)
  4. Code review: PR to main with checklist, min 1 approval (at solo dev stage; scales to 2+ at team stage)
  5. Tagging: Tag releases as v{domain}-{project}-{version} (v.ml-iris-knn-1.0.0)
  6. Sync: All work on main, no long-lived branches (simplifies merge strategy)
alternatives_considered: |
  A. Git Flow (develop, release, hotfix branches) — rejected, overkill for current scale
  B. Trunk-Based Development (short branches, frequent PRs) — chosen, matches startup/solo-dev
  C. Monorepo trunk with per-project tags — simplifies history, enables atomic cross-project changes
consequences: |
  Positive:
  - Simple branch names communicate work scope (ml-iris-knn/classifier is obviously iris-knn work)
  - Commit message convention enables automated changelog generation
  - Short-lived branches (max 1-2 weeks) reduce merge conflicts
  - Per-project tagging allows independent version control
  - Clear PR checklist ensures quality gates are followed
  
  Negative:
  - Developers must remember commit message format (mitigated by .gitmessage template)
  - Short branches require discipline (no "work-in-progress" branches)
  
  Mitigations:
  - .gitmessage template auto-loaded when creating commits
  - Makefile target: make pr-checklist (verifies all gates before pushing)
  - CI/CD enforces commit message format and branch naming on push
related_adrs: |
  - ADR-013 — Per-project 3-layer architecture (work is organized per project)
  - ADR-020 — Project readiness checklist (PR checklist based on TIER 1/2/3 gates)
  - ADR-007-v3 — Repository layout (monorepo, so all branches share same codebase)
---

# ADR-018 — Development Workflow & Git Strategy

**Status:** Proposed (new)  
**Date:** May 2026  
**Author:** Archit Pandya

## Context

Phase 1a marks the start of actual implementation. Developers need clear guidance on:

- How to name branches
- How to write commit messages
- When/how to test locally
- How to submit code for review
- When to tag releases

Without explicit workflow, consistency suffers. This ADR locks the workflow for all phases and all domains.

## Decision

**Lightweight, pragmatic, trunk-based development workflow:**

### 1. Branch Naming

**Format:** `{domain}-{project}/{feature}`

**Examples:**
```
ml-iris-knn/classifier           (implement classifier model)
ml-iris-knn/api-routes           (implement API endpoints)
ml-iris-knn/database-integration (add postgres integration)
dl-lstm/training-pipeline        (Phase 2, DL domain)
nlp-sentiment/huggingface-setup   (Phase 3, NLP domain)
```

**Pattern breakdown:**
- `{domain}`: ml, dl, nlp, agentic (4-letter prefix)
- `{project}`: project name (kebab-case, matches folder name)
- `{feature}`: specific feature being implemented (kebab-case)

**Why this pattern:**
- Immediately obvious which project/domain the work is for
- Scales across all 8 projects and 4 domains
- Enables filtering: `git branch | grep ml-iris-knn/` shows all iris-knn work
- Supports parallel development: multiple developers on different features

### 2. Commit Message Format

**Conventional Commits:** https://www.conventionalcommits.org/

**Format:** `{type}({scope}): {subject}`

**Types:**
- `feat:` — New feature
- `fix:` — Bug fix
- `refactor:` — Code restructuring (no behavior change)
- `docs:` — Documentation
- `test:` — Test additions/changes
- `chore:` — Build, dependencies, configuration

**Scope:** Typically the layer or component affected (e.g., `presentation-logic`, `db-logic`, `model`)

**Examples:**
```
feat(presentation-logic): add /predict endpoint with Pydantic validation
fix(db-logic): correct SQL query syntax in prediction repository
refactor(application-logic): extract preprocessing to separate method
docs(shared): add docstrings to config.py
test(presentation-logic): add unit tests for API schemas
chore: bump scikit-learn to 1.4.0
```

**Full commit message format:**
```
feat(presentation-logic): add /predict endpoint with Pydantic validation

- Implements POST /predict route accepting PredictionRequest
- Validates input using Pydantic schema
- Delegates to PredictionService for business logic
- Returns PredictionResponse with confidence score
- Includes request_id header for tracing

Closes #42
```

**Why Conventional Commits:**
- Enables automated changelog generation (feat → `## Features`, fix → `## Fixes`)
- Makes git history scannable (`git log --grep=^feat`)
- Communicates intent in commit message (not just code diff)

### 3. `.gitmessage` Template

Save template to repository; developers set git config:

```bash
# .gitmessage (committed to repo root)
# {type}({scope}): {subject}
#
# Describe the change in more detail here.
# - Bullet point 1
# - Bullet point 2
#
# Closes #{issue_number}

# Configure locally (one-time):
git config commit.template .gitmessage
```

### 4. Local Development Workflow

**Before pushing, follow this cadence:**

**Step 1: Create feature branch**
```bash
git checkout -b ml-iris-knn/classifier
```

**Step 2: Implement feature (iterate locally)**
```bash
# Edit code
vim ml/ml-iris-knn/application-logic/model/classifier.py

# Test locally (TIER 1 — Code Readiness)
make lint
make test-unit
make test-cov

# Fix any issues, re-test
```

**Step 3: Docker test (TIER 2 — Docker Readiness)**
```bash
make docker-build
make docker-run
curl http://localhost:8000/health

# Stop container
make docker-stop
```

**Step 4: Integration test (TIER 3 — Integration Readiness)**
```bash
# Start full stack with compose
cd deployment/ml/
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Run end-to-end tests
make test-e2e

# Verify Nginx routing
curl http://localhost/ml/health

# Clean up
docker-compose down
```

**Step 5: Run Makefile checklist (verify all gates)**
```bash
make pr-checklist
# Outputs:
# [✅] Lint passed
# [✅] Unit tests passed (coverage 82%)
# [✅] Docker image built successfully
# [✅] Compose validation passed
# [✅] E2E tests passed
# [✅] Ready to push
```

**Step 6: Commit (following Conventional Commits)**
```bash
git add .
git commit  # Opens editor with .gitmessage template
# Type: feat(application-logic): implement classifier with 3-fold cross-validation

git log --oneline | head -5
# e1a2b3c feat(application-logic): implement classifier with 3-fold cross-validation
# d4e5f6g refactor(db-logic): extract data loader to separate module
# ...
```

**Step 7: Push and create PR**
```bash
git push origin ml-iris-knn/classifier
# GitHub/GitLab prompts to create PR
```

### 5. Pull Request Workflow

**PR Checklist (automated + manual):**

```markdown
## PR: ml-iris-knn/classifier

### TIER 1 — Code Readiness
- [x] Lint passing (black, flake8, mypy)
- [x] Unit tests passing (coverage > 70%)
- [x] No security issues (bandit clean)
- [x] Docstrings on public functions

### TIER 2 — Docker Readiness
- [x] Docker image builds cleanly
- [x] Image size < 500MB
- [x] /health endpoint returns 200
- [x] Logs are JSON formatted

### TIER 3 — Integration Readiness
- [x] E2E tests pass (local compose stack)
- [x] Database connectivity verified
- [x] No hardcoded credentials

### Code Review
- [x] Architecture matches ADR-013 (3-layer pattern)
- [x] No root-level shared/ dependencies
- [x] Configuration via environment variables
- [x] Error handling implemented

### Documentation
- [x] README updated with new feature
- [x] CHANGELOG.md entry added (v1.0.1 section)
- [ ] Runbook added (if applicable)

---

**Ready to merge:** All items ✅

**Merge criteria:**
1. All automated checks pass (CI/CD)
2. At least 1 approval (solo dev phase; 2+ at team phase)
3. All checklist items ✅
4. No merge conflicts
```

**PR Approval Rules:**
- **Solo development (Phase 1-5):** 1 approval (self-review, verify all gates)
- **Team development (Phase 6+):** 2+ approvals (peer review)

### 6. Merge Strategy

**Squash commits before merge** (keeps main history clean):

```bash
# Before merging PR, squash feature branch
git checkout ml-iris-knn/classifier
git rebase -i main  # Interactive rebase, squash intermediate commits
# Result: all work becomes 1 logical commit per feature

git push origin ml-iris-knn/classifier --force-with-lease

# Merge to main
git checkout main
git merge --ff-only ml-iris-knn/classifier
git push origin main
```

**Why squash:**
- Main branch history is clean, one commit per feature
- Easier to revert if needed (one revert = one feature removed)
- Aligns with Conventional Commits format

### 7. Tagging & Releases

**Tag format:** `v{domain}-{project}-{version}`

**Version numbering:** SemVer (MAJOR.MINOR.PATCH)

**Examples:**
```
v.ml-iris-knn-1.0.0         (first production release)
v.ml-iris-knn-1.0.1         (bug fix)
v.ml-iris-knn-1.1.0         (new feature)
v.ml-housing-1.0.0          (separate project, separate versioning)
```

**When to tag:**
- After TIER 3 complete and merged to main
- Before deploying to production

**How to tag:**
```bash
# Create tag
git tag v.ml-iris-knn-1.0.0 -m "ml-iris-knn: first production release"

# Push tag to remote
git push origin v.ml-iris-knn-1.0.0
```

**Auto-changelog generation:**
```bash
# Generate changelog from commits since last tag
git log v.ml-iris-knn-0.9.0..v.ml-iris-knn-1.0.0 --grep=^feat --oneline
# Output:
# e1a2b3c feat(application-logic): implement classifier with cross-validation
# d4e5f6g feat(presentation-logic): add /predict endpoint
# h7i8j9k feat(db-logic): add prediction repository
```

### 8. Sync with Main

**Frequency:** Daily (if actively developing)

```bash
git fetch origin main
git rebase origin/main  # or merge if multiple developers
```

**Why daily:**
- Reduces merge conflicts (small, frequent rebases easier than large merge)
- Ensures local code is fresh (not stale against main)
- Catches conflicts early (before PR review)

### 9. File Commit Standards

**What to commit:**
- Source code (presentation-logic, application-logic, db-logic, shared)
- Tests
- Configuration (configs/, Dockerfile, Makefile, pyproject.toml)
- Documentation (README, CHANGELOG, ADRs)

**What NOT to commit:**
- Data files (data/, models/ — use .gitignore)
- Secrets (.env files, API keys)
- Build artifacts (__pycache__, *.pyc, dist/)
- IDE files (.vscode/, .idea/)

**.gitignore per project:**
```
__pycache__/
*.pyc
.env
.env.local
data/
models/
notebooks/.ipynb_checkpoints/
.pytest_cache/
.mypy_cache/
```

### 10. Guardrails: Pre-commit Hooks

Optional but recommended — run checks before commit:

```bash
# .git/hooks/pre-commit (install once per repo)
#!/bin/bash
echo "Running pre-commit checks..."

make lint          # black, flake8, mypy
if [ $? -ne 0 ]; then
  echo "Lint failed. Commit aborted."
  exit 1
fi

make test-unit     # pytest
if [ $? -ne 0 ]; then
  echo "Tests failed. Commit aborted."
  exit 1
fi

echo "✅ All checks passed. Commit proceeding."
```

## Git History Example

After Phase 1a (ml-iris-knn) and Phase 1b (ml-housing):

```
* e5d4c3b feat(db-logic): add s3 loader for housing project     [v.ml-housing-1.0.0]
* f6e5d4c feat(presentation-logic): implement POST /train endpoint
* g7f6e5d feat(application-logic): integrate housing model with mlflow
* h8g7f6e fix(db-logic): handle null values in preprocessor
* i9h8g7f feat(application-logic): implement classifier with cross-validation  [v.ml-iris-knn-1.0.0]
* j0i9h8g feat(presentation-logic): add /predict and /health endpoints
* k1j0i9h feat(db-logic): implement data loaders and preprocessing
* l2k1j0i refactor: apply v3 architecture — project-autonomous 3-layer design
* m3l2k1j Add compose orchestration: central platform stack
```

Each commit is atomic, self-contained, and traceable.

## CI/CD Integration (Future)

ADR-018 sets the workflow. CI/CD (Phase 5/6) will enforce:

1. **Branch naming:** Validate branch names match pattern
2. **Commit messages:** Validate Conventional Commits format
3. **PR checks:** Auto-run lint, test, docker-build on PR
4. **Merge blockers:** Block merge if checks fail

For now (Phase 1a-1b), manual discipline. CI/CD automates later.

## Checklist: Phase 1a Development

```
[ ] Checkout: git checkout -b ml-iris-knn/classifier
[ ] Code: Implement classifier in application-logic/model/
[ ] Test: make lint && make test-unit (TIER 1)
[ ] Docker: make docker-build && make docker-run (TIER 2)
[ ] Integration: docker-compose up && make test-e2e (TIER 3)
[ ] Checklist: make pr-checklist (all ✅)
[ ] Commit: git commit (use .gitmessage template)
[ ] Push: git push origin ml-iris-knn/classifier
[ ] PR: Create PR with checklist items
[ ] Review: Self-review (solo dev phase) or peer review
[ ] Merge: Squash and merge to main
[ ] Tag: git tag v.ml-iris-knn-1.0.0 (after TIER 3 complete)
```

## Related ADRs

- **ADR-013** — Per-project 3-layer architecture (work organized per project)
- **ADR-015** — Deployment service separation (commits follow separation)
- **ADR-020** — Project readiness checklist (PR checklist based on tiers)
- **ADR-017** — Docker Compose file strategy (testing uses compose files)

---

**Status: READY FOR IMPLEMENTATION**

Workflow is lightweight, pragmatic, and scales from solo development (Phase 1-5) to team development (Phase 6+). Git history is clean, commit messages are meaningful, and every PR is traceable to architecture decisions.
