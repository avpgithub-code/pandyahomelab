# Phase 1d Execution Plan — ml-titanic-automl

**Objective:** AutoML classifier on Titanic survival dataset — compare 5+ algorithms, auto-tune best model, deploy via PyCaret  
**URL:** `https://pandyahomelab.com/ml/titanic-automl/`  
**Port:** 8003 (host) → 8000 (container)  
**IP:** 172.20.0.12 (ml-network — ADR-016 compliant)  
**Tag:** `v.ml-titanic-automl-1.0.0`

**Model:** PyCaret AutoML — best classifier auto-selected by AUC  
**Dataset:** Titanic survival (891 rows) — persisted to PostgreSQL on first load  
**Pydantic:** Full v2 patterns — `@field_validator`, `@model_validator`, `Annotated` types, `ConfigDict`  
**MLflow:** Auto-logged via PyCaret — all algorithm runs, tuning trials, plots, artifacts

All infrastructure already running. Follow top-to-bottom without deviation.

---

## Pre-Flight Check

```bash
curl -k https://localhost:8443/ml/iris-knn/health
curl -k https://localhost:8443/ml/housing-linear/health
curl http://localhost:5000/health                     # MLflow: OK
sudo docker ps | grep -E "postgres|mlflow|nginx"      # All healthy
```

---

## Phase 1d.1 — Project Scaffolding

```bash
cd /volume1/pandya-homelab
git checkout -b ml-titanic-automl/scaffold

cp -r ml/_templates/ml-project-template/ ml/ml-titanic-automl/
cd ml/ml-titanic-automl/
ln -s db-logic db_logic
ln -s application-logic application_logic
ln -s presentation-logic presentation_logic
```

Update metadata:

**pyproject.toml:**
```toml
name = "ml-titanic-automl"
version = "1.0.0-alpha1"
description = "AutoML classifier on Titanic survival — PyCaret compares 5+ algorithms"
```

**README.md:** Replace "ML Project Template" → "ML Titanic AutoML Classifier"  
**CHANGELOG.md:** Add v1.0.0-alpha1 entry

```bash
git commit -m "scaffold(ml-titanic-automl): initialize from ml-project-template"
```

---

## Phase 1d.2 — DB Logic Layer

**Dataset:** Titanic survival via seaborn (`sns.load_dataset('titanic')`)  
**Persistence:** PostgreSQL (ml-postgres, already running)  
**Pattern:** Load from DB if table exists, otherwise download and persist

### `db-logic/loaders/loaders.py`

```python
import seaborn as sns
import pandas as pd
from sqlalchemy import create_engine, text
from typing import Tuple
from sklearn.model_selection import train_test_split
import os

class LocalDataLoader:
    TABLE_NAME = "titanic"
    FEATURE_COLS = ["pclass", "sex", "age", "sibsp", "parch", "fare", "embarked"]
    TARGET_COL = "survived"

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
        df = sns.load_dataset("titanic")
        df = self._clean(df)
        df.to_sql(self.TABLE_NAME, self._engine, if_exists="replace", index=False)
        return df

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df[self.FEATURE_COLS + [self.TARGET_COL]].copy()
        df["age"] = df["age"].fillna(df["age"].median())
        df["fare"] = df["fare"].fillna(df["fare"].median())
        df["embarked"] = df["embarked"].fillna("S")
        df = df.dropna()
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
- `test_correct_columns` (7 features + target)
- `test_no_nulls_after_clean`
- `test_survived_is_binary` (0 and 1 only)

```bash
python3 -m pytest tests/db/ -v
git commit -m "feat(db-logic): implement Titanic loader with PostgreSQL persistence"
```

---

## Phase 1d.3 — Application Logic Layer

**PyCaret version:** 3.x  
**Algorithms compared:** LR, Random Forest, XGBoost, Decision Tree, KNN, Naive Bayes, SVM  
**Tuning:** `tune_model()` on top performer — optimized for AUC  
**MLflow:** `log_experiment=True` in `setup()` — all runs auto-logged

### `application-logic/services/prediction_service.py`

```python
import os
import logging
import pandas as pd
from typing import Dict, List, Optional

from db_logic.loaders.loaders import LocalDataLoader

logger = logging.getLogger(__name__)

_MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://ml-mlflow:5000")
_EXPERIMENT = "ml-titanic-automl"


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
        from pycaret.classification import (
            setup, compare_models, tune_model,
            finalize_model, pull, predict_model
        )
        import mlflow

        df = self._loader.load()

        mlflow.set_tracking_uri(_MLFLOW_URI)

        exp = setup(
            data=df,
            target="survived",
            session_id=42,
            log_experiment=True,
            experiment_name=_EXPERIMENT,
            log_plots=True,
            verbose=False,
            html=False,
        )

        # Compare top 5 models
        top_models = compare_models(n_select=5, sort="AUC", verbose=False)
        leaderboard_df = pull()
        self._leaderboard = leaderboard_df.head(5).to_dict(orient="records")

        # Tune best model
        tuned = tune_model(top_models[0], optimize="AUC", verbose=False)
        self._best_model_name = type(tuned).__name__

        # Finalize on full dataset
        self._model = finalize_model(tuned)

        # Capture metrics from leaderboard
        best_row = leaderboard_df.iloc[0]
        self._metrics = {
            "accuracy":  round(float(best_row.get("Accuracy", 0)), 4),
            "auc":       round(float(best_row.get("AUC", 0)), 4),
            "f1":        round(float(best_row.get("F1", 0)), 4),
            "precision": round(float(best_row.get("Prec.", 0)), 4),
            "recall":    round(float(best_row.get("Recall", 0)), 4),
        }
        self._ready = True

        # Capture MLflow run_id
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
        from pycaret.classification import predict_model
        X = pd.DataFrame([features])
        result = predict_model(self._model, data=X, verbose=False)
        pred = int(result["prediction_label"].iloc[0])
        score = round(float(result["prediction_score"].iloc[0]), 4)
        return {
            "prediction": pred,
            "survived": bool(pred),
            "survival_label": "Survived" if pred == 1 else "Did Not Survive",
            "confidence": score,
        }

    def get_model_info(self) -> Dict:
        if not self._ready:
            self.train()
        return {
            "model_type": "AutoML Classifier",
            "best_model": self._best_model_name,
            "dataset": "Titanic",
            "n_samples": 891,
            "n_features": 7,
            "algorithms_compared": 5,
            "optimized_for": "AUC",
            "leaderboard": self._leaderboard,
            "metrics": self._metrics,
            "run_id": self._run_id,
            "experiment_id": self._experiment_id,
            "mlflow_url": (
                f"/mlflow/#/experiments/{self._experiment_id}/runs/{self._run_id}"
                if self._run_id else None
            ),
        }

    @property
    def is_ready(self) -> bool:
        return self._ready
```

### Tests (`tests/application/test_classifier.py`)
- `test_predict_returns_valid_survival` (0 or 1)
- `test_predict_confidence_between_0_and_1`
- `test_accuracy_above_threshold` (>0.75)
- `test_leaderboard_has_multiple_models`
- `test_predict_without_train_raises`

**Note:** `scope="module"` on the train fixture — PyCaret setup takes ~2 min.

```bash
python3 -m pytest tests/application/ -v   # slow — trains AutoML
git commit -m "feat(application-logic): implement PyCaret AutoML classifier"
```

---

## Phase 1d.4 — Presentation Logic Layer

### Schemas (Full Pydantic v2)

```python
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Annotated, Dict, List, Literal, Optional

class PredictionRequest(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True)

    pclass:   Annotated[int,   Field(ge=1, le=3,   description="Passenger class")]
    sex:      Literal["male", "female"]
    age:      Annotated[float, Field(gt=0, lt=120, description="Age in years")]
    sibsp:    Annotated[int,   Field(ge=0, le=8,   description="Siblings/spouses aboard")]
    parch:    Annotated[int,   Field(ge=0, le=6,   description="Parents/children aboard")]
    fare:     Annotated[float, Field(ge=0,         description="Ticket fare")]
    embarked: Literal["S", "C", "Q"]

    @field_validator("age", "fare", mode="before")
    @classmethod
    def round_to_two_decimals(cls, v):
        return round(float(v), 2)

    @model_validator(mode="after")
    def validate_business_rules(self):
        if self.pclass == 1 and self.fare < 5.0:
            raise ValueError("First class fare unrealistically low")
        return self


class PredictionResponse(BaseModel):
    prediction:     int
    survived:       bool
    survival_label: str
    confidence:     float
    request_id:     Optional[str] = None


class LeaderboardEntry(BaseModel):
    model:    str
    accuracy: float
    auc:      float
    f1:       float


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
- **Leaderboard table** — top 5 models with Accuracy, AUC, F1 columns. Best model highlighted.
- **Input form** — dropdowns for pclass/sex/embarked, sliders for age/fare/sibsp/parch
- **Prediction result** — "Survived" (green) or "Did Not Survive" (red) + confidence gauge
- **Model Card** — best model name, metrics, "View in MLflow →" button
- Example passengers: "Rose (1st class, female)", "Jack (3rd class, male)"
- `fetch()` calls `/ml/titanic-automl/predict`
- Model Card loads from `/ml/titanic-automl/model-info` on page load

### Tests (`tests/presentation/test_routes.py`)
- `test_health_returns_200`
- `test_predict_returns_200`
- `test_predict_invalid_pclass_returns_422` (pclass=5)
- `test_predict_invalid_sex_returns_422` (sex="unknown")
- `test_predict_business_rule_returns_422` (pclass=1, fare=0.5)
- `test_predict_returns_valid_survival`
- `test_model_info_returns_200`
- `test_model_info_has_leaderboard`

```bash
python3 -m pytest tests/ -v
git commit -m "feat(presentation-logic): implement /predict and /model-info with Pydantic v2"
```

---

## Phase 1d.5 — Pydantic v2 Migration (iris-knn + housing-linear)

Fix deprecation warnings across existing projects:

**`@validator` → `@field_validator`** in both schemas.py files:

```python
# OLD (deprecated)
from pydantic import validator
@validator("data")
def validate_features(cls, v): ...

# NEW (Pydantic v2)
from pydantic import field_validator
@field_validator("data")
@classmethod
def validate_features(cls, v): ...
```

```bash
git commit -m "fix(pydantic): migrate iris-knn and housing-linear to Pydantic v2 field_validator"
```

---

## Phase 1d.6 — Docker Build

### `requirements.txt`

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pycaret[full]==3.3.1
scikit-learn==1.3.2
numpy==1.26.3
pandas==2.1.4
seaborn==0.13.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
mlflow>=2.10.0
boto3>=1.26.0
```

**Note:** `pycaret[full]` includes XGBoost, LightGBM, CatBoost. Image ~2GB.

```bash
cd /volume1/pandya-homelab/ml/ml-titanic-automl
sudo docker build -f docker/Dockerfile -t ml-titanic-automl:latest .

sudo docker run -d -p 8003:8000 \
  -e DATABASE_URL="postgresql://postgres:ml_postgres_dev_password@host.docker.internal:5433/mldb" \
  --name ml-titanic-automl ml-titanic-automl:latest

sleep 30
curl http://localhost:8003/health
curl -X POST http://localhost:8003/predict \
  -H "Content-Type: application/json" \
  -d '{"pclass":1,"sex":"female","age":28.0,"sibsp":0,"parch":0,"fare":100.0,"embarked":"S"}'

sudo docker stop ml-titanic-automl && sudo docker rm ml-titanic-automl
git commit -m "build(docker): finalize Dockerfile for ml-titanic-automl"
```

---

## Phase 1d.7 — Integration

### Step 1: Add to `deployment/ml/docker-compose.dev.yml`

```yaml
ml-titanic-automl:
  image: ml-titanic-automl:latest
  container_name: ml-titanic-automl
  environment:
    PYTHONPATH: /app
    MLFLOW_TRACKING_URI: http://ml-mlflow:5000
    DATABASE_URL: postgresql://postgres:${ML_POSTGRES_PASSWORD}@ml-postgres:5432/mldb
  ports:
    - "8003:8000"
  networks:
    ml-network:
      ipv4_address: 172.20.0.12
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
upstream ml_titanic {
    server ml-titanic-automl:8000 max_fails=3 fail_timeout=30s;
}

location /ml/titanic-automl/ {
    proxy_pass http://ml_titanic/;
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
    return 200 '{"domain":"ml","projects":["iris-knn","housing-linear","titanic-automl"],"status":"active"}';
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

curl -k https://localhost:8443/ml/titanic-automl/health
curl -k -X POST https://localhost:8443/ml/titanic-automl/predict \
  -H "Content-Type: application/json" \
  -d '{"pclass":1,"sex":"female","age":28.0,"sibsp":0,"parch":0,"fare":100.0,"embarked":"S"}'
```

```bash
git commit -m "feat(deployment): wire ml-titanic-automl into ml-network with Nginx routing"
```

---

## Phase 1d.8 — Landing Page Update

In `website/index.html`:
- Replace "Random Forest Classifier — Planned" card with AutoML Classifier card
- `status-wip` → `status-live`
- Route: `/ml/titanic-automl/`
- Update domain count: `2 live · 1 planned` → `3 live · 1 planned`

```bash
git commit -m "feat(website): add ml-titanic-automl as live on landing page"
```

---

## Phase 1d.9 — Merge & Tag

```bash
cd /volume1/pandya-homelab
git log main..HEAD --oneline
git checkout main
git merge --ff-only ml-titanic-automl/scaffold
git tag v.ml-titanic-automl-1.0.0 -m "ml-titanic-automl: PyCaret AutoML classifier, 5+ algorithms, PostgreSQL persistence"
git log --oneline | head -5
```

---

## Exit Criteria — Phase 1d Complete

- [ ] All tests passing (TIER 1)
- [ ] Docker image builds cleanly
- [ ] `https://pandyahomelab.com/ml/titanic-automl/` loads with leaderboard
- [ ] Prediction returns Survived/Not Survived with confidence
- [ ] MLflow shows `ml-titanic-automl` experiment with 5+ algorithm runs
- [ ] PostgreSQL has `titanic` table with cleaned data
- [ ] Pydantic v2 validation rejects invalid inputs (422)
- [ ] Landing page shows titanic-automl as Live
- [ ] Merged to main, tagged `v.ml-titanic-automl-1.0.0`

---

## IP/Port Reference Card

| Service | IP | Host Port | URL |
|---|---|---|---|
| ml-postgres | 172.20.0.2 | 5433 | — |
| ml-minio | 172.20.0.3 | 9000 | — |
| ml-redis | 172.20.0.4 | 6379 | — |
| ml-mlflow | 172.20.0.5 | 5000 | /mlflow/ |
| ml-iris-knn | 172.20.0.10 | 8001 | /ml/iris-knn/ |
| ml-housing-linear | 172.20.0.11 | 8002 | /ml/housing-linear/ |
| **ml-titanic-automl** | **172.20.0.12** | **8003** | **/ml/titanic-automl/** |
| Nginx on ml-net | 172.20.0.20 | — | proxy |
