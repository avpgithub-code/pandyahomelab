# Phase 1b Execution Plan — ml-housing-linear

**Objective:** Build ml-housing-linear (linear regression on housing prices)  
**URL:** https://pandyahomelab.com/ml/housing-linear/  
**Port:** 8002 (host) → 8000 (container)  
**IP:** 172.20.0.11 (ml-network)  
**Tag:** v.ml-housing-linear-1.0.0  

All infrastructure conflicts from Phase 1a are already solved.
Follow this plan top-to-bottom without deviation.

---

## Pre-Flight Check

Before starting, verify infrastructure is healthy:

```bash
cd /volume1/pandya-homelab/deployment/ml/
sudo docker-compose ps
```

Expected: ml-postgres, ml-minio, ml-redis all **(healthy)**

```bash
curl -k https://localhost:8443/ml/iris-knn/health
```

Expected: `{"status":"healthy",...}`

If either fails, start infrastructure first:
```bash
sudo docker-compose up -d          # ML infra
cd ../nginx && sudo docker-compose up -d   # Nginx
nohup cloudflared tunnel run pandya-homelab >> ~/cloudflared.log 2>&1 &
```

---

## Phase 1b.1 — Project Scaffolding

```bash
cd /volume1/pandya-homelab
git checkout -b ml-housing-linear/scaffold

cp -r ml/_templates/ml-project-template/ ml/ml-housing-linear/
cd ml/ml-housing-linear/

# Create Python import symlinks (required — folders use hyphens)
ln -s db-logic db_logic
ln -s application-logic application_logic
ln -s presentation-logic presentation_logic
```

Update metadata:

**pyproject.toml:**
```toml
name = "ml-housing-linear"
version = "1.0.0-alpha1"
description = "Housing price prediction using Linear Regression"
```

**README.md:** Replace "ML Project Template" → "ML Housing Linear Regression"

**CHANGELOG.md:** Add v1.0.0-alpha1 entry

```bash
git add .
git commit -m "scaffold(ml-housing-linear): initialize from ml-project-template"
```

---

## Phase 1b.2 — DB Logic Layer

**Dataset:** California Housing (sklearn built-in, ~20,000 rows)  
Features: MedInc, HouseAge, AveRooms, AveBedrms, Population, AveOccup, Latitude, Longitude  
Target: Median house value

### Files to implement:

**`db-logic/loaders/loaders.py`**
```python
from sklearn.datasets import fetch_california_housing
import pandas as pd
from sklearn.model_selection import train_test_split
from typing import Optional, Tuple, List

class LocalDataLoader:
    FEATURE_COLS = ["MedInc","HouseAge","AveRooms","AveBedrms",
                    "Population","AveOccup","Latitude","Longitude"]
    TARGET_COL = "MedHouseVal"

    def load(self) -> pd.DataFrame:
        data = fetch_california_housing(as_frame=True)
        return data.frame

    def get_feature_names(self) -> List[str]:
        return self.FEATURE_COLS

    def split(self, df, test_size=0.2, random_state=42):
        X = df[self.FEATURE_COLS]
        y = df[self.TARGET_COL]
        return train_test_split(X, y, test_size=test_size, random_state=random_state)
```

**`db-logic/transforms/preprocessor.py`** — same StandardScaler pattern as iris-knn

### Tests (`tests/db/test_loaders.py`):
- test_load_returns_dataframe (20640 rows)
- test_correct_columns (8 features + target)
- test_split_shapes
- test_preprocessor_fit_transform_shape
- test_scaled_mean_near_zero

```bash
# Run TIER 1 tests
python3 -m pytest tests/db/ -v
# Expected: all passing
```

```bash
git commit -m "feat(db-logic): implement housing data loader and preprocessor"
```

---

## Phase 1b.3 — Application Logic Layer

**Model:** `sklearn.linear_model.LinearRegression`  
**Metrics:** RMSE, MAE, R² score  

### Files to implement:

**`application-logic/model/classifier.py`** → rename concept to `regressor.py`
```python
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import numpy as np

class HousingRegressor:
    def __init__(self):
        self._model = LinearRegression()
        self._trained = False

    def train(self, X_train, y_train):
        self._model.fit(X_train, y_train)
        self._trained = True
        return self

    def predict(self, X) -> List[float]:
        self._check_trained()
        return self._model.predict(X).tolist()

    def evaluate(self, X_test, y_test) -> Dict:
        y_pred = self._model.predict(X_test)
        return {
            "rmse": round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 4),
            "mae":  round(float(mean_absolute_error(y_test, y_pred)), 4),
            "r2":   round(float(r2_score(y_test, y_pred)), 4),
        }
```

**`application-logic/services/prediction_service.py`**
- Same pattern as iris-knn PredictionService
- Returns: prediction (float), unit ("$100,000s"), metrics

### Tests (`tests/application/test_regressor.py`):
- test_predict_returns_float
- test_predict_positive_value
- test_r2_score_above_threshold (>0.55 for linear regression)
- test_predict_without_train_raises

```bash
python3 -m pytest tests/application/ -v
```

```bash
git commit -m "feat(application-logic): implement housing linear regression and prediction service"
```

---

## Phase 1b.4 — Presentation Logic Layer

### Schemas (`presentation-logic/api/schemas.py`):
```python
class PredictionRequest(BaseModel):
    data: List[float]  # 8 features

    @validator("data")
    def validate_features(cls, v):
        if len(v) != 8:
            raise ValueError("Exactly 8 features required")
        return v

class PredictionResponse(BaseModel):
    prediction: float       # predicted house value
    prediction_usd: str     # human-readable e.g. "$245,000"
    unit: str               # "$100,000s"
    request_id: Optional[str]
```

### Demo UI (`presentation-logic/api/ui.html`):
- 8 sliders for housing features
- Show predicted price in USD
- Match dark theme of iris-knn UI
- fetch() calls `/ml/housing-linear/predict`
- Back link → pandyaHomeLab home

### Tests (`tests/presentation/test_routes.py`):
- test_health_returns_200
- test_predict_returns_200
- test_predict_invalid_features_returns_422 (wrong count)
- test_predict_returns_positive_value

```bash
python3 -m pytest tests/ -v
# Expected: all passing (TIER 1 complete)
```

```bash
git commit -m "feat(presentation-logic): implement /health and /predict endpoints for housing"
```

---

## Phase 1b.5 — TIER 2: Docker Build

**requirements.txt** (keep lean — no torch):
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
scikit-learn==1.3.2
numpy==1.26.3
pandas==2.1.4
```

```bash
cd /volume1/pandya-homelab/ml/ml-housing-linear

sudo docker build -f docker/Dockerfile -t ml-housing-linear:latest .
# Expected: builds cleanly, <600MB

sudo docker run -d -p 8002:8000 --name ml-housing-linear ml-housing-linear:latest
sleep 15

curl http://localhost:8002/health
curl -X POST http://localhost:8002/predict \
  -H "Content-Type: application/json" \
  -d '{"data": [8.3252, 41.0, 6.984, 1.024, 322.0, 2.556, 37.88, -122.23]}'

sudo docker stop ml-housing-linear && sudo docker rm ml-housing-linear
```

Expected:
- `/health` → 200 OK
- `/predict` → predicted value + USD string

```bash
git commit -m "build(docker): finalize Dockerfile for ml-housing-linear"
```

---

## Phase 1b.6 — TIER 3: Integration

### Step 1: Add to docker-compose.dev.yml

```yaml
ml-housing-linear:
  image: ml-housing-linear:latest
  container_name: ml-housing-linear
  environment:
    PYTHONPATH: /app
  ports:
    - "8002:8000"
  networks:
    ml-network:
      ipv4_address: 172.20.0.11
  depends_on:
    ml-postgres:
      condition: service_healthy
    ml-redis:
      condition: service_healthy
    ml-minio:
      condition: service_healthy
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### Step 2: Add Nginx upstream + location

In `deployment/nginx/nginx.conf`, add:

```nginx
# Add upstream (in http block, alongside ml_projects)
upstream ml_housing {
    server ml-housing-linear:8000 max_fails=3 fail_timeout=30s;
}

# Add location block (alongside /ml/iris-knn/)
location /ml/housing-linear/ {
    proxy_pass http://ml_housing/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 30s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}

# Update /ml/ listing
location = /ml/ {
    return 200 '{"domain":"ml","projects":["iris-knn","housing-linear"],"status":"active"}';
    add_header Content-Type application/json;
}
```

### Step 3: Deploy full stack

```bash
# Start housing container
cd /volume1/pandya-homelab/deployment/ml/
sudo docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
sleep 30
sudo docker-compose -f docker-compose.yml -f docker-compose.dev.yml ps

# Rebuild Nginx with new upstream
cd /volume1/pandya-homelab/deployment/nginx/
sudo docker-compose down
sudo docker build -t pandya-nginx:latest .
sudo docker-compose up -d
sleep 10

# Test
curl -k https://localhost:8443/ml/housing-linear/health
curl -k -X POST https://localhost:8443/ml/housing-linear/predict \
  -H "Content-Type: application/json" \
  -d '{"data": [8.3252, 41.0, 6.984, 1.024, 322.0, 2.556, 37.88, -122.23]}'
```

Expected: both return valid responses.

```bash
git commit -m "feat(deployment): wire ml-housing-linear into ml-network with Nginx routing"
```

---

## Phase 1b.7 — Landing Page Update

Update `website/index.html`:
- Change ml-housing card from `status-wip` → `status-live`
- Update route: `/ml/regression` → `/ml/housing-linear/`
- Update link: `proj-link-disabled` → `ml-link` with `href="/ml/housing-linear/"`

```bash
git add website/index.html
git commit -m "feat(website): mark ml-housing-linear as live on landing page"
```

**Purge Cloudflare cache** after deploying (Dashboard → Caching → Purge Everything)

---

## Phase 1b.8 — Merge & Tag

```bash
cd /volume1/pandya-homelab
git log main..HEAD --oneline   # review all commits

git checkout main
git merge --ff-only ml-housing-linear/scaffold

git tag v.ml-housing-linear-1.0.0 -m "ml-housing-linear: linear regression with interactive demo"

git log --oneline | head -5
```

---

## Exit Criteria — Phase 1b Complete

- [ ] 27+ tests passing (all layers)
- [ ] Docker image builds cleanly
- [ ] `https://pandyahomelab.com/ml/housing-linear/` loads demo UI
- [ ] Prediction returns house price in USD
- [ ] Landing page shows both iris-knn and housing-linear as Live
- [ ] Merged to main, tagged v.ml-housing-linear-1.0.0

---

## IP/Port Reference Card (print this)

| Service | Container IP | Host Port | URL Path |
|---|---|---|---|
| Nginx (proxy) | 172.24.0.2 | 8080/8443 | / |
| ml-postgres | 172.20.0.2 | 5433 | — |
| ml-minio | 172.20.0.3 | 9000/9001 | — |
| ml-redis | 172.20.0.4 | 6379 | — |
| ml-mlflow | 172.20.0.5 | 5000 | — |
| ml-iris-knn | 172.20.0.10 | 8001 | /ml/iris-knn/ |
| ml-housing-linear | 172.20.0.11 | 8002 | /ml/housing-linear/ |
| Nginx on ml-net | 172.20.0.20 | — | proxy only |
