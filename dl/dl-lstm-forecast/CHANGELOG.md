# Changelog

All notable changes to dl-lstm-forecast will be documented in this file.

## [1.0.0-alpha1] — 2026-05-25

### Added
- Initial project scaffold (Phase 2b.1) — copied from `ml/_templates/ml-project-template/`
- 3-layer architecture (presentation, application, db logic) per ADR-013
- Python import-compatible symlinks: `application_logic`, `db_logic`, `presentation_logic`
- Project metadata customized for the dl-lstm-forecast project

### Pending (Phase 2b.2 onward)
- db-logic: CitiBike dataset builder (`scripts/build_dataset.py`) + daily-counts loader + sliding-window transforms
- application-logic: PyTorch LSTMForecaster + MC-Dropout autoregressive forecast + PredictionService with MLflow tracking to `dl-mlflow:5000`
- presentation-logic: FastAPI routes + Chart.js forecast UI with confidence band + compare-to-actuals overlay + About drawer + feedback widget
- Tests across all three layers (tiny-subset fixtures for fast suite)
- Dockerfile (CPU-only PyTorch, baked CSV)
- Integration with dl-network (Phase 2b.6)
- Landing-page card flip Planned → Live (Phase 2b.8)
