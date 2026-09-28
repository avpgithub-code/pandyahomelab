# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] — 2026-09-28

### Changed
- `ui.html`: the About panel's Mermaid 10.9.8 now loads from the site's own `/vendor/` copy instead of cdn.jsdelivr.net, so visitors' browsers contact no third party (see `website/vendor/README.md`).
- `about.json`: new Dataset section naming the source and its licence, matching the NLP demos.

## [1.0.0-alpha1] — 2026-05-05

### Added
- Initial ml-iris-knn project scaffold
- K-Nearest Neighbors (k-NN) classifier implementation
- 3-layer architecture (presentation, application, db logic)
- FastAPI application with /health and /predict endpoints
- Pydantic schemas for iris classification requests/responses
- Data loader for Iris dataset (CSV, local)
- Data preprocessor with StandardScaler normalization
- Pytest tests for all layers (coverage > 70%)
- Docker multi-stage build
- Makefile with full development workflow
- JSON structured logging

### Infrastructure
- PostgreSQL connection for prediction history
- MinIO integration for model artifacts
- Redis integration for caching
- MLflow tracking for experiments

### Testing
- Unit tests: data loaders, preprocessor, classifier
- API tests: health endpoint, prediction validation
- Integration tests: database connectivity, service composition

## Template Versioning

This template is versioned alongside ADR-013, ADR-014. When those ADRs evolve, this template is updated and version incremented. Projects created from v1.0 keep v1.0 in their README unless explicitly migrated.
