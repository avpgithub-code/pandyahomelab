# Phase 1e Execution Plan — ml-housing-automl

**Objective:** AutoML regressor on California Housing dataset — compare 5+ algorithms, auto-tune best model, deploy via PyCaret  
**URL:** `https://pandyahomelab.com/ml/housing-automl/`  
**Port:** 8004 (host) → 8000 (container)  
**IP:** 172.20.0.13 (ml-network — ADR-016 compliant)  
**Tag:** `v.ml-housing-automl-1.0.0`

**Model:** PyCaret AutoML — best regressor auto-selected by RMSE  
**Dataset:** California Housing (20,640 rows) — persisted to PostgreSQL on first load  
**Bonus:** Side-by-side comparison vs Phase 1b `ml-housing-linear` baseline in the UI  
**Pydantic:** Full v2 — same patterns as Phase 1d  
**MLflow:** Auto-logged via PyCaret — all algorithm runs, tuning trials, plots, artifacts

Phase 1d must be complete before starting Phase 1e (shares same pattern, PostgreSQL already proven).

---

## Pre-Flight Check

```bash
curl -k https://localhost:8443/ml/titanic-automl/health   # Phase 1d must be live
curl http://localhost:5000/health                          # MLflow: OK
sudo docker ps | grep ml-postgres                         # postgres healthy
```

---

## Phase 1e.1 — Project Scaffolding

```bash
cd /volume1/pandya-homelab
git checkout -b ml-housing-automl/scaffold

cp -r ml/_templates/ml-project-template/ ml/ml-housing-automl/
cd ml/ml-housing-automl/
ln -s db-logic db_logic
ln -s application-logic application_logic
ln -s presentation-logic presentation_logic
```

Update metadata:

**pyproject.toml:**
```toml
name = "ml-housing-automl"
version = "1.0.0-alpha1"
description = "AutoML regressor on California Housing — PyCaret compares 5+ algorithms"
```

**README.md:** Replace "ML Project Template" → "ML Housing AutoML Regressor"  
**CHANGELOG.md:** Add v1.0.0-alpha1 entry

```bash
git commit -m "scaffold(ml-housing-automl): initialize from ml-project-template"
```

---

## Phase 1e.2 — DB Logic Layer

**Dataset:** California Housing via sklearn (`fetch_california_housing`)  
**Persistence:** PostgreSQL (ml-postgres, same as Phase 1d pattern)  
**Note:** Same 8 features as Phase 1b but now stored in DB and run through AutoML

### `db-logic/loaders/loaders.py`

```python
import pandas as pd
from sklearn.datasets import fetch_california_housing
from sqlalchemy import create_engine, text
from sklearn.model_selection import train_test_split
from typing import Tuple
import os

class LocalDataLoader:
    TABLE_NAME = "california_housing"
    FEATURE_COLS = ["MedInc", "HouseAge", "AveRooms", "AveBedrms",
                    "Population", "AveOccup", "Latitude", "Longitude"]
    TARGET_COL = "MedHouseVal"

    def __init__(self):
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:ml_postgres_dev_password@ml-postgres:5432/mldb"
        )
        self._engine = create_engine(db_url)

    def load(self) -> pd.DataFrame:
        if self._table_exists():
            return pd.read_sql(f"SELECT * FROM {self.TABLE_NAME}", self._engine)
        return self._download_and_persist()

    def _download_and_persist(self) -> pd.DataFrame:
        data = fetch_california_housing(as_frame=True)
        df = data.frame
        df.to_sql(self.TABLE_NAME, self._engine, if_exists="replace", index=False)
        return df

    def _table_exists(self) -> bool:
        with self._engine.connect() as conn:
            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_name = :t)"
            ), {"t": self.TABLE_NAME})
            return result.scalar()

    def get_feature_names(self):
        return self.FEATURE_COLS

    def split(self, df, test_size=0.2, random_state=42):
        X = df[self.FEATURE_COLS]
        y = df[self.TARGET_COL]
        return train_test_split(X, y, test_size=test_size, random_state=random_state)
```

### Tests (`tests/db/test_loaders.py`)
- `test_load_returns_dataframe`
- `test_correct_columns` (8 features + target)
- `test_row_count` (20,640 rows)
- `test_no_nulls`

```bash
python3 -m pytest tests/db/ -v
git commit -m "feat(db-logic): implement California Housing loader with PostgreSQL persistence"
```

---

## Phase 1e.3 — Application Logic Layer

**Algorithms compared:** Linear Regression, Ridge, Lasso, Random Forest, XGBoost, LightGBM, ElasticNet  
**Tuning:** `tune_model()` on top performer — optimized for RMSE  
**Bonus metric:** Compare best AutoML RMSE vs Phase 1b baseline (0.7456) to show improvement

### `application-logic/services/prediction_service.py`

```python
import os
import logging
import pandas as pd
from typing import Dict, List, Optional

from db_logic.loaders.loaders import LocalDataLoader

logger = logging.getLogger(__name__)

_MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://ml-mlflow:5000")
_EXPERIMENT = "ml-housing-automl"
_BASELINE_RMSE = 0.7456   # Phase 1b ml-housing-linear baseline


class PredictionService:
    def __init__(self):
        self._loader = LocalDataLoader()
        self._model = None
        self._leaderboard = None
        self._best_model_name = None
        self._metrics: Dict = {}
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False

    def train(self) -> Dict:
        from pycaret.regression import (
            setup, compare_models, tune_model,
            finalize_model, pull
        )
        import mlflow

        df = self._loader.load()
        mlflow.set_tracking_uri(_MLFLOW_URI)

        setup(
            data=df,
            target="MedHouseVal",
            session_id=42,
            log_experiment=True,
            experiment_name=_EXPERIMENT,
            log_plots=True,
            verbose=False,
            html=False,
        )

        top_models = compare_models(n_select=5, sort="RMSE", verbose=False)
        leaderboard_df = pull()
        self._leaderboard = leaderboard_df.head(5).to_dict(orient="records")

        tuned = tune_model(top_models[0], optimize="RMSE", verbose=False)
        self._best_model_name = type(tuned).__name__
        self._model = finalize_model(tuned)

        best_row = leaderboard_df.iloc[0]
        self._metrics = {
            "rmse":          round(float(best_row.get("RMSE", 0)), 4),
            "mae":           round(float(best_row.get("MAE", 0)), 4),
            "r2":            round(float(best_row.get("R2", 0)), 4),
            "baseline_rmse": _BASELINE_RMSE,
            "improvement":   round(_BASELINE_RMSE - float(best_row.get("RMSE", 0)), 4),
        }
        self._ready = True

        try:
            run = mlflow.last_active_run()
            if run:
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
        except Exception as e:
            logger.warning(f"MLflow run_id capture skipped: {e}")

        return self._metrics

    def predict(self, features: Dict) -> Dict:
        if not self._ready:
            self.train()
        from pycaret.regression import predict_model
        X = pd.DataFrame([features])
        result = predict_model(self._model, data=X, verbose=False)
        value = round(float(result["prediction_label"].iloc[0]), 4)
        return {
            "prediction":      value,
            "prediction_usd":  f"${value * 100_000:,.0f}",
            "unit":            "$100,000s",
        }

    def get_model_info(self) -> Dict:
        if not self._ready:
            self.train()
        return {
            "model_type":          "AutoML Regressor",
            "best_model":          self._best_model_name,
            "dataset":             "California Housing",
            "n_samples":           20640,
            "n_features":          8,
            "algorithms_compared": 5,
            "optimized_for":       "RMSE",
            "leaderboard":         self._leaderboard,
            "metrics":             self._metrics,
            "run_id":              self._run_id,
            "experiment_id":       self._experiment_id,
            "mlflow_url": (
                f"/mlflow/#/experiments/{self._experiment_id}/runs/{self._run_id}"
                if self._run_id else None
            ),
        }

    @property
    def is_ready(self) -> bool:
        return self._ready
```

### Tests (`tests/application/test_regressor.py`)
- `test_predict_returns_positive_value`
- `test_predict_returns_usd_string`
- `test_rmse_below_baseline` (RMSE < 0.7456 — AutoML beats Phase 1b)
- `test_leaderboard_has_multiple_models`
- `test_predict_without_train_raises`

```bash
python3 -m pytest tests/application/ -v   # slow — trains AutoML
git commit -m "feat(application-logic): implement PyCaret AutoML regressor"
```

---

## Phase 1e.4 — Presentation Logic Layer

### Schemas (Full Pydantic v2)

```python
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Annotated, Dict, List, Literal, Optional

class PredictionRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    med_inc:    Annotated[float, Field(gt=0,     le=20,    description="Median income")]
    house_age:  Annotated[float, Field(ge=1,     le=52,    description="House age (years)")]
    ave_rooms:  Annotated[float, Field(ge=1,     le=15,    description="Avg rooms per household")]
    ave_bedrms: Annotated[float, Field(ge=0.5,   le=5,     description="Avg bedrooms per household")]
    population: Annotated[int,   Field(ge=3,     le=35000, description="Block population")]
    ave_occup:  Annotated[float, Field(ge=1,     le=10,    description="Avg household occupancy")]
    latitude:   Annotated[float, Field(ge=32.5,  le=42.0,  description="Latitude")]
    longitude:  Annotated[float, Field(ge=-124.4, le=-114.3, description="Longitude")]

    @field_validator("med_inc", "house_age", "ave_rooms", "ave_bedrms", "ave_occup", mode="before")
    @classmethod
    def round_to_two_decimals(cls, v):
        return round(float(v), 2)

    @model_validator(mode="after")
    def validate_geographic_bounds(self):
        if self.latitude < 34.0 and self.longitude > -116.0:
            raise ValueError("Coordinates appear outside California bounds")
        return self


class PredictionResponse(BaseModel):
    prediction:     float
    prediction_usd: str
    unit:           str
    request_id:     Optional[str] = None


class ModelInfoResponse(BaseModel):
    model_type:          str
    best_model:          str
    dataset:             str
    n_samples:           int
    n_features:          int
    algorithms_compared: int
    optimized_for:       str
    leaderboard:         List[Dict]
    metrics:             Dict
    run_id:              Optional[str] = None
    experiment_id:       Optional[str] = None
    mlflow_url:          Optional[str] = None
```

### Demo UI (`presentation-logic/api/ui.html`)
- Dark theme matching existing demos
- **Leaderboard table** — top 5 regressors ranked by RMSE. Best model highlighted.
- **Baseline comparison banner** — "AutoML RMSE: 0.52 vs Linear Baseline: 0.75 — 30% improvement"
- **Input sliders** — same 8 features as Phase 1b housing-linear
- **Prediction result** — house price in USD (large, green)
- **Model Card** — best model name, metrics, "View in MLflow →" button
- Example locations: "San Francisco Bay", "Los Angeles", "Central Valley"
- `fetch()` calls `/ml/housing-automl/predict`
- Model Card loads from `/ml/housing-automl/model-info` on page load

### Tests (`tests/presentation/test_routes.py`)
- `test_health_returns_200`
- `test_predict_returns_200`
- `test_predict_invalid_latitude_returns_422`
- `test_predict_out_of_bounds_california_returns_422`
- `test_predict_returns_positive_usd`
- `test_model_info_returns_200`
- `test_model_info_has_leaderboard`

```bash
python3 -m pytest tests/ -v
git commit -m "feat(presentation-logic): implement /predict and /model-info with Pydantic v2"
```

---

## Phase 1e.5 — Docker Build

### `requirements.txt`

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pycaret[full]==3.3.1
scikit-learn==1.3.2
numpy==1.26.3
pandas==2.1.4
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
mlflow>=2.10.0
boto3>=1.26.0
```

Identical to Phase 1d — Docker layer cache will be reused. Build is fast.

```bash
cd /volume1/pandya-homelab/ml/ml-housing-automl
sudo docker build -f docker/Dockerfile -t ml-housing-automl:latest .

sudo docker run -d -p 8004:8000 \
  -e DATABASE_URL="postgresql://postgres:ml_postgres_dev_password@host.docker.internal:5433/mldb" \
  --name ml-housing-automl ml-housing-automl:latest

sleep 30
curl http://localhost:8004/health
curl -X POST http://localhost:8004/predict \
  -H "Content-Type: application/json" \
  -d '{"med_inc":8.33,"house_age":41,"ave_rooms":6.98,"ave_bedrms":1.02,"population":322,"ave_occup":2.56,"latitude":37.88,"longitude":-122.23}'

sudo docker stop ml-housing-automl && sudo docker rm ml-housing-automl
git commit -m "build(docker): finalize Dockerfile for ml-housing-automl"
```

---

## Phase 1e.6 — Integration

### Step 1: Add to `deployment/ml/docker-compose.dev.yml`

```yaml
ml-housing-automl:
  image: ml-housing-automl:latest
  container_name: ml-housing-automl
  environment:
    PYTHONPATH: /app
    MLFLOW_TRACKING_URI: http://ml-mlflow:5000
    DATABASE_URL: postgresql://postgres:${ML_POSTGRES_PASSWORD}@ml-postgres:5432/mldb
  ports:
    - "8004:8000"
  networks:
    ml-network:
      ipv4_address: 172.20.0.13
  depends_on:
    ml-postgres:
      condition: service_healthy
    ml-redis:
      condition: service_healthy
    ml-mlflow:
      condition: service_healthy
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
    interval: 10s
    timeout: 5s
    retries: 5
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

### Step 2: Add Nginx upstream + location

In `deployment/nginx/nginx.conf`:

```nginx
upstream ml_housing_automl {
    server ml-housing-automl:8000 max_fails=3 fail_timeout=30s;
}

location /ml/housing-automl/ {
    proxy_pass http://ml_housing_automl/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 30s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
}

# Update /ml/ listing
location = /ml/ {
    return 200 '{"domain":"ml","projects":["iris-knn","housing-linear","titanic-automl","housing-automl"],"status":"active"}';
    add_header Content-Type application/json;
}
```

### Step 3: Deploy and verify

```bash
cd /volume1/pandya-homelab/deployment/ml/
sudo docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

cd ../nginx/
sudo docker-compose down
sudo docker build -t pandya-nginx:latest .
sudo docker-compose up -d
sleep 10

curl -k https://localhost:8443/ml/housing-automl/health
curl -k -X POST https://localhost:8443/ml/housing-automl/predict \
  -H "Content-Type: application/json" \
  -d '{"med_inc":8.33,"house_age":41,"ave_rooms":6.98,"ave_bedrms":1.02,"population":322,"ave_occup":2.56,"latitude":37.88,"longitude":-122.23}'
```

```bash
git commit -m "feat(deployment): wire ml-housing-automl into ml-network with Nginx routing"
```

---

## Phase 1e.7 — Landing Page Update

In `website/index.html`:
- Add AutoML Regressor card (fourth ML card)
- Replace existing "Planned" slot or add new card
- `status-live` class
- Route: `/ml/housing-automl/`
- Update domain count: `3 live · 1 planned` → `4 live · 0 planned`
- Domain now complete — no planned items remaining

```bash
git commit -m "feat(website): add ml-housing-automl as live — ML domain complete"
```

---

## Phase 1e.8 — Merge & Tag

```bash
cd /volume1/pandya-homelab
git log main..HEAD --oneline
git checkout main
git merge --ff-only ml-housing-automl/scaffold
git tag v.ml-housing-automl-1.0.0 -m "ml-housing-automl: PyCaret AutoML regressor, ML domain complete"
git log --oneline | head -5
```

---

## Exit Criteria — Phase 1e Complete (ML Domain Complete)

- [ ] All tests passing (TIER 1)
- [ ] AutoML RMSE < 0.7456 (beats Phase 1b baseline)
- [ ] Docker image builds cleanly
- [ ] `https://pandyahomelab.com/ml/housing-automl/` loads with leaderboard
- [ ] Baseline comparison banner shows improvement over Phase 1b
- [ ] MLflow shows `ml-housing-automl` experiment with 5+ algorithm runs
- [ ] PostgreSQL has `california_housing` table
- [ ] Pydantic v2 validates California geographic bounds
- [ ] Landing page shows 4 live ML projects, 0 planned
- [ ] Merged to main, tagged `v.ml-housing-automl-1.0.0`

---

## Final ML Domain IP/Port Reference Card

| Service | IP | Host Port | URL |
|---|---|---|---|
| ml-postgres | 172.20.0.2 | 5433 | — |
| ml-minio | 172.20.0.3 | 9000 | — |
| ml-redis | 172.20.0.4 | 6379 | — |
| ml-mlflow | 172.20.0.5 | 5000 | /mlflow/ |
| ml-iris-knn | 172.20.0.10 | 8001 | /ml/iris-knn/ |
| ml-housing-linear | 172.20.0.11 | 8002 | /ml/housing-linear/ |
| ml-titanic-automl | 172.20.0.12 | 8003 | /ml/titanic-automl/ |
| **ml-housing-automl** | **172.20.0.13** | **8004** | **/ml/housing-automl/** |
| Nginx on ml-net | 172.20.0.20 | — | proxy |

**ML Domain: 4 projects · 0 planned · COMPLETE**  
**Next: Phase 2a — DL Domain (dl-mnist-cnn)**
