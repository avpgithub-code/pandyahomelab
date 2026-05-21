# Phase 2b Execution Plan — dl-lstm-forecast (Stub)

**Objective:** Build dl-lstm-forecast — LSTM time-series forecaster on a public dataset
**URL:** `https://pandyahomelab.com/dl/lstm-forecast/`
**Port:** 8011 (host) → 8000 (container)
**dl-network IP:** 172.21.0.11
**Tracking:** writes to `dl-mlflow:5000` (no ml-network attachment per V3 domain autonomy)
**Tag at ship:** `v.dl-lstm-forecast-1.0.0`

> This is a **stub** — full step-by-step plan to be authored when 2a ships. The
> sub-phase will follow the same pattern as 2a (see [Phase 2 Master Plan](PHASE_2_MASTER_PLAN.md)).
> Only the **project-specific** decisions are listed here.

---

## Open decisions (need user sign-off before full plan is written)

### Dataset choice
| Option | Pros | Cons |
|---|---|---|
| **Airline passengers** (classic ~144 monthly points) | Tiny, fast iterate, well-known | Too small to be impressive |
| **NYC bike-share daily counts** | Real-world, multi-year, ~1500 points, public | Bigger download, needs cleaning |
| **Stock OHLCV** (e.g., yfinance) | Engaging demo (price next day) | Implies financial advice; needs careful disclaimer |
| **Weather** (NOAA station daily temp) | Honest signal, public, reproducible | Less viscerally interesting |

### Model architecture (starting point)
- 1-layer LSTM, hidden=64, dropout=0.2
- Input: window of N past timesteps → predict next 1 (or next M)
- Loss: MSE
- Optimizer: Adam (lr=1e-3)
- Epochs: ~50, early-stop on val loss

### Demo UI
- Line chart (Chart.js) of historical data
- Visitor picks a date / window → server returns N-step-ahead forecast with a confidence band
- Pre-loaded "show me a sample forecast" button (for visitors who don't want to fiddle)
- About drawer + feedback widget (same pattern as ML demos)

---

## What 2a must have shipped first

Hard preconditions before 2b can be planned in full:
- `dl-network` exists and is healthy
- Nginx is attached to `dl-network` at 172.21.0.20
- `/dl/` returns the live JSON listing (not 503), and `/dl/mnist-cnn/` works end-to-end
- About drawer pattern verified against the PyTorch-based 2a demo (since it's the first non-sklearn About drawer)

---

## Steps (high-level — full plan TBD)

1. Decision: dataset + forecast horizon + UI shape (user sign-off gate)
2. Branch `dl-lstm-forecast/scaffold`; copy `ml/_templates/ml-project-template/` → `ml/dl-lstm-forecast/`
3. db-logic: dataset loader, train/val/test split, window sequencing
4. application-logic: `LSTMForecaster` class + `PredictionService` with MLflow logging
5. presentation-logic: schemas, routes (`/predict`, `/model-info`, `/`, `/health`), `ui.html` with Chart.js
6. Tests across all three layers
7. Dockerfile (reuse 2a's PyTorch CPU base if image-layer caching saves time)
8. `deployment/dl/docker-compose.dev.yml` — add service block
9. Nginx: new upstream + `location /dl/lstm-forecast/` block
10. Rebuild + redeploy (Nginx + new demo); end-to-end verification
11. About drawer JSON, feedback widget `<script>` tag
12. Landing page: flip 2nd DL card to Live
13. Merge + tag

---

## Sanity checks before writing the full plan
- Confirm `.11` is free on `dl-network` (should be — 2a only uses `.10`)
- Confirm host port 8011 is unused on the NAS
- Decide if dataset will be baked into the image, downloaded on container start, or stored in a named volume (dataset size > ~10MB → volume)
