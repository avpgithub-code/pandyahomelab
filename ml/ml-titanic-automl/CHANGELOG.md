# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0-alpha1] — 2026-05-08

### Added
- PyCaret AutoML classifier on Titanic survival dataset
- PostgreSQL persistence via SQLAlchemy (load-once, serve-from-db pattern)
- Full Pydantic v2 validation with `@field_validator`, `@model_validator`, `Annotated`, `ConfigDict`
- MLflow auto-logging via PyCaret `log_experiment=True`
- Leaderboard UI showing top 5 algorithms compared by AUC
- Example passengers: Rose (1st class) and Jack (3rd class)
- Business rule validation: first-class fare floor check

## [1.0.0] — 2026-05-05

### Added
- Initial project scaffold
- 3-layer architecture (presentation, application, db logic)
- FastAPI application with health check endpoint
- Pydantic schemas for request/response validation
- Pytest fixtures and sample tests
- Docker multi-stage build
- Makefile with lint, test, docker targets
- Environment configuration via .env
- JSON structured logging
- Data loader abstractions (local, S3, database)
- Model base class for inheritance

### Infrastructure
- PostgreSQL connection template
- MinIO object storage integration
- Redis cache integration
- MLflow tracking integration

### Documentation
- README with architecture explanation
- Per-layer implementation guide
- Deployment workflow (TIER 1, 2, 3)

## Template Versioning

This template is versioned alongside ADR-013, ADR-014. When those ADRs evolve, this template is updated and version incremented. Projects created from v1.0 keep v1.0 in their README unless explicitly migrated.
