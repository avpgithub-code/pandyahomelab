# Changelog

All notable changes to dl-mnist-cnn will be documented in this file.

## [1.0.1] — 2026-08-27 (post-tag polish, back-ported from Phase 2b.10)

### Changed
- `application-logic/services/prediction_service.py`: replaced `mlflow.pytorch.log_model` with `tempfile.TemporaryDirectory` + `torch.save(state_dict)` + `mlflow.log_artifact` (classic per-run artifact upload path). Same fix landed on [dl-lstm-forecast](../dl-lstm-forecast/) in the same commit — see its CHANGELOG for the full write-up. Root reason: MLflow 3.11.1's LoggedModel + `--serve-artifacts` combo silently marks uploads Failed on `dl-mlflow`; classic path proven-good by direct probe.
- Model file now lands under the run's **Artifacts** tab as `model/mnist_cnn_state.pt` (not under **Logged Models**). Reload with `torch.load(state_path)` + `MnistCNN().load_state_dict(...)` rather than `mlflow.pytorch.load_model(uri)`.
- Verification: post-polish warm-up: `Test accuracy: 0.9891`. Artifact at `/mlartifacts/1/112be133d87549adbe41aeeec329f492/artifacts/model/`.

### Removed (from prior state)
- 5 pre-fix `LOGGED_MODEL_UPLOAD_FAILED` entries on the tracker (`dl-mnist-cnn` experiment id=1) — DELETE'd via `/api/2.0/mlflow/logged-models/{model_id}` so the public MLflow UI shows no Failed badges.

## [1.0.0-alpha1] — 2026-05-22

### Added
- Initial project scaffold (Phase 2a.2) — copied from `ml/_templates/ml-project-template/`
- 3-layer architecture (presentation, application, db logic) per ADR-013
- Python import-compatible symlinks: `application_logic`, `db_logic`, `presentation_logic`
- Project metadata customized for the dl-mnist-cnn project

### Pending (Phase 2a.3 onward)
- db-logic: MNIST data loader (torchvision) + preprocessor
- application-logic: PyTorch CNN model + prediction service with MLflow tracking to `dl-mlflow:5000`
- presentation-logic: FastAPI routes + HTML5 canvas drawing UI + About drawer + feedback widget
- Tests across all three layers
- Dockerfile (CPU-only PyTorch, ~2.5GB image)
- Integration with dl-network (Phase 2a.7)
- Landing-page card flip Planned → Live
