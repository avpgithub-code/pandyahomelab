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
Read `mlflow_operational_lessons.md` in memory before starting — all MLflow gotchas are pre-solved.

---

## Pre-Flight Check

```bash
curl -k https://localhost:8443/ml/iris-knn/health     # Expected: {"status":"healthy",...}
curl -k https://localhost:8443/ml/housing-linear/health
curl http://localhost:5000/health                     # MLflow: OK
sudo docker ps | grep -E "iris|housing|mlflow|nginx"  # All healthy
```

---

## Phase 2a.1 — DL Domain Infrastructure

### Create branch
```bash
cd /volume1/pandya-homelab
git checkout -b dl-mnist-cnn/scaffold
```

### Create `deployment/dl/docker-compose.yml`

```yaml
version: '3.8'

# DL Domain Infrastructure
# dl-network: 172.21.0.0/24 (isolated per ADR-016)

networks:
  dl-network:
    driver: bridge
    ipam:
      driver: default
      config:
        - subnet: 172.21.0.0/24
          gateway: 172.21.0.1

  # Shared ML infra network (for MLflow access)
  ml_ml-network:
    external: true

services:
  # Placeholder — project containers added in docker-compose.dev.yml
```

### Create `deployment/dl/docker-compose.dev.yml`

```yaml
version: '3.8'

services:
  dl-mnist-cnn:
    image: dl-mnist-cnn:latest
    container_name: dl-mnist-cnn
    environment:
      PYTHONPATH: /app
      MLFLOW_TRACKING_URI: http://ml-mlflow:5000
    ports:
      - "8010:8000"
    volumes:
      - dl_mnist_data:/app/data
    networks:
      dl-network:
        ipv4_address: 172.21.0.10
      ml_ml-network:
        ipv4_address: 172.20.0.30
    depends_on: []
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

volumes:
  dl_mnist_data:
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

### Step 1: Start DL infrastructure

```bash
cd /volume1/pandya-homelab/deployment/dl/
sudo docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
sleep 60
sudo docker-compose -f docker-compose.yml -f docker-compose.dev.yml ps
```

### Step 2: Rebuild Nginx with dl-network

```bash
cd /volume1/pandya-homelab/deployment/nginx/
sudo docker-compose down
sudo docker build -t pandya-nginx:latest .
sudo docker-compose up -d
sleep 10
```

### Step 3: Verify end-to-end

```bash
curl -k https://localhost:8443/dl/mnist-cnn/health
curl -k "https://localhost:8443/dl/" | python3 -m json.tool
```

```bash
git commit -m "feat(deployment): wire dl-mnist-cnn into dl-network with Nginx routing"
```

---

## Phase 2a.8 — Landing Page Update

In `website/index.html`:
- Change dl-mnist-cnn card from `status-planned` → `status-live`
- Update route to `/dl/mnist-cnn/`
- Add `dl-link` class with `href="/dl/mnist-cnn/"`
- Update domain count: `0 live · 3 planned` → `1 live · 2 planned`

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

## IP/Port Reference Card

| Service | Container IP | Host Port | URL Path |
|---|---|---|---|
| Nginx (proxy) | 172.24.0.2 | 8080/8443 | / |
| ml-postgres | 172.20.0.2 | 5433 | — |
| ml-minio | 172.20.0.3 | 9000/9001 | — |
| ml-redis | 172.20.0.4 | 6379 | — |
| ml-mlflow | 172.20.0.5 | 5000 | /mlflow/ |
| ml-iris-knn | 172.20.0.10 | 8001 | /ml/iris-knn/ |
| ml-housing-linear | 172.20.0.11 | 8002 | /ml/housing-linear/ |
| Nginx on ml-net | 172.20.0.20 | — | proxy only |
| **dl-mnist-cnn** | **172.21.0.10** | **8010** | **/dl/mnist-cnn/** |
| Nginx on dl-net | 172.21.0.20 | — | proxy only |

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
