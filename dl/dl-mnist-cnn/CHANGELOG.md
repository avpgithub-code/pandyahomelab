# Changelog

All notable changes to dl-mnist-cnn will be documented in this file.

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
