# ML Project Template

**Version:** 1.0.0  
**Template Date:** May 2026  
**Architecture:** Per-project 3-layer (ADR-013)

## Overview

This is a production-ready ML project template following the **presentation-logic → application-logic → db-logic** architecture pattern. Use this template as a starting point for new ML projects in the pandyaHomeLab platform.

## Project Structure

```
ml/ml-{project-name}/
├── presentation-logic/     # API routes, schemas, middleware
│   ├── api/
│   │   ├── main.py        (FastAPI app factory)
│   │   ├── routes.py      (API endpoints)
│   │   ├── schemas.py     (Pydantic models)
│   │   └── dependencies.py (Dependency injection)
│   └── errors/
│       └── handlers.py    (Error handlers)
│
├── application-logic/      # Business logic, model, services
│   ├── model/
│   │   └── classifier.py  (Model definition)
│   ├── pipeline/
│   │   └── inference_pipeline.py
│   └── services/
│       └── prediction_service.py
│
├── db-logic/              # Data loading, preprocessing, persistence
│   ├── loaders/
│   │   └── loaders.py     (LocalDataLoader, S3Loader, DBLoader)
│   ├── transforms/
│   │   └── preprocessor.py
│   └── repository/
│       └── prediction_repository.py
│
├── shared/                # Project-local utilities
│   ├── config.py          (Configuration)
│   ├── logger.py          (Logging)
│   ├── metrics.py         (Metrics)
│   ├── constants.py
│   ├── exceptions.py
│   └── utils.py
│
├── tests/                 # Test suite
│   ├── presentation/      (API tests)
│   ├── application/       (Model/logic tests)
│   └── db/                (Loader/repository tests)
│
├── notebooks/             # Development notebooks
├── data/                  # Data directory (gitignored)
├── models/                # Model checkpoints (gitignored)
├── configs/               # YAML configurations
│   ├── model.yaml         (Hyperparameters)
│   ├── api.yaml           (API config)
│   └── logging.yaml       (Logging config)
│
├── docker/                # Docker configuration
│   ├── Dockerfile         (Multi-stage build)
│   └── .dockerignore
│
├── pyproject.toml         # Project metadata
├── requirements.txt       # Dependencies
├── requirements-dev.txt   # Dev dependencies
├── Makefile               # Build targets
├── README.md
├── .env.example
├── .gitignore
└── CHANGELOG.md
```

## Quick Start

### 1. Create Project from Template

```bash
cp -r ml/_templates/ml-project-template/ ml/ml-iris-knn/
cd ml/ml-iris-knn/
```

### 2. Customize Project Metadata

Edit `Makefile`, `pyproject.toml`, `README.md` with your project name and description.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Run Tests (TIER 1)

```bash
make lint
make test-unit
make test-cov
```

### 5. Build Docker Image (TIER 2)

```bash
make docker-build
make docker-run
# Test endpoint: curl http://localhost:8000/health
```

### 6. Integrate with Infrastructure (TIER 3)

Add service to `deployment/ml/docker-compose.yml` and configure Nginx upstream.

## Architecture Layers

### Presentation Logic
**Responsibility:** HTTP API, request/response validation, error handling

**Files:**
- `api/main.py` — FastAPI app creation
- `api/routes.py` — Endpoint definitions (GET /health, POST /predict)
- `api/schemas.py` — Pydantic request/response models
- `errors/handlers.py` — Custom error responses

**Key Pattern:**
```python
# All routes validate input via Pydantic schemas
@router.post("/predict")
async def predict(request: PredictionRequest):
    # Route delegates to application-logic service
    result = await prediction_service.predict(request.data)
    return PredictionResponse(prediction=result)
```

### Application Logic
**Responsibility:** Business logic, model operations, data transformation

**Files:**
- `model/classifier.py` — Model architecture and training
- `pipeline/inference_pipeline.py` — Data→model→result flow
- `services/prediction_service.py` — Orchestrates model + data access

**Key Pattern:**
```python
# Services own the business logic, not routes
class PredictionService:
    def predict(self, data):
        # 1. Validate
        # 2. Call db-logic to load features
        # 3. Call model to predict
        # 4. Store audit trail
        # 5. Return result
```

### DB Logic
**Responsibility:** Data access, loading, persistence

**Files:**
- `loaders/loaders.py` — Load data from local disk, S3, or PostgreSQL
- `transforms/preprocessor.py` — Feature engineering and normalization
- `repository/prediction_repository.py` — Store/retrieve predictions (audit trail)

**Key Pattern:**
```python
# Data access is centralized, repository pattern for persistence
class LocalDataLoader(BaseDataLoader):
    def load(self):
        # Load from disk
        pass

class PredictionRepository:
    def save_prediction(self, input, output):
        # Store to PostgreSQL
        pass
```

### Shared (Project-Local)
**Responsibility:** Utilities used across layers

**Files:**
- `config.py` — Load environment variables
- `logger.py` — Structured JSON logging
- `metrics.py` — Application metrics
- `constants.py` — Constants
- `exceptions.py` — Custom exceptions
- `utils.py` — Helper functions

**Note:** Project-local shared/ avoids root-level dependencies and keeps projects autonomous.

## Development Workflow

### 1. Implement Model (Application Logic)

```python
# application-logic/model/classifier.py
class IrisClassifier(BaseClassifier):
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100)
    
    def train(self, X_train, y_train):
        self.model.fit(X_train, y_train)
    
    def predict(self, X):
        return self.model.predict_proba(X)
```

### 2. Implement Data Loading (DB Logic)

```python
# db-logic/loaders/loaders.py
class IrisDataLoader(LocalDataLoader):
    def load(self):
        return pd.read_csv("/app/data/iris.csv")
```

### 3. Wire Routes (Presentation Logic)

```python
# presentation-logic/api/routes.py
@router.post("/predict")
async def predict(request: PredictionRequest):
    service = PredictionService(classifier, loader)
    result = await service.predict(request.data)
    return PredictionResponse(prediction=result)
```

### 4. Test Each Layer

```bash
# Test models
pytest tests/application/

# Test API
pytest tests/presentation/

# Test data access
pytest tests/db/

# All tests with coverage
make test-cov
```

## Infrastructure Setup

Each project connects to shared domain infrastructure:

```
PostgreSQL    (shared by 2 projects per domain)
MinIO         (shared by 2 projects per domain)
Redis         (shared cache)
MLflow        (shared experiment tracking)
```

Configure in `.env` or `shared/config.py`:

```python
DATABASE_URL = "postgresql://postgres:password@ml-postgres:5432/mlproject"
MINIO_ENDPOINT = "ml-minio:9000"
REDIS_URL = "redis://ml-redis:6379"
```

## Deployment

### TIER 1: Code Readiness
```bash
make lint          # Black, flake8, mypy
make test-unit     # Pytest
pip check          # Dependency conflicts
```

### TIER 2: Docker Readiness
```bash
make docker-build  # Build image
docker run -p 8000:8000 ml-iris-knn
curl http://localhost:8000/health  # Should return 200
```

### TIER 3: Integration Readiness
```bash
# Add to deployment/ml/docker-compose.yml
# Verify Nginx routing: curl http://localhost/ml/health
# Run end-to-end tests: make test-e2e
```

## Troubleshooting

### Service won't start
```bash
# Check logs
docker logs ml-iris-knn

# Check health endpoint
curl http://localhost:8000/health

# Check environment variables
docker inspect ml-iris-knn | grep Env
```

### Tests fail
```bash
# Clear cache
make clean

# Re-run with verbose output
pytest tests/ -v

# Check coverage
make test-cov
```

## Related Documentation

- **ADR-013** — Per-project 3-layer architecture
- **ADR-014** — Project autonomy and templates
- **ADR-016** — Domain-level network topology
- **ADR-019** — Internet access and routing
- **ADR-020** — Project readiness checklist

## Support

For issues or questions, refer to the main README at `docs/README.md` or contact the maintainer.
