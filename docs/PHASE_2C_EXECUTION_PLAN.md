# Phase 2c Execution Plan — dl-yolo-object-detection (Stub)

**Objective:** Build dl-yolo-object-detection — real-time object detection with bounding boxes
**URL:** `https://pandyahomelab.com/dl/object-detection/`
**Port:** 8012 (host) → 8000 (container)
**dl-network IP:** 172.21.0.12
**Tracking:** writes to `dl-mlflow:5000` (no ml-network attachment per V3 domain autonomy)
**Tag at ship:** `v.dl-object-detection-1.0.0`

> This is a **stub** — full step-by-step plan to be authored when 2a and 2b ship.
> 2c is the heaviest of the three: largest image, most user-facing complexity (image
> upload, drawing boxes), and the only one likely to need a pre-trained model rather
> than training from scratch on the NAS. Only **project-specific** decisions live here.

---

## Open decisions (need user sign-off before full plan is written)

### Model choice
| Option | Image size impact | Inference speed (CPU) | Coverage |
|---|---|---|---|
| **YOLOv8n** (ultralytics, ~6MB weights, COCO-80) | ~3.5GB image | ~0.5s / 640px image | 80 classes — broad |
| **YOLOv5s** (older but stable) | ~3GB | ~0.4s | 80 classes |
| **Faster R-CNN** (torchvision pretrained) | ~3GB | ~2-3s/image | 80 classes — slow on CPU |
| **MobileNet-SSD** (lightweight) | ~2.5GB | ~0.3s | 20 classes — less impressive |

**Default leaning:** YOLOv8n via ultralytics — best balance of demo wow-factor and CPU speed.

### Demo UI shape
- File-upload box + drag-and-drop (HTML5) → image preview
- "Detect" button → POST image → returns JSON `{boxes: [{class, score, x, y, w, h}, ...]}`
- Canvas overlay draws labeled bounding boxes on the preview
- Confidence threshold slider (default 0.5)
- "Use sample image" buttons (3–4 pre-shipped images) for visitors who don't want to upload
- About drawer + feedback widget

### Privacy
- Uploaded images should **not** be persisted. Process in-memory, return JSON, drop the bytes.
- No image bytes in MLflow either — only model parameters / inference stats.

---

## What 2a must have shipped first

Hard preconditions:
- `dl-network` and Nginx attachment live
- 2a and 2b shipped — so this is the third DL demo and validates the pattern at scale
- Nginx body-size limit raised for `/dl/object-detection/` (default 1MB is too small for photos — bump to ~10MB on this location)

---

## Steps (high-level — full plan TBD)

1. Decision gate: model + UI + confidence-threshold default (user sign-off)
2. Branch `dl-object-detection/scaffold`; copy template
3. db-logic: image preprocessor (resize, normalize, tensorize); no dataset loader (pre-trained model)
4. application-logic: `Detector` wrapping YOLOv8n; `PredictionService` logs inference latency + class distribution to MLflow
5. presentation-logic:
   - Schemas: `DetectionRequest` (base64 image or multipart upload), `DetectionResponse` (boxes array)
   - Routes: `POST /predict` (accepts image), `GET /model-info`, `GET /`, `GET /health`
   - `ui.html` with file upload + canvas overlay drawing
6. Tests
7. Dockerfile — pin ultralytics version, pre-download model weights at image-build time (no first-request stall)
8. `deployment/dl/docker-compose.dev.yml` — add service block, bump per-location Nginx `client_max_body_size`
9. Rebuild + deploy
10. About drawer, feedback widget
11. Landing page: flip 3rd DL card to Live → DL count = **3 live**
12. Merge + tag → **Phase 2 complete**

---

## Sanity checks before writing the full plan
- Confirm `.12` is free on `dl-network` (should be — 2a uses `.10`, 2b uses `.11`)
- Confirm host port 8012 is unused
- Decide whether weights ship inside the image (recommended — reproducible builds) or download at first run (faster image, longer first request)
- Decide on max image dimensions / file size and reject larger uploads cleanly with a 413
