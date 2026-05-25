# Phase 2b Execution Plan — dl-lstm-forecast

**Objective:** Build dl-lstm-forecast — LSTM time-series forecaster on real-world NYC CitiBike daily ride counts.
**URL:** `https://pandyahomelab.com/dl/lstm-forecast/`
**Port:** 8011 (host) → 8000 (container)
**dl-network IP:** 172.21.0.11
**Tracker:** `mlflow-dl.pandyahomelab.com` (writes to `dl-mlflow:5000` on dl-network — no ml-network attachment per V3 domain autonomy)
**Tag at ship:** `v.dl-lstm-forecast-1.0.0`

**Model:** 1-layer LSTM, hidden=64, dropout=0.2, predicts next-day ride count from a sliding window of past N days.
**Dataset:** NYC CitiBike daily ride counts (aggregated from public trip-level data, ~3 years → ~1,100 daily points).
**Target metric:** test MAPE ≤ 15% on held-out final-year window. (LSTMs on noisy daily counts won't beat 99% MNIST-style accuracy; MAPE is the honest yardstick.)
**Demo UI:** Chart.js line chart of historical counts + autoregressive 14-day forecast with widening MC-Dropout confidence band + "compare to actuals" overlay when anchor is historical + one-click sample-forecast button.

All Phase 2a DL domain infrastructure is already live (dl-network, dl-postgres, dl-minio, dl-redis, dl-mlflow exposed at `mlflow-dl.pandyahomelab.com`, Nginx attached to dl-network at .20). 2b only adds one container.

Read these memories before starting:
- `phase_2a_complete` — what 2b inherits; the four hard-won lessons (Nginx eager upstream resolve, Cloudflare 100s ceiling, /model-info trap, logging visibility)
- `deployment_image_rebuild_rules` — bind-mount vs. baked, compose-has-no-build trap, Nginx 502 cooldown
- `mlflow_operational_lessons` — re-apply to dl-mlflow runs
- `cloudflare_tunnel` — no new tunnel/cert/DNS work; existing wildcards cover everything
- `feedback_widget_v1` — one-line embed

---

## Locked decisions (sign-off 2026-05-25)

| # | Decision | Choice |
|---|---|---|
| 1 | Dataset | NYC CitiBike daily ride counts (aggregated from public trip data). Reproducible-build path: download + clean + aggregate once via `db-logic/scripts/build_dataset.py`, commit the resulting CSV. |
| 2 | Forecast horizon | 14-day forecast, implemented as a **1-step model rolled out autoregressively** (model output for day t+1 is fed back as input for predicting day t+2, and so on for 14 steps). |
| 3 | Demo UI | Chart.js historical line + 14-day forecast with widening confidence band (MC Dropout, N=30 stochastic forward passes per step → mean ± 2σ) + "compare to actuals" overlay activated when the visitor's chosen anchor date is inside the historical range + pre-loaded "show me a sample forecast" button. About drawer + feedback widget same as 2a. |
| 4 | Dataset storage | Cleaned daily-aggregated CSV (`db-logic/data/bike_share_daily.csv`, < 1 MB) **baked into the image** via `COPY`. Raw CitiBike download and aggregation happens once via `db-logic/scripts/build_dataset.py`; the output CSV is committed so v1.0.0 has fixed training data forever. |

---

## Pre-flight check

```bash
curl -k https://localhost:8443/dl/mnist-cnn/health             # {"status":"healthy",...}
curl -k https://localhost:8443/                                # landing page 200
curl -ks https://mlflow-dl.pandyahomelab.com/health            # MLflow OK
sudo docker ps | grep -E "dl-mnist-cnn|dl-mlflow|pandya-nginx" # all healthy
git status                                                     # clean
git log --oneline -1                                           # f653796 (or later)
```

---

## Phase 2b.1 — Branch + scaffold

```bash
cd /volume1/pandya-homelab
git checkout -b dl-lstm-forecast/scaffold
cp -r ml/_templates/ml-project-template/ dl/dl-lstm-forecast/
cd dl/dl-lstm-forecast/
# Hyphen-to-underscore symlinks (Python importability)
ln -s db-logic db_logic
ln -s application-logic application_logic
ln -s presentation-logic presentation_logic
```

Customize template metadata:
- `pyproject.toml` → name = `dl-lstm-forecast`
- `Makefile` → PROJECT_NAME, DOCKER_IMAGE
- `README.md` → project blurb, dataset, model, Phase 2b context
- `CHANGELOG.md` → `[1.0.0-alpha1] — 2026-05-25` scaffold entry + roadmap of pending sub-phases

Template layer code (iris-flavored loaders/classifier/etc.) is **left in place**; it gets wholesale-replaced in 2b.2 / 2b.3 / 2b.4. Matches the 2a.2 pattern — keeps the scaffold commit tightly scoped to "metadata customized" and each subsequent sub-phase commit tightly scoped to "this layer's real implementation lands."

**Commit:** `feat(dl-lstm-forecast): scaffold project from template (V3-aligned dl/ path)`

---

## Phase 2b.2 — db-logic

Files:
- `db-logic/scripts/build_dataset.py` — downloads recent CitiBike monthly trip-data zips, sums trips per day across all stations, writes `db-logic/data/bike_share_daily.csv` with columns `date, ride_count`. Run once locally, commit the CSV. Idempotent (skips already-downloaded months).
- `db-logic/loaders/bike_share_loader.py` — `load_daily_counts() -> pd.DataFrame`, `train_val_test_split(df, val_days=90, test_days=180) -> (train, val, test)` (time-respecting split, no shuffling).
- `db-logic/transforms/windowing.py` — `make_windows(series, window_size, horizon=1) -> (X, y)` sliding-window arrays; `StandardScaler` wrapper that fits on train only.
- `tests/db_logic/test_loader.py`, `test_windowing.py` — tiny-subset fixtures so suite stays fast.

**Design points:**
- Window size = 28 days (4 weeks → captures weekly seasonality + recent trend). Configurable via `configs/training.yaml`.
- Scaler fit on train, applied to val/test — locked early so the same scaler is used at inference.
- Loader exposes `get_last_window()` for inference (current trailing N days as starting state).

**Commit:** `feat(dl-lstm-forecast): db-logic — CitiBike daily loader + sliding-window transforms + tests`

---

## Phase 2b.3 — application-logic

Files:
- `application-logic/models/lstm_forecaster.py` — `LSTMForecaster(nn.Module)` with `nn.LSTM(input_size=1, hidden_size=64, num_layers=1, dropout=0.2)` + linear head. Dropout stays on at inference for MC Dropout.
- `application-logic/services/prediction_service.py` — eager warm-up via FastAPI lifespan (copy shape from `dl/dl-mnist-cnn/application-logic/services/prediction_service.py`), `threading.Lock` around `train()`, `forecast(anchor_date, horizon=14, n_samples=30)` does autoregressive rollout under MC Dropout, returns mean + lower/upper band per step.
- MLflow logging: experiment name `dl-lstm-forecast`, params (window_size, hidden, dropout, lr, epochs, horizon), metrics (train_loss, val_loss, test_mape, test_rmse). Capture `run_id` before `log_model` (per `mlflow_operational_lessons`).
- Tests: tiny fixture (50-day synthetic series, 3 epochs) so suite runs in ~30s. Verify shape contracts, MC-sample variance > 0, autoregressive rollout produces 14 steps.

**Design points:**
- Training: Adam(lr=1e-3), MSE loss, ~50 epochs with early-stopping on val loss (patience=5).
- MC Dropout: at inference, set `model.train()` for dropout layers only (or use `enable_dropout(model)` helper) — keep BatchNorm in eval mode (but our model has none). N=30 samples per autoregressive step is the visible CPU cost.
- Forecast band: per step, take mean of 30 samples = forecast; ±2σ = band edges.
- **Cloudflare 100s ceiling check:** worst-case `/predict` = 30 samples × 14 steps × ~5ms per LSTM forward = ~2s. Comfortable margin. Training runs only in the warm-up thread, never on the request path.

**Commit:** `feat(dl-lstm-forecast): application-logic — LSTMForecaster + MC-Dropout autoregressive forecast + MLflow logging + tests`

---

## Phase 2b.4 — presentation-logic

Files:
- `presentation-logic/api/main.py` — FastAPI app with lifespan handler that schedules `_eager_warm_up()` via `asyncio.create_task(asyncio.to_thread(service.train))`. `print(..., flush=True)` for lifecycle log (uvicorn root logger gotcha — see `phase_2a_complete`).
- `presentation-logic/api/routes.py` — `/predict` POST (body: `{anchor_date, horizon}`, default horizon=14), `/model-info` GET (returns placeholder if not trained, avoids Cloudflare 524), `/health` GET, `/` GET (serves `ui.html`).
- `presentation-logic/api/schemas.py` — `PredictRequest`, `PredictResponse {anchor_date, horizon, points: [{day_offset, date, mean, lower, upper, actual?}]}`.
- `presentation-logic/api/ui.html` — Chart.js setup:
  - Historical series line (full series)
  - Forecast line (14 dates after anchor) overlaid with shaded confidence band
  - When anchor is historical: separate "actuals over forecast window" line for direct visual compare
  - Sample-forecast button (anchors to a sensible default — e.g., a recent date with strong seasonal signal)
  - Date picker for the anchor; clamped to `[first_date + window_size, last_date]`
  - About drawer (drives off `about.json` with live `{{tokens}}` for metrics)
  - One-line `<script src="/feedback-widget.js"></script>` before `</body>`
- `presentation-logic/api/about.json` — Project Summary, Dataset, Architecture (Mermaid), Training, Metrics (live tokens), Code Walkthrough, Author/Credits, Learn More.
- Tests: autouse `pretrained_service` fixture monkey-patches `routes._service` (same pattern as 2a). 14 routes tests minimum.

**Pinned versions** (carried over from 2a — known compatible):
- `httpx<0.28` (FastAPI TestClient + starlette 0.27 compat)
- `pydantic==2.5.0` with `protected_namespaces=()` on any `model_*` field schema

**Commit:** `feat(dl-lstm-forecast): presentation-logic — Chart.js forecast UI + REST API + About drawer + tests`

---

## Phase 2b.5 — Dockerfile + requirements + .dockerignore

- `docker/Dockerfile` — `python:3.10-slim` base, PyTorch CPU wheels (use 2a's Dockerfile as template — same wheel index, same pip flags). `COPY db-logic/data/bike_share_daily.csv` baked in.
- `requirements.txt` — pinned: torch 2.1.1+cpu, pandas, numpy, scikit-learn (for scaler), mlflow, fastapi, uvicorn, httpx<0.28, pydantic==2.5.0.
- `requirements-dev.txt` — pytest, pytest-asyncio, pre-existing dev pins.
- **`.dockerignore` excluding `.venv/`** — non-negotiable; bug bit Phase 2a (960 MB → 205 kB context). Ship from day one.

**Commit:** `feat(dl-lstm-forecast): Dockerfile + requirements + .dockerignore`

---

## Phase 2b.6 — Compose + Nginx

- Add `dl-lstm-forecast` block to [deployment/dl/docker-compose.dev.yml](deployment/dl/docker-compose.dev.yml):
  - Image `dl-lstm-forecast:latest`
  - IP `172.21.0.11`, host port `8011:8000`
  - Env: `MLFLOW_TRACKING_URI=http://dl-mlflow:5000`
  - Attaches to `dl_dl-network` only (no ml-network)
  - Healthcheck hitting `/health`
- Add upstream + location to [deployment/nginx/nginx.conf](deployment/nginx/nginx.conf):
  - `upstream dl_lstm { server dl-lstm-forecast:8000; }`
  - `location /dl/lstm-forecast/ { proxy_pass http://dl_lstm/; ... }` with the same proxy headers + 600s timeouts as 2a (paranoid against warm-up edge cases, even though forecasts are fast).
- **Critical:** upstream block must NOT exist before the container exists (Nginx eagerly resolves upstream hostnames at startup — `phase_2a_complete` lesson). Order: container up first, then nginx rebuild + recreate.
- Rebuild pandya-nginx image (nginx.conf is baked — `deployment_image_rebuild_rules`).

**Commit:** `feat(dl-lstm-forecast): wire into dl-network + Nginx routing`

---

## Phase 2b.7 — Build + deploy + verify

```bash
# Build demo image (user runs on NAS)
cd /volume1/pandya-homelab
sudo docker build --no-cache -f dl/dl-lstm-forecast/docker/Dockerfile \
  -t dl-lstm-forecast:latest dl/dl-lstm-forecast/

# Bring up demo (container exists before Nginx upstream resolves it)
sudo docker compose \
  -f deployment/dl/docker-compose.yml \
  -f deployment/dl/docker-compose.dev.yml \
  up -d dl-lstm-forecast

# Wait for warm-up (watch logs for "Eager warm-up complete")
sudo docker logs -f dl-lstm-forecast

# Rebuild and recreate Nginx (nginx.conf baked)
sudo docker build -f deployment/nginx/Dockerfile -t pandya-nginx:latest deployment/nginx/
sudo docker compose -f deployment/nginx/docker-compose.yml up -d --force-recreate pandya-nginx
sudo docker exec pandya-nginx nginx -s reload    # skip max_fails cooldown
```

Verify:
- `curl -k https://localhost:8443/dl/lstm-forecast/health` → 200
- Open `https://pandyahomelab.com/dl/lstm-forecast/` in browser → UI loads, sample-forecast button works, anchor-date picker works, confidence band visible
- `https://mlflow-dl.pandyahomelab.com/` → new `dl-lstm-forecast` experiment with first run
- About drawer renders with live metric tokens
- Feedback widget visible at page bottom
- `https://pandyahomelab.com/dl/mnist-cnn/` still works (no regression)

**Commit:** `feat(dl-lstm-forecast): build + deploy + verify end-to-end`

---

## Phase 2b.8 — Landing page flip

Edit `website/index.html`:
- LSTM card: `status-planned` → `status-live`, `proj-link-disabled` → `<a href="/dl/lstm-forecast/">`
- DL section count: `1 live · 2 planned` → `2 live · 1 planned`

(Static HTML is bind-mounted under `/var/www/html:ro` per `deployment_image_rebuild_rules` — no rebuild needed; hard-refresh confirms.)

**Commit:** `feat(website): mark dl-lstm-forecast as live on landing page (Phase 2b.8)` **← tag v.dl-lstm-forecast-1.0.0 here**

---

## Phase 2b.9 — Merge + tag

```bash
git checkout main
git merge --no-ff dl-lstm-forecast/scaffold
git tag -a v.dl-lstm-forecast-1.0.0 -m "Phase 2b — LSTM time-series forecaster"
git push origin main
git push origin v.dl-lstm-forecast-1.0.0
```

---

## Sub-phase exit criteria (inherited from Phase 2 Master Plan)

- [ ] Model trains to documented target metric (MAPE ≤ 15% on test window)
- [ ] All TIER 1 tests pass
- [ ] Docker image builds cleanly
- [ ] `https://pandyahomelab.com/dl/lstm-forecast/` loads the demo UI
- [ ] Predict round-trip works in the browser (with confidence band visible)
- [ ] MLflow experiment visible at `https://mlflow-dl.pandyahomelab.com/`
- [ ] About drawer renders with live metrics
- [ ] Feedback widget appears at the bottom of the page
- [ ] Landing page card marked Live, route active
- [ ] Branch merged to `main`, tagged `v.dl-lstm-forecast-1.0.0`

---

## Sanity checks before starting 2b.1

- `.11` is free on `dl-network` (only `.10` = dl-mnist-cnn so far) ✅
- Host port `8011` unused on NAS ✅
- Dataset baked into image — confirmed < 10 MB once aggregated; `db-logic/data/` ships with the repo

---

## What this plan does NOT commit to

- Exact CitiBike year-range (decide in 2b.2 when looking at file sizes — aim for 2021–2024 or similar 3-year window).
- Exact early-stopping patience / final epoch count — tune in 2b.3 based on val-loss curves.
- Whether "compare to actuals" overlay defaults to on or off in the UI — decide in 2b.4 based on visual clarity.
