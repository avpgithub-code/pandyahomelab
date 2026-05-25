# dl-lstm-forecast

**LSTM time-series forecaster on NYC CitiBike daily ride counts.**

**Phase:** 2b (second DL demo on the pandyaHomeLab platform — first was [dl-mnist-cnn](../dl-mnist-cnn/))
**Live demo:** https://pandyahomelab.com/dl/lstm-forecast/ (pending Phase 2b.8 flip)
**Tracker:** https://mlflow-dl.pandyahomelab.com/ (experiment: `dl-lstm-forecast`)

---

## What it does

A visitor lands on the demo and sees a multi-year chart of daily CitiBike ride counts in NYC. They pick any date on the timeline (or hit the "show me a sample forecast" button) and the server returns a 14-day-ahead forecast with a confidence band. If the anchor date is historical, the actual values for the next 14 days are overlaid so the visitor can directly compare the model's prediction to reality.

## How it works

- **Model:** 1-layer LSTM, hidden=64, dropout=0.2, trained to predict next-day ride count from a 28-day sliding window. Loss = MSE, optimizer = Adam (lr=1e-3), ~50 epochs with early stopping on validation loss.
- **Multi-day forecast:** the 1-step model is rolled out autoregressively — its prediction for day t+1 is fed back as input to predict day t+2, and so on for 14 steps.
- **Confidence band:** at inference, dropout layers are kept on (MC Dropout); the model is queried N=30 times per autoregressive step, yielding mean ± 2σ. The band widens naturally with horizon — accumulated forecast uncertainty made visible.

## Architecture (3-layer)

```
dl/dl-lstm-forecast/
├── presentation-logic/      FastAPI routes + Chart.js UI + About drawer
├── application-logic/       LSTMForecaster (PyTorch) + PredictionService + MLflow logging
├── db-logic/                CitiBike daily CSV loader + sliding-window transforms
├── shared/                  config, logger, metrics (project-local per ADR-013)
├── docker/                  Dockerfile + .dockerignore
├── tests/                   pytest suite (tiny-subset fixtures for fast runs)
├── configs/                 YAML hyperparameters
├── data/                    cleaned daily CSV (baked into image)
├── models/                  checkpoints (gitignored)
└── notebooks/               exploratory analysis
```

Symlinks `application_logic`, `db_logic`, `presentation_logic` exist alongside the hyphenated dirs so Python imports work without renaming.

## Dataset

NYC CitiBike daily ride counts, aggregated from the public [CitiBike trip data](https://citibikenyc.com/system-data). The cleaning script (`db-logic/scripts/build_dataset.py`) downloads multi-year trip-level data, sums trips per day across all stations, and writes `db-logic/data/bike_share_daily.csv` (~1 MB). The CSV is **committed** to the repo so the v1.0.0 image has fixed, reproducible training data.

## Network slot

| dl-network IP | Host port | Container port |
|---|---|---|
| 172.21.0.11 | 8011 | 8000 |

Attaches to `dl_dl-network` only (V3 domain autonomy — no ml-network reach-back). Tracking writes to `dl-mlflow:5000` on the same network; the UI is exposed publicly at `mlflow-dl.pandyahomelab.com`.

## Build & deploy (TIER summary)

| Tier | Command | Pass = |
|---|---|---|
| 1 (code) | `make lint && make test-unit` | All tests green |
| 2 (docker) | `make docker-build && make docker-run` then `curl localhost:8011/health` | 200 OK |
| 3 (integration) | Add to `deployment/dl/docker-compose.dev.yml`, Nginx upstream, deploy | `https://pandyahomelab.com/dl/lstm-forecast/` loads, MLflow run logged |

Full deploy procedure: see [docs/PHASE_2B_EXECUTION_PLAN.md](../../docs/PHASE_2B_EXECUTION_PLAN.md).

## Related

- **Phase 2 Master Plan:** [docs/PHASE_2_MASTER_PLAN.md](../../docs/PHASE_2_MASTER_PLAN.md)
- **Sibling DL demo:** [dl/dl-mnist-cnn/](../dl-mnist-cnn/) (Phase 2a, CNN + canvas drawing UI)
- **ADRs:** ADR-013 (per-project 3-layer), ADR-016 (dl-network topology), ADR-019 (Nginx routing), ADR-020 (3-tier readiness)
