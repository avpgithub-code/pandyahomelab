# Changelog

All notable changes to dl-lstm-forecast will be documented in this file.

## [1.0.1] — 2026-08-27 (post-tag polish, Phase 2b.10)

### Changed
- `application-logic/services/prediction_service.py`: replaced `mlflow.pytorch.log_model` with `tempfile.TemporaryDirectory` + `torch.save(state_dict)` + `mlflow.log_artifact` (classic per-run artifact upload path). Reason: MLflow 3.11.1 + `--serve-artifacts` on `dl-mlflow` silently marks every LoggedModel upload as `LOGGED_MODEL_UPLOAD_FAILED`; identical config works on `ml-mlflow`, root cause not isolated, empirical workaround via classic path proven by direct probe.
- Model file now lands under the run's **Artifacts** tab as `model/lstm_forecaster_state.pt` (not under **Logged Models**). Reload with `torch.load(state_path)` + `LSTMForecaster().load_state_dict(...)` rather than `mlflow.pytorch.load_model(uri)`.
- Verification: run `skittish-snail-768` at `test_mape=0.2101`, `test_rmse=8164.52`, `epochs_run=16`. Artifact at `/mlartifacts/2/41f128e896f54a3f9f6ad2cace3c779c/artifacts/model/`.
- Same fix backported to [dl-mnist-cnn](../dl-mnist-cnn/) in the same commit; see its CHANGELOG.

### Removed (from prior state)
- 3 pre-fix `LOGGED_MODEL_UPLOAD_FAILED` entries on the tracker (`dl-lstm-forecast` experiment id=2) — DELETE'd via `/api/2.0/mlflow/logged-models/{model_id}` so the public MLflow UI shows no Failed badges.

## [1.0.0] — 2026-05-25 (ship, tag `v.dl-lstm-forecast-1.0.0`)

### Added
- db-logic (Phase 2b.2): `scripts/build_dataset.py` fetches toddwschneider/nyc-citibike-data's pre-aggregated daily CSV (883 rows, 2013-07-01 → 2015-11-30); `loaders/loaders.py` `BikeShareLoader` with cached load + time-respecting split + trailing-window lookup; `transforms/preprocessor.py` `make_windows` + `WindowScaler`. 15 tests on synthetic fixtures.
- application-logic (Phase 2b.3): `model/forecaster.py` `LSTMForecaster` (1-layer LSTM, hidden=64, dropout=0.2) + `enable_mc_dropout` + `TimeSeriesForecaster` train/evaluate/forecast wrapper (autoregressive 14-day rollout, MC Dropout N=30). `services/prediction_service.py` composes loader + scaler + forecaster + MLflow logging. 20 tests.
- presentation-logic (Phase 2b.4): FastAPI app with lifespan-based eager warm-up; routes `/`, `/about`, `/health`, `/history`, `/forecast`, `/model-info`; Chart.js UI with history line + forecast band + compare-to-actuals overlay + date picker + sample button; About drawer + feedback widget. 24 tests.
- Dockerfile + requirements + `.dockerignore` (Phase 2b.5).
- Compose service block + Nginx upstream/location (Phase 2b.6).
- Landing-page card flipped to ✓ Live (Phase 2b.8).

### Ship metrics
- Test MAPE: **21.0–21.4%** (varies by random init) on the last-180-days test window.
- Test RMSE: ~8,200 rides/day.
- Warm-up: ~10s on NAS CPU.
- Full forecast (14 days × 30 MC samples): ~1.5s.
- Test suite: 59 passing in ~17s.

### Known at ship time (not blocking)
- MLflow LoggedModel artifact upload silently fails on `dl-mlflow` (fixed in 1.0.1 above via post-tag polish).

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
