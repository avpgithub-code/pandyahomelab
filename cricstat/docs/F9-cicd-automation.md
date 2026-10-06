# F9 — cricstat CI/CD and automation

Status: **done** (2026-10-05). It pilots platform Stage 3 (CI/CD) for one project first.
The design was decided in planning: CI on every change, **pull-based** CD (no inbound ports and no runner on the NAS),
a manual approval gate first, then automatic deploys once proven.

## 1. The loop
```
push / PR ──► GitHub Actions: lint + tests (py3.8, 3.12) ──► image build + smoke (non-root)
                                   │ main, or manual run
                                   ▼
                     approval gate (environment nas-production: you approve)
                                   ▼
                     publish ghcr.io/avpgithub-code/cricstat-pipeline:{branch, sha-…}
                                   ▼  (NAS pulls; GitHub never connects to the NAS)
 DSM task ──► deployment/cricstat/cd-pull.sh: pull → smoke test on the NAS CPU → tag :latest (old → :previous)
                                   ▼
 next scheduled run (05:30 daily) uses the new image · `cd-pull.sh rollback` restores :previous
```

## 2. What runs where
| Piece | Where | State |
|---|---|---|
| CI: ruff + pytest on Python 3.8 and 3.12 | `.github/workflows/cricstat-ci.yml`, job `pipeline-tests` | ✅ live (first run green) |
| Image build and non-root smoke test | job `pipeline-image` | ✅ live. It now runs as uid 1026, so the Synology 700-bits bug is caught in CI |
| Publish to GHCR | `.github/workflows/cricstat-publish.yml` (only when `cricstat/cricstat-pipeline/**` changes on main, or by hand), environment **`nas-production`** (required reviewer: avpgithub-code) | ✅ first publish approved 2026-10-05 (`feat-cricstat-foundation`, `sha-bb73e10`); package is public, anonymous pull OK |
| NAS deploy | `deployment/cricstat/cd-pull.sh` (pull, NAS smoke test, retag, rollback) | ✅ proven 2026-10-05: deploy, no-op re-run, rollback, roll forward, failed-pull exit 1, real `recent` run (run 5) on the GHCR image |
| NAS schedule | DSM task **"cricstat CD pull"**, daily 05:15 (before the 05:30 refresh) | ✅ live 2026-10-05 (verified with synoschedtask). `:main` published from merge `2e5cddc` and deployed to the NAS |
| Action versions | checkout v7, setup-python v7, buildx v4, login v4, metadata v6, build-push v7 | updated (clears the Node.js 20 warnings) |

## 3. Rules that keep it safe
- **Publishing needs your approval** on GitHub (Actions → the run → "Review deployments"). PRs never publish, and
  docs-only changes never ask (the publish workflow only runs when the image's own files change).
- **Every new image is smoke-tested on the NAS itself** before it goes live. CI runners have AVX and the NAS doesn't,
  so passing in CI is not enough.
- **The previous image is always kept** (`:previous`), and `sh cd-pull.sh rollback` swaps it back in seconds.
- **Exit codes drive alerts:** a failed pull or smoke test exits 1, and the DSM email fires.
- **Once CD is live, don't build images on the NAS** (`docker compose build` would overwrite `:latest` with an untested
  local build). Emergencies only, and log it.
- **No secrets in CI** until the eval gate (P3/P4). GHCR uses the workflow's own short-lived `GITHUB_TOKEN`.

## 4. Gates added in later phases (already planned)
| Gate | Added in | Blocks |
|---|---|---|
| Serving-DB build: F4 metric fixtures + data-quality checks before the atomic swap | P0 (build step) | A bad build reaching the site |
| Golden-figure check after each full build | P0 | Wrong stats (results published on Methodology) |
| Model promotion: backtest must not regress, then the MLflow alias moves | P1 | Worse forecasts going live |
| Agent eval subset on PRs, full set nightly | P3/P4 | Accuracy regressions |
| Always-on services: `cd-pull.sh` restarts and health-checks them, and rolls back on failure | P0 (cricstat-api) | A broken API staying up |
| Switch the manual approval to automatic | After a few clean deploys | — |

## 5. One-time steps for you
1. ✅ Done: the package inherited **public** visibility from the repo. (Steps, if ever needed: make the package **public** on GitHub (Your profile → Packages → `cricstat-pipeline`
   → Package settings → Change visibility → Public). The repo is public and the image holds no secrets, so the NAS can
   pull without storing a token.)
2. ✅ Done: **DSM task "cricstat CD pull":** daily at 05:15, user root, email on abnormal termination. Command:
   `sh /volume1/pandya-homelab/deployment/cricstat/cd-pull.sh`
