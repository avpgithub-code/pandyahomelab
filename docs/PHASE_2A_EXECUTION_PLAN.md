# Phase 2a Execution Plan — dl-mnist-cnn

**Objective:** Build dl-mnist-cnn (CNN image classifier on MNIST handwritten digits)  
**URL:** `https://pandyahomelab.com/dl/mnist-cnn/`  
**Port:** 8010 (host) → 8000 (container)  
**IP:** 172.21.0.10 (dl-network)  
**Tag:** `v.dl-mnist-cnn-1.0.0`

**Model:** PyTorch CNN — 2 conv layers + 2 FC layers  
**Dataset:** MNIST (60,000 train / 10,000 test, 28×28 grayscale)  
**Target accuracy:** ≥98%  
**Demo UI:** HTML5 canvas — draw a digit, get prediction with confidence bars

All Phase 1 infrastructure is already running. Follow top-to-bottom without deviation.
Read these memories before starting — every gotcha worth knowing is pre-solved:
- `mlflow_operational_lessons` — MLflow routing + artifact config
- `deployment_image_rebuild_rules` — bind-mount vs. baked-image, `docker compose build` is a no-op trap, Nginx 502 cooldown
- `feedback_widget_v1` — one-line embed for the bottom-of-page widget
- `pycaret_docker_lessons` — adjacent pattern for fussy framework wheels (PyTorch wheels are similarly large)

Also read `docs/PHASE_2_MASTER_PLAN.md` first — it covers cross-cutting decisions (dl-network, MLflow attachment, About drawer, feedback widget, landing-page card flip) that apply to **every** DL sub-phase so 2b/2c don't repeat them.

---

## Pre-Flight Check

```bash
curl -k https://localhost:8443/ml/iris-knn/health     # Expected: {"status":"healthy",...}
curl -k https://localhost:8443/ml/housing-linear/health
curl http://localhost:5000/health                     # MLflow: OK
sudo docker ps | grep -E "iris|housing|mlflow|nginx"  # All healthy
```

---

## Phase 2a.1 — DL Domain Infrastructure (domain-local per V3)

### Create branch
```bash
cd /volume1/pandya-homelab
git checkout -b dl-mnist-cnn/scaffold
```

### Create `deployment/dl/docker-compose.yml` (infrastructure — postgres/minio/redis/mlflow)

Domain-autonomous: dl-network has its **own** postgres/minio/redis/mlflow stack, mirroring ml-network. No cross-network reach-back into ml-network.

**MLflow config mirrors ml-mlflow exactly** (vanilla `ghcr.io/mlflow/mlflow:latest` image, SQLite backend store, local artifact volume with `--serve-artifacts`) — this is the documented "correct combo" from [mlflow_operational_lessons](../memory/mlflow_operational_lessons.md). `dl-postgres` and `dl-minio` are stood up on the network for use by future DL demos (analytics, image storage, etc.) but are **not wired into dl-mlflow** — exactly like the ML side.

```yaml
version: '3.8'

# DL Domain Infrastructure
# Each service connects to dl-network (172.21.0.0/24, isolated per V3 domain autonomy).
# Mirrors deployment/ml/docker-compose.yml structure exactly so operational knowledge
# (MLflow gotchas, healthcheck patterns, log rotation) transfers verbatim.

networks:
  dl-network:
    driver: bridge
    ipam:
      driver: default
      config:
        - subnet: 172.21.0.0/24
          gateway: 172.21.0.1

services:
  # Infrastructure Services (shared by future DL projects: 2a/2b/2c)

  dl-postgres:
    image: postgres:16-alpine
    container_name: dl-postgres
    environment:
      POSTGRES_DB: ${DL_POSTGRES_DB:-dldb}
      POSTGRES_USER: ${DL_POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${DL_POSTGRES_PASSWORD}
    ports:
      - "5434:5432"
    volumes:
      - dl_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DL_POSTGRES_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      dl-network:
        ipv4_address: 172.21.0.2
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  dl-minio:
    image: minio/minio:latest
    container_name: dl-minio
    environment:
      MINIO_ROOT_USER: ${DL_MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${DL_MINIO_ROOT_PASSWORD}
    ports:
      - "9002:9000"
      - "9003:9001"
    volumes:
      - dl_minio_data:/minio_data
    command: minio server /minio_data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      dl-network:
        ipv4_address: 172.21.0.3
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  dl-redis:
    image: redis:7-alpine
    container_name: dl-redis
    ports:
      - "6380:6379"
    volumes:
      - dl_redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      dl-network:
        ipv4_address: 172.21.0.4
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  dl-mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    container_name: dl-mlflow
    environment:
      GIT_PYTHON_REFRESH: quiet
    command: >
      mlflow server
      --backend-store-uri sqlite:///mlflow/mlruns.db
      --default-artifact-root mlflow-artifacts:/
      --serve-artifacts
      --host 0.0.0.0
      --port 5000
      --allowed-hosts "*"
      --cors-allowed-origins "https://mlflow-dl.pandyahomelab.com"
    volumes:
      - dl_mlflow_data:/mlflow
      - dl_mlartifacts_data:/mlartifacts
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 35s
    networks:
      dl-network:
        ipv4_address: 172.21.0.5
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # Project Services (placeholder — built from dl/dl-mnist-cnn/ in Phase 2a.6)
  # These will be added in docker-compose.dev.yml during Phase 2a.7

volumes:
  dl_postgres_data:
  dl_minio_data:
  dl_redis_data:
  dl_mlflow_data:
  dl_mlartifacts_data:
```

### Create `deployment/dl/docker-compose.dev.yml` (empty stub now; demo containers added in 2a.7)

The two-file compose pattern (`-f docker-compose.yml -f docker-compose.dev.yml`) is established from day one for shape parity with the ML stack, but the overlay stays empty until Phase 2a.7 — when `dl-mnist-cnn:latest` exists as a built image, the `dl-mnist-cnn:` service block gets added here. Writing the full block now would break `docker compose up` because the image doesn't exist yet.

```yaml
version: '3.8'

# Dev overlay: DL project containers attached to dl-network.
# Usage: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
#
# Services added in subsequent sub-phases:
#   - dl-mnist-cnn               (Phase 2a.7)
#   - dl-lstm-forecast           (Phase 2b)
#   - dl-yolo-object-detection   (Phase 2c)

services: {}
```

### Create `deployment/dl/.env.example` (template — real `.env` is gitignored, user-created)

```bash
# DL Domain Infrastructure Configuration — TEMPLATE
# Copy this file to .env and fill in real values.
# The .env file is gitignored to prevent secret leakage.

# PostgreSQL
DL_POSTGRES_DB=dldb
DL_POSTGRES_USER=postgres
DL_POSTGRES_PASSWORD=replace_me_with_strong_password

# MinIO
DL_MINIO_ROOT_USER=minioadmin
DL_MINIO_ROOT_PASSWORD=replace_me_with_strong_password
```

### Bring up dl-network infrastructure first

Before any DL demo:
```bash
cd /volume1/pandya-homelab/deployment/dl
sudo docker compose up -d   # starts dl-postgres, dl-minio, dl-redis, dl-mlflow
sudo docker compose ps      # all four should be healthy/running
```

Verify dl-mlflow is reachable on the network:
```bash
sudo docker exec dl-mlflow curl -s http://dl-mlflow:5000/health || echo "mlflow not up yet"
```

### Connect Nginx to dl-network

In `deployment/nginx/docker-compose.yml`, add the dl-network:

```yaml
  # External domain networks
  ml_ml-network:
    external: true
  dl_dl-network:
    external: true
```

And add the container's dl-network attachment:
```yaml
    networks:
      pandya-proxy-network:
        ipv4_address: 172.24.0.2
      ml_ml-network:
        ipv4_address: 172.20.0.20
      dl_dl-network:
        ipv4_address: 172.21.0.20
```

### Add Nginx upstream + location for DL

In `deployment/nginx/nginx.conf`:

```nginx
upstream dl_mnist {
    server dl-mnist-cnn:8000 max_fails=3 fail_timeout=30s;
}

# In server block:
location /dl/mnist-cnn/ {
    proxy_pass http://dl_mnist/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 30s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
}

location = /dl/ {
    return 200 '{"domain":"dl","projects":["mnist-cnn"],"status":"active"}';
    add_header Content-Type application/json;
}

# Replace the /dl/ coming-soon block with the above
```

**Note:** `/dl/` currently returns 503 coming-soon — replace it.

```bash
git commit -m "feat(deployment): add dl-network infrastructure and Nginx routing for DL domain"
```

---

## Phase 2a.1b — Expose dl-mlflow via subdomain (`mlflow-dl.pandyahomelab.com`)

Runs **after** 2a.1 (needs `dl-network` live, `dl-mlflow` container running, Nginx attached to `dl-network` at `172.21.0.20`). Implements the locked subdomain decision from [PHASE_2_MASTER_PLAN.md](PHASE_2_MASTER_PLAN.md). Kept as a separate sub-step because it's the only DL piece that needs Cloudflare-side work (tunnel ingress) and host-based Nginx routing (new `server` block) rather than path-based routing — easy to roll back independently if anything misbehaves.

### Pre-flight already complete (platform setup, May 2026)
- ✅ Cloudflare Universal SSL wildcard cert (`*.pandyahomelab.com, pandyahomelab.com`, free, managed, auto-renewing)
- ✅ Wildcard DNS record (`* CNAME pandyahomelab.com`, proxied) — covers `mlflow-dl`, future `mlflow-nlp`, `mlflow-agentic`, etc.
- ✅ Verified: `nslookup mlflow-dl.pandyahomelab.com` resolves to Cloudflare anycast IPs

So the only remaining work is the tunnel ingress rule + Nginx server block.

### Step 1: Add tunnel ingress rule

Edit `/var/services/homes/avpadmin/.cloudflared/config.yml` — insert **before** the catch-all `http_status:404` (cloudflared evaluates ingress top-down):

```yaml
  - hostname: mlflow-dl.pandyahomelab.com
    service: https://localhost:8443
    originRequest:
      noTLSVerify: true
```

Restart cloudflared (per the runbook in [cloudflare_tunnel memory](../memory/cloudflare_tunnel.md)):
```bash
pkill -f cloudflared && sleep 2
nohup cloudflared tunnel run pandya-homelab >> ~/cloudflared.log 2>&1 &
```

Verify the tunnel re-registered both old and new ingress rules:
```bash
tail -20 ~/cloudflared.log
# Expect: "Registered tunnel connection" lines, no errors
```

### Step 2: Add Nginx upstreams + server block

In `deployment/nginx/nginx.conf`. Two changes here; the `/dl/mnist-cnn/` route is deferred to Phase 2a.7.

**Why not batch /dl/mnist-cnn/ here:** Nginx resolves all upstream hostnames at startup (not lazily on first request, as initially assumed). Declaring `upstream dl_mnist { server dl-mnist-cnn:8000; }` before the container exists causes `nginx: [emerg] host not found in upstream "dl-mnist-cnn:8000"` and the server fails to start. Two ways around it: (i) defer the upstream + location to Phase 2a.7 when the container exists; (ii) use the variable + `resolver 127.0.0.11` pattern so DNS resolution defers to request time. Option (i) is simpler and the path taken here — one extra Nginx rebuild in Phase 2a.7 is a small cost vs. the resolver-pattern config nuance.

**(a) One new upstream** (added after `ml_mlflow`):
```nginx
upstream dl_mlflow {
    server dl-mlflow:5000 max_fails=3 fail_timeout=30s;
}
```

**(b) Replace the existing `/dl/` 503 block** with the DL JSON listing (only — no `/dl/mnist-cnn/` location yet) inside the `pandyahomelab.com` server block. The comment heading for the still-pending domains becomes "NLP, Agentic — coming soon".

```nginx
location = /dl/ {
    return 200 '{"domain":"dl","projects":["mnist-cnn"],"status":"active"}';
    add_header Content-Type application/json;
}
```

**(c) New `server` block** for `mlflow-dl.pandyahomelab.com`, appended at the end of the `http {}` block. Uses the existing self-signed cert at `/etc/nginx/certs/server.{crt,key}` (cloudflared has `noTLSVerify: true`, so the cert SAN coverage doesn't matter for tunnel-terminated traffic). Logging uses `combined`-only — MLflow is ops/dev surface, not visitor traffic.

```nginx
server {
    listen 443 ssl http2;
    server_name mlflow-dl.pandyahomelab.com;

    ssl_certificate /etc/nginx/certs/server.crt;
    ssl_certificate_key /etc/nginx/certs/server.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    access_log /var/log/nginx/access.log combined;
    error_log /var/log/nginx/error.log warn;

    # Host-based routing means /api/2.0/mlflow, /ajax-api/2.0/mlflow, /graphql
    # all proxy to dl_mlflow here — no collision with the ml_mlflow versions
    # in the pandyahomelab.com server block (host header disambiguates).
    location / {
        proxy_pass http://dl_mlflow/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Existing `server_name` check:** the main HTTPS server block at the top of `nginx.conf` already has `server_name pandyahomelab.com www.pandyahomelab.com;` explicitly — no risk of it catching `mlflow-dl` requests as the default server.

### Step 3: Rebuild Nginx image and recreate

`nginx.conf` is **baked** into the pandya-nginx image (see [deployment_image_rebuild_rules](../memory/deployment_image_rebuild_rules.md)) — every change requires a rebuild:

```bash
cd /volume1/pandya-homelab/deployment/nginx
sudo docker build -t pandya-nginx:latest .

cd /volume1/pandya-homelab/deployment/ml
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate pandya-nginx

# Skip the 30s upstream-cooldown 502 burst
sudo docker exec pandya-nginx nginx -s reload
```

### Step 4: Verify end-to-end

```bash
# From the NAS
curl -kI https://mlflow-dl.pandyahomelab.com/
# Expect: HTTP/2 200, Content-Type: text/html (the MLflow UI)

# Test an MLflow API path to confirm it routes to dl_mlflow, not ml_mlflow
curl -k https://mlflow-dl.pandyahomelab.com/api/2.0/mlflow/experiments/list | python3 -m json.tool
# Expect: {"experiments": [...]} from dl-mlflow's empty database — NOT iris-knn experiments
```

Browser check: `https://mlflow-dl.pandyahomelab.com/` loads the dl-mlflow UI (fresh tracker, no experiments yet — the first one will appear after the dl-mnist-cnn demo runs its first training).

```bash
git commit -m "feat(deployment): expose dl-mlflow via mlflow-dl.pandyahomelab.com"
```

### Step 5: Refresh memory

After this step completes, refresh [cloudflare_tunnel memory](../memory/cloudflare_tunnel.md) to capture:
- The new `mlflow-dl.pandyahomelab.com` ingress rule
- The subdomain pattern as the platform standard for per-domain MLflow
- The wildcard CNAME + wildcard cert setup as the "do once, reuse forever" platform foundation

---

## Phase 2a.2 — Project Scaffolding

```bash
cp -r ml/_templates/ml-project-template/ ml/dl-mnist-cnn/
cd ml/dl-mnist-cnn/
ln -s db-logic db_logic
ln -s application-logic application_logic
ln -s presentation-logic presentation_logic
```

Update metadata:

**pyproject.toml:**
```toml
name = "dl-mnist-cnn"
version = "1.0.0-alpha1"
description = "Handwritten digit classification using CNN (PyTorch)"
```

**README.md:** Replace "ML Project Template" → "DL MNIST CNN Classifier"  
**CHANGELOG.md:** Add v1.0.0-alpha1 entry

```bash
git commit -m "scaffold(dl-mnist-cnn): initialize from ml-project-template"
```

---

## Phase 2a.3 — DB Logic Layer

**Dataset:** MNIST via torchvision (auto-downloads to `/app/data`, ~11MB)  
**Features:** 28×28 grayscale pixel values (784 floats, normalized 0-1)  
**Target:** Digit class 0–9

### `db-logic/loaders/loaders.py`

```python
import torch
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, random_split
from typing import Tuple

class LocalDataLoader:
    CLASSES = list(range(10))
    IMG_SIZE = 28

    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = data_dir
        self._transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,))
        ])

    def load_train(self) -> DataLoader:
        dataset = datasets.MNIST(self.data_dir, train=True, download=True, transform=self._transform)
        return DataLoader(dataset, batch_size=64, shuffle=True)

    def load_test(self) -> DataLoader:
        dataset = datasets.MNIST(self.data_dir, train=False, download=True, transform=self._transform)
        return DataLoader(dataset, batch_size=1000, shuffle=False)

    def preprocess_input(self, pixels: list) -> torch.Tensor:
        """Convert flat 784-float list to normalized 1×28×28 tensor."""
        t = torch.tensor(pixels, dtype=torch.float32).reshape(1, 1, 28, 28)
        mean, std = 0.1307, 0.3081
        return (t / 255.0 - mean) / std
```

### `db-logic/transforms/preprocessor.py`

```python
import torch
from torchvision import transforms

class DataPreprocessor:
    """Normalizes MNIST pixel values to zero mean / unit variance."""

    MEAN = 0.1307
    STD  = 0.3081

    def transform_input(self, pixels: list) -> torch.Tensor:
        t = torch.tensor(pixels, dtype=torch.float32).reshape(1, 1, 28, 28)
        return (t / 255.0 - self.MEAN) / self.STD
```

### Tests (`tests/db/test_loaders.py`)
- `test_load_train_returns_dataloader`
- `test_load_test_returns_dataloader`
- `test_train_dataset_size` (60,000 samples)
- `test_test_dataset_size` (10,000 samples)
- `test_preprocess_input_shape` (output: 1×1×28×28)

```bash
python3 -m pytest tests/db/ -v
git commit -m "feat(db-logic): implement MNIST data loader and preprocessor"
```

---

## Phase 2a.4 — Application Logic Layer

**Model:** PyTorch CNN  
**Architecture:**
- Conv2d(1→32, 3×3) → ReLU → Conv2d(32→64, 3×3) → ReLU → MaxPool(2) → Dropout(0.25)
- Flatten → Linear(9216→128) → ReLU → Dropout(0.5) → Linear(128→10)
- Optimizer: Adam (lr=0.001)  
- Loss: CrossEntropyLoss  
- Epochs: 3 (≥98% accuracy, ~8 min CPU on NAS)

### `application-logic/model/classifier.py`

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List

class MnistCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, 1)
        self.conv2 = nn.Conv2d(32, 64, 3, 1)
        self.dropout1 = nn.Dropout(0.25)
        self.dropout2 = nn.Dropout(0.5)
        self.fc1 = nn.Linear(9216, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.max_pool2d(x, 2)
        x = self.dropout1(x)
        x = torch.flatten(x, 1)
        x = F.relu(self.fc1(x))
        x = self.dropout2(x)
        return self.fc2(x)

class DigitClassifier:
    CLASSES = [str(i) for i in range(10)]

    def __init__(self):
        self._model = MnistCNN()
        self._trained = False

    def train(self, train_loader, epochs: int = 3) -> "DigitClassifier":
        optimizer = torch.optim.Adam(self._model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()
        self._model.train()
        for epoch in range(epochs):
            for data, target in train_loader:
                optimizer.zero_grad()
                loss = criterion(self._model(data), target)
                loss.backward()
                optimizer.step()
        self._trained = True
        return self

    def evaluate(self, test_loader) -> Dict:
        self._model.eval()
        correct = total = 0
        with torch.no_grad():
            for data, target in test_loader:
                pred = self._model(data).argmax(dim=1)
                correct += pred.eq(target).sum().item()
                total += len(target)
        return {"accuracy": round(correct / total, 4), "correct": correct, "total": total}

    def predict(self, tensor) -> Dict:
        self._check_trained()
        self._model.eval()
        with torch.no_grad():
            output = self._model(tensor)
            probs = torch.softmax(output, dim=1)[0]
            pred = probs.argmax().item()
        return {
            "prediction": pred,
            "digit": str(pred),
            "confidence": round(probs[pred].item(), 4),
            "probabilities": {str(i): round(probs[i].item(), 4) for i in range(10)},
        }

    def _check_trained(self):
        if not self._trained:
            raise RuntimeError("Model must be trained before predict.")

    @property
    def is_trained(self) -> bool:
        return self._trained
```

### `application-logic/services/prediction_service.py`

Same pattern as iris-knn PredictionService:
- Lazy `train()` on first predict
- MLflow tracking: log `epochs=3`, `optimizer=adam`, `lr=0.001`, `architecture=MnistCNN`, `n_train=60000`
- Log metrics: `accuracy`, `correct`, `total`
- `get_model_info()` returns run_id, mlflow_url, metrics

### Tests (`tests/application/test_classifier.py`)
- `test_predict_returns_valid_digit` (0–9)
- `test_predict_confidence_between_0_and_1`
- `test_accuracy_above_threshold` (>0.97)
- `test_predict_without_train_raises`

**Note:** Training takes ~8 minutes on NAS CPU. Use `module` scope fixture to train once.

```bash
python3 -m pytest tests/application/ -v  # slow — trains CNN
git commit -m "feat(application-logic): implement MNIST CNN classifier and prediction service"
```

---

## Phase 2a.5 — Presentation Logic Layer

### Schemas

```python
class PredictionRequest(BaseModel):
    pixels: List[float]  # 784 values (0-255 raw pixel values, flattened 28×28)

    @validator("pixels")
    def validate_pixels(cls, v):
        if len(v) != 784:
            raise ValueError("Exactly 784 pixel values required (28×28 image)")
        return v

class PredictionResponse(BaseModel):
    prediction: int           # predicted digit 0-9
    digit: str                # string representation
    confidence: float         # softmax confidence
    probabilities: Dict[str, float]  # per-digit probabilities
    request_id: Optional[str]

class ModelInfoResponse(BaseModel):
    model_type: str           # "MnistCNN"
    dataset: str              # "MNIST"
    n_train: int              # 60000
    n_test: int               # 10000
    architecture: Dict        # layer summary
    parameters: Dict          # epochs, optimizer, lr
    metrics: Dict             # accuracy
    run_id: Optional[str]
    experiment_id: Optional[str]
    mlflow_url: Optional[str]
```

### Routes
- `GET /` → demo UI (canvas drawing)
- `GET /health` → HealthResponse
- `POST /predict` → PredictionResponse
- `GET /model-info` → ModelInfoResponse

### Demo UI (`presentation-logic/api/ui.html`)
- **HTML5 canvas** (280×280px) — user draws a digit with mouse/touch
- JavaScript resizes canvas to 28×28 and extracts pixel array
- `fetch('/dl/mnist-cnn/predict', {method:'POST', body: JSON.stringify({pixels: [...]})})` 
- Shows predicted digit large (0-9) + confidence bar + per-digit probability bars
- "Clear" button to reset canvas
- Example digit buttons (pre-loaded sample images)
- Dark theme matching iris-knn and housing-linear UIs
- Model Card section (fetches `/dl/mnist-cnn/model-info` on load)
- "View in MLflow →" link

### Tests (`tests/presentation/test_routes.py`)
- `test_health_returns_200`
- `test_predict_returns_200`
- `test_predict_invalid_pixels_returns_422` (wrong count)
- `test_predict_returns_valid_digit` (0–9)
- `test_model_info_returns_200`
- `test_model_info_has_accuracy`

```bash
python3 -m pytest tests/ -v
git commit -m "feat(presentation-logic): implement /health, /predict, /model-info for MNIST CNN"
```

---

## Phase 2a.6 — Docker Build

### `requirements.txt` (CPU-only PyTorch — no CUDA)

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
torch==2.1.1
torchvision==0.16.1
numpy==1.26.3
mlflow>=2.10.0
boto3>=1.26.0
```

**Note:** CPU-only torch wheels from PyTorch index:
```
--extra-index-url https://download.pytorch.org/whl/cpu
```

Add to `docker/Dockerfile` builder stage pip install:
```dockerfile
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
```

**Expected image size:** ~2.5GB (PyTorch CPU is large — acceptable)

```bash
cd /volume1/pandya-homelab/ml/dl-mnist-cnn
sudo docker build -f docker/Dockerfile -t dl-mnist-cnn:latest .
# Expected: builds cleanly

sudo docker run -d -p 8010:8000 --name dl-mnist-cnn dl-mnist-cnn:latest
sleep 60   # CNN training takes time on first predict

curl http://localhost:8010/health
curl -X POST http://localhost:8010/predict \
  -H "Content-Type: application/json" \
  -d "{\"pixels\": $(python3 -c 'import json; print(json.dumps([0.0]*784))')}"

sudo docker stop dl-mnist-cnn && sudo docker rm dl-mnist-cnn
```

```bash
git commit -m "build(docker): finalize Dockerfile for dl-mnist-cnn"
```

---

## Phase 2a.7 — Integration

### Step 1: Add the dl-mnist-cnn service to the dev overlay

Edit `deployment/dl/docker-compose.dev.yml` — replace the empty `services: {}` with the actual service block:

```yaml
services:
  dl-mnist-cnn:
    image: dl-mnist-cnn:latest
    container_name: dl-mnist-cnn
    environment:
      PYTHONPATH: /app
      MLFLOW_TRACKING_URI: http://dl-mlflow:5000
    ports:
      - "8010:8000"
    networks:
      dl-network:
        ipv4_address: 172.21.0.10
    depends_on:
      dl-postgres:
        condition: service_healthy
      dl-redis:
        condition: service_healthy
      dl-minio:
        condition: service_healthy
      dl-mlflow:
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

### Step 2: Bring up dl-mnist-cnn (infrastructure already running)

```bash
cd /volume1/pandya-homelab/deployment/dl/
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d dl-mnist-cnn
sleep 15
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml ps dl-mnist-cnn
# Expect: Up X seconds (healthy)
```

### Step 3: Add the deferred `/dl/mnist-cnn/` route to Nginx (deferred from Phase 2a.1b)

Now that the `dl-mnist-cnn` container exists, the upstream hostname will resolve at Nginx startup. Add to `deployment/nginx/nginx.conf`:

**(a) Upstream (after `dl_mlflow`):**
```nginx
upstream dl_mnist {
    server dl-mnist-cnn:8000 max_fails=3 fail_timeout=30s;
}
```

**(b) Location block (inside the `pandyahomelab.com` server block, before `location = /dl/`):**
```nginx
location /dl/mnist-cnn/ {
    proxy_pass http://dl_mnist/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 30s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

### Step 4: Rebuild Nginx + recreate

```bash
cd /volume1/pandya-homelab/deployment/nginx/
sudo docker build -t pandya-nginx:latest .
sudo docker compose up -d --force-recreate
```

### Step 5: Verify end-to-end

```bash
curl -k https://localhost:8443/dl/mnist-cnn/health        # Expect: healthy JSON
curl -k https://localhost:8443/dl/ | python3 -m json.tool # Expect: dl listing
```

```bash
git commit -m "feat(deployment): wire dl-mnist-cnn into dl-network with Nginx routing"
```

---

## Phase 2a.8 — Landing Page + About Drawer + Feedback Widget

**Landing page (`website/index.html`):**
- Change dl-mnist-cnn card from `status-planned` → `status-live`
- Update route to `/dl/mnist-cnn/`
- Add `dl-link` class with `href="/dl/mnist-cnn/"`
- Update domain count: `0 live · 3 planned` → `1 live · 2 planned`

**About drawer (new since this plan was written — every demo now ships with one):**
- Create `ml/dl-mnist-cnn/presentation-logic/api/about.json` with sections: Project Summary, Dataset, CNN Architecture (with Mermaid diagram), Training, Metrics (use `{{tokens}}` for live values from `/model-info`), Code Walkthrough, Author/Credits, Learn More
- Reuse the About drawer JS/CSS from iris-knn/housing-linear ui.html — it's the same pattern, only the JSON differs

**Feedback widget (new since this plan was written):**
- Add `<script src="/feedback-widget.js"></script>` before `</body>` in `ui.html`
- That's the whole change — the widget auto-detects `page_id`, the Nginx `/feedback/` route already exists, and the rate limiter is shared (per-page, 3-per-5min)

```bash
git commit -m "feat(website): mark dl-mnist-cnn as live on landing page"
```

---

## Phase 2a.9 — Merge & Tag

```bash
cd /volume1/pandya-homelab
git log main..HEAD --oneline   # review all commits

git checkout main
git merge --ff-only dl-mnist-cnn/scaffold

git tag v.dl-mnist-cnn-1.0.0 -m "dl-mnist-cnn: CNN handwritten digit classifier with canvas UI"
git log --oneline | head -5
```

---

## Exit Criteria — Phase 2a Complete

- [ ] CNN trains to ≥98% accuracy
- [ ] All tests passing (TIER 1)
- [ ] Docker image builds cleanly
- [ ] `https://pandyahomelab.com/dl/mnist-cnn/` loads canvas drawing UI
- [ ] Drawing a digit returns prediction with confidence bars
- [ ] MLflow experiment `dl-mnist-cnn` visible at `/mlflow/`
- [ ] Landing page shows dl-mnist-cnn as Live
- [ ] Merged to main, tagged `v.dl-mnist-cnn-1.0.0`

---

## IP/Port Reference Card (refreshed May 2026 — full V3 domain autonomy)

**ml-network (172.20.0.0/24) — existing, unchanged:**

| Service | Container IP | Host Port | URL Path |
|---|---|---|---|
| ml-postgres | 172.20.0.2 | 5433 | — |
| ml-minio | 172.20.0.3 | 9000/9001 | — |
| ml-redis | 172.20.0.4 | 6379 | — |
| ml-mlflow | 172.20.0.5 | — | /mlflow/ |
| ml-iris-knn | 172.20.0.10 | 8001 | /ml/iris-knn/ |
| ml-housing-linear | 172.20.0.11 | 8002 | /ml/housing-linear/ |
| ml-titanic-automl | 172.20.0.12 | 8003 | /ml/titanic-automl/ |
| Nginx on ml-net | 172.20.0.20 | — | proxy attachment |
| analytics-ingester | 172.20.0.30 | — | platform service |
| admin-portal | 172.20.0.31 | — | /admin/, /feedback/ |

**dl-network (172.21.0.0/24) — instantiated by this phase:**

| Service | Container IP | Host Port | URL Path |
|---|---|---|---|
| dl-postgres | 172.21.0.2 | 5434 | — |
| dl-minio | 172.21.0.3 | 9002/9003 | — |
| dl-redis | 172.21.0.4 | 6380 | — |
| dl-mlflow | 172.21.0.5 | — | https://mlflow-dl.pandyahomelab.com/ |
| **dl-mnist-cnn** | **172.21.0.10** | **8010** | **/dl/mnist-cnn/** |
| Nginx on dl-net | 172.21.0.20 | — | proxy attachment |

**Pandya proxy network (172.24.0.0/24):**

| Service | Container IP | Host Port | URL Path |
|---|---|---|---|
| pandya-nginx | 172.24.0.2 | 8080/8443 | / |

**No cross-network attachments.** ml-network and dl-network are independent — DL demos cannot reach ml-mlflow or ml-postgres, and vice versa.

---

## Key Differences vs Phase 1b/1c

| Aspect | ML (Phase 1b) | DL (Phase 2a) |
|---|---|---|
| Framework | scikit-learn | PyTorch |
| Image size | ~400MB | ~2.5GB |
| Training time | <5 seconds | ~8 min (CPU) |
| Input type | float array (4-8 features) | pixel array (784 values) |
| UI | sliders | canvas drawing |
| Model format | sklearn pickle | PyTorch state_dict |
| test fixture scope | function | **module** (train once per test session) |

## MLflow Notes (pre-solved — see mlflow_operational_lessons.md)
- Same `MLFLOW_TRACKING_URI: http://ml-mlflow:5000` in docker-compose.dev.yml
- Same `mlflow-artifacts:/` default artifact root (already configured on server)
- dl-mnist-cnn connects to `ml_ml-network` to reach MLflow
- Experiment will be `dl-mnist-cnn`, experiment_id will be auto-assigned (3 or 4)
