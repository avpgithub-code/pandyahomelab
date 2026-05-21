# Phase 2 Master Plan — DL Domain

**Objective:** Stand up the Deep Learning domain on the pandyaHomeLab platform. Three demo projects, all reachable under `/dl/`, all tracking experiments in the shared MLflow.

**Network:** First time we instantiate a second domain network on the NAS. `dl-network` (172.21.0.0/24) is in the architecture but doesn't exist yet — Phase 2a creates it.

**Framework:** PyTorch (CPU-only wheels — no CUDA on the NAS). Images will be ~2.5GB; build time and bandwidth will dominate the first iteration.

---

## Sub-phases

| Sub-phase | Project | URL | Status |
|---|---|---|---|
| **2a** | `dl-mnist-cnn` — CNN handwritten digit classifier | `/dl/mnist-cnn/` | Plan exists, needs drift refresh ([docs/PHASE_2A_EXECUTION_PLAN.md](PHASE_2A_EXECUTION_PLAN.md)) |
| **2b** | `dl-lstm-forecast` — LSTM time-series forecaster | `/dl/lstm-forecast/` | Stub planned ([docs/PHASE_2B_EXECUTION_PLAN.md](PHASE_2B_EXECUTION_PLAN.md)) |
| **2c** | `dl-yolo-object-detection` — YOLOv8 object detection | `/dl/object-detection/` | Stub planned ([docs/PHASE_2C_EXECUTION_PLAN.md](PHASE_2C_EXECUTION_PLAN.md)) |

**Order is forced:** 2a must ship first because it creates `dl-network`, adds Nginx attachment to it, and replaces the placeholder `/dl/` 503. 2b and 2c attach to the already-running infrastructure.

---

## What's shared across 2a / 2b / 2c

These are the patterns each sub-phase follows. New for Phase 2; everything below applies once.

### dl-network (one-time setup, done in 2a)
- CIDR `172.21.0.0/24` (already reserved in [v3 architecture](../memory/v3_architecture_locked.md)).
- Created by `deployment/dl/docker-compose.yml` (the base file — services-empty, network-only, same pattern as `deployment/ml/docker-compose.yml`).
- Nginx attaches a **second interface** at `172.21.0.20` so it can proxy `/dl/*` upstream containers.

### Domain-local infrastructure (per V3 architecture)
Each DL demo **only** attaches to `dl-network` — no cross-network reach-back into `ml-network`. This honors the V3 "domain autonomy" principle: each domain has its own postgres / minio / redis / mlflow.

Phase 2a is therefore *two* things, in this order:
1. **Stand up dl-network infrastructure** (4 containers: dl-postgres, dl-minio, dl-redis, dl-mlflow). This happens *before* any DL demo and is reused by 2b and 2c.
2. **Build the first DL demo** (dl-mnist-cnn).

### Per-project networking
Each DL demo:
- Gets a slot at `172.21.0.10`, `.11`, `.12` (mirroring how ML demos used `.10`, `.11`, `.12`).
- Attaches **only** to `dl-network`. No `ml_ml-network` attachment.

### MLflow
- **New tracking server: `dl-mlflow:5000`** on `dl-network` at `172.21.0.5`. Separate from the ML tracking server.
- Each demo creates its own experiment by name (`dl-mnist-cnn`, `dl-lstm-forecast`, etc.).
- Configuration is the same as ml-mlflow — see [mlflow_operational_lessons](../memory/mlflow_operational_lessons.md). Re-apply every gotcha (artifact root, ajax/graphql Nginx routes, CORS) to the new instance.
- **Open question:** how to expose the dl-mlflow UI. The current `/mlflow/` Nginx routes (including the un-prefixed `/api/2.0/mlflow`, `/ajax-api/2.0/mlflow`, `/graphql`) bind to *one* MLflow server. Options to decide during 2a.0:
  - **Subdomain**: `mlflow-dl.pandyahomelab.com` (clean, needs Cloudflare DNS work + cert)
  - **Sub-path with rewrite**: `/dl/mlflow/` — MLflow 3.x supports a base path; needs `--gunicorn-opts "--proxy-headers"` and MLflow served behind a path prefix. Cleaner than option 1 but the `/api/2.0/mlflow` collision is still there.
  - **Internal-only**: dl-mlflow has no public UI; visitors only see `/mlflow/` (ML). Ops user uses SSH tunnel for dl-mlflow UI. Simplest; matches the spirit of "domain autonomy" (each domain's tracking is independent, no shared UI).

### Feedback widget
- All three demos add the **one-line `<script src="/feedback-widget.js">`** before `</body>` in their `ui.html`.
- See [feedback_widget_v1](../memory/feedback_widget_v1.md). No new Nginx or backend work needed — the route already exists.

### About drawer
- All three demos ship with an `about.json` and the About drawer pattern (same as iris-knn / housing-linear / titanic-automl).
- Sections: Project Summary, Dataset, Architecture (with Mermaid diagram), Training, Metrics with live token substitution, Code Walkthrough, Author/Credits, Learn More.

### Landing page (`website/index.html`)
- DL section currently shows *0 live · 3 planned* with all three planned cards already in place.
- Each sub-phase ends with: swap the corresponding card's `status-planned` → `status-live`, change `proj-link-disabled` → real `<a href>`, update the `domain-count`.

### Build & deploy pattern
- Demo images are baked via `COPY . .` — every code or `ui.html` change requires `docker build` + `compose up -d --force-recreate`.
- `nginx.conf` is **baked** into the `pandya-nginx` image — every Nginx route change requires rebuilding that image.
- Each demo's `compose-project-dir` follows the same pattern (`deployment/dl/docker-compose.yml` + `docker-compose.dev.yml`) — base declares the network, dev overlay adds the services.
- After `--force-recreate`, expect a 30-second 502 burst from Nginx's `max_fails` cooldown. Reload Nginx to skip it.
- All the above is captured in [deployment_image_rebuild_rules](../memory/deployment_image_rebuild_rules.md).

---

## Per-sub-phase exit criteria (applies to each)

- [ ] Model trains to documented target accuracy/metric
- [ ] All TIER 1 tests pass
- [ ] Docker image builds cleanly on first attempt (lessons captured if not)
- [ ] `https://pandyahomelab.com/dl/<project>/` loads the demo UI
- [ ] Predict round-trip works in the browser
- [ ] MLflow experiment visible at `/mlflow/`
- [ ] About drawer renders with live metrics
- [ ] Feedback widget appears at the bottom of the page
- [ ] Landing page card marked Live, route active
- [ ] Branch merged to `main`, tagged `v.<project>-1.0.0`

---

## Phase 2 exit criteria (overall)

- [ ] All three DL demos shipped (2a, 2b, 2c)
- [ ] dl-network instantiated and stable
- [ ] DL domain count on landing page = **3 live**
- [ ] At least one experiment per demo logged in MLflow
- [ ] No regressions on ML domain (iris/housing/titanic still healthy)
- [ ] Decision recorded: should DL analytics fork off its own ingester, or reuse the existing one on ml-network? (Defer to end of Phase 2.)

---

## IP / Port allocation across Phase 2

All on `dl-network` (172.21.0.0/24). No cross-network attachments — clean domain autonomy.

| Service | dl-network IP | Host port | Notes |
|---|---|---|---|
| dl-postgres | 172.21.0.2 | 5434 (host) | Domain-local DB |
| dl-minio | 172.21.0.3 | 9002/9003 (host) | Artifact store for dl-mlflow |
| dl-redis | 172.21.0.4 | 6380 (host) | Cache (DL-only — separate from ml-redis) |
| dl-mlflow | 172.21.0.5 | — | Experiment tracking for DL |
| **dl-mnist-cnn** | 172.21.0.10 | 8010 | Phase 2a |
| **dl-lstm-forecast** | 172.21.0.11 | 8011 | Phase 2b |
| **dl-yolo-object-detection** | 172.21.0.12 | 8012 | Phase 2c |
| pandya-nginx (second interface) | 172.21.0.20 | — | Proxy attachment |

**Host port mapping rationale:** every host port is shifted by +1 (or doubled-shift) vs. ml-network's equivalent — 5433→5434, 9000→9002, 6379→6380. Avoids conflicts on the Synology host.

**No ml-network attachment for any DL service.** ml-network and dl-network are completely isolated, as the V3 architecture intends.

---

## What this plan does *not* commit to

- Specific dates. Each sub-phase ships when ready; user-driven cadence.
- The exact architecture inside each demo (left to per-sub-phase plans). Listed model choices are starting points, not contracts.
- Whether NLP and Agentic domains follow this exact template — they likely will, but that's Phase 3+.
