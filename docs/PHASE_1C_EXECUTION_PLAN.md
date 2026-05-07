# Phase 1c Execution Plan — MLflow Tracking

**Objective:** Wire MLflow experiment tracking into both ML projects, add `/model-info` endpoint, and show a Model Card with a "View in MLflow →" link on each demo UI.

**Branch:** `mlops/mlflow-tracking`  
**Tag:** `v.mlflow-tracking-1.0.0`

All infrastructure is already running:
- MLflow healthy at `http://ml-mlflow:5000` (internal) / `https://pandyahomelab.com/mlflow/`
- MinIO bucket `ml-artifacts` exists
- Both ML project containers on `ml-network` (can reach `ml-mlflow:5000`)

Follow top-to-bottom without deviation.

---

## Pre-Flight Check

```bash
curl http://localhost:5000/health          # Expected: OK
curl http://localhost:5000/api/2.0/mlflow/experiments/list  # Expected: JSON with experiments
curl -k https://localhost:8443/mlflow/health  # Expected: OK through Nginx
```

---

## Phase 1c.1 — Wire MLFLOW_TRACKING_URI into docker-compose.dev.yml

Both project containers need `MLFLOW_TRACKING_URI` so the mlflow client knows where to log.
Also add `ml-mlflow` as a `depends_on` so projects wait for MLflow to be healthy.

**`deployment/ml/docker-compose.dev.yml`** — add to BOTH ml-iris-knn and ml-housing-linear:
```yaml
environment:
  PYTHONPATH: /app
  MLFLOW_TRACKING_URI: http://ml-mlflow:5000
depends_on:
  ml-mlflow:
    condition: service_healthy
```

```bash
git commit -m "feat(deployment): add MLFLOW_TRACKING_URI to project containers"
```

---

## Phase 1c.2 — MLflow tracking in ml-iris-knn

### Files to update:

**`application-logic/services/prediction_service.py`**
- `import mlflow, mlflow.sklearn, os`
- Set tracking URI + experiment name at module level
- Wrap `train()` with `mlflow.start_run()`
- Log params: `n_neighbors`, `algorithm`, `dataset`, `n_samples`, `n_features`, `test_size`
- Log metrics: `accuracy`, `precision_macro`, `recall_macro`, `f1_macro`
- Log model: `mlflow.sklearn.log_model(self._classifier._model, "model")`
- Store `run_id` and `experiment_id` on self after training
- Add `get_model_info() -> Dict` method

**`presentation-logic/api/schemas.py`**
- Add `ModelInfoResponse` schema

**`presentation-logic/api/routes.py`**
- Add `GET /model-info` endpoint

**`presentation-logic/api/ui.html`**
- Add Model Card section (loads on page load via fetch to `/ml/iris-knn/model-info`)
- Shows: model type, dataset, accuracy, parameters
- "View in MLflow →" button linking to `/mlflow/#/experiments/{id}/runs/{run_id}`

### Tests:
- `test_model_info_returns_200`
- `test_model_info_has_run_id`
- `test_model_info_has_metrics`

```bash
git commit -m "feat(mlflow): add experiment tracking to ml-iris-knn"
```

---

## Phase 1c.3 — MLflow tracking in ml-housing-linear

### Same pattern as iris-knn:

**`application-logic/services/prediction_service.py`**
- Log params: `model`, `dataset`, `n_samples`, `n_features`, `test_size`, `random_state`
- Log metrics: `rmse`, `mae`, `r2`
- Log model: `mlflow.sklearn.log_model(self._regressor._model, "model")`

**`presentation-logic/api/ui.html`**
- Add Model Card: shows RMSE, MAE, R², dataset info
- "View in MLflow →" button

### Tests:
- `test_model_info_returns_200`
- `test_model_info_has_run_id`
- `test_model_info_has_r2`

```bash
git commit -m "feat(mlflow): add experiment tracking to ml-housing-linear"
```

---

## Phase 1c.4 — Docker rebuild both images

```bash
cd /volume1/pandya-homelab/ml/ml-iris-knn
sudo docker build -f docker/Dockerfile -t ml-iris-knn:latest .

cd /volume1/pandya-homelab/ml/ml-housing-linear
sudo docker build -f docker/Dockerfile -t ml-housing-linear:latest .
```

Both need `mlflow` added to `requirements.txt`.

---

## Phase 1c.5 — Deploy and verify

```bash
cd /volume1/pandya-homelab/deployment/ml/
sudo docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
sleep 30

# Trigger training (first predict call logs the MLflow run)
curl -k -X POST https://localhost:8443/ml/iris-knn/predict \
  -H "Content-Type: application/json" \
  -d '{"data": [5.1, 3.5, 1.4, 0.2]}'

curl -k -X POST https://localhost:8443/ml/housing-linear/predict \
  -H "Content-Type: application/json" \
  -d '{"data": [8.3252, 41.0, 6.984, 1.024, 322.0, 2.556, 37.88, -122.23]}'

# Verify model-info endpoints
curl -k https://localhost:8443/ml/iris-knn/model-info
curl -k https://localhost:8443/ml/housing-linear/model-info

# Verify runs appear in MLflow
curl http://localhost:5000/api/2.0/mlflow/experiments/list
```

Expected: two experiments (`ml-iris-knn`, `ml-housing-linear`) each with one run.

```bash
git commit -m "feat(deployment): deploy MLflow-tracked versions of both ML projects"
```

---

## Phase 1c.6 — Merge & Tag

```bash
git checkout main
git merge --ff-only mlops/mlflow-tracking
git tag v.mlflow-tracking-1.0.0 -m "Phase 1c: MLflow tracking wired into iris-knn and housing-linear"
```

---

## Exit Criteria — Phase 1c Complete

- [ ] Both projects log runs to MLflow on `train()`
- [ ] `/model-info` returns run_id, parameters, metrics, mlflow_url
- [ ] Demo UIs show Model Card with metrics + "View in MLflow →" link
- [ ] MLflow UI at `https://pandyahomelab.com/mlflow/` shows 2 experiments with runs
- [ ] Artifacts (model files) stored in MinIO `ml-artifacts` bucket
- [ ] Merged to main, tagged `v.mlflow-tracking-1.0.0`

---

## MLflow Experiment Structure

| Experiment | Parameters | Metrics | Artifact |
|---|---|---|---|
| ml-iris-knn | n_neighbors=3, dataset=iris, n_samples=150 | accuracy, precision, recall, f1 | sklearn KNeighborsClassifier |
| ml-housing-linear | model=LinearRegression, dataset=california_housing, n_samples=20640 | rmse, mae, r2 | sklearn LinearRegression |
