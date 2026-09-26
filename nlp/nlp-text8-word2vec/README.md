# NLP project template

Starting point for every Phase 3 demo (3a–3d). It runs end-to-end as shipped: a
placeholder TF-IDF + logistic-regression classifier on a 24-sentence built-in
corpus, so the About drawer, Model Card, MLflow logging and tests all work before
the real model exists.

Built from the live `dl/dl-lstm-forecast` layout rather than the older
`ml/_templates/ml-project-template`, which has no UI, About drawer or `/model-info`
contract and whose healthcheck calls `curl` (not present in `python:slim`).

## Create a demo

```sh
nlp/_templates/new-nlp-project.sh nlp-quora-randomforest 0 "Quora Duplicate Questions"
```

The slot number (0–9) sets the container IP (`172.22.0.1<slot>`) and host port
(`127.0.0.1:802<slot>`) from `docs/NETWORK_CIDR_SUMMARY.md` §5/§8. Then fill in
`__DESCRIPTION__`, `__SUBTITLE__` and every `TODO`.

## What each demo inherits

| Piece | Where | Contract |
|---|---|---|
| About drawer | `presentation-logic/api/ui.html` | ml-iris-knn's drawer (the only copy that renders a confusion matrix). Fetches `/about` + `/model-info`, fills `{{tokens}}`, lazy-loads Mermaid. |
| About content | `presentation-logic/api/about.json` | All standard sections in plan order: problem → approach → text-pipeline → *demo-specific* → architecture → service-architecture → network → stack → dataset → limitations → walkthrough → metrics → learn. |
| Live numbers | `PredictionService.get_model_info()` | `metrics`, `metrics_display`, `confusion_matrix`, `split`, `training`, `preprocessing`, `run_id`, `experiment_id`, `mlflow_url`. Never trains. |
| MLflow | `PredictionService._log_to_mlflow()` | Classic `mlflow.log_artifact` path (not LoggedModel), experiment = container name, fails soft. Client pinned to the server's 3.11.1. |
| Warm-up | `presentation-logic/api/main.py` | Lifespan task trains in a thread; `/predict` during warm-up waits on the train lock. |
| Pipeline trace | `db-logic/transforms/preprocessor.py` | Named steps; `/predict` returns the text after each one for the UI panel. |

## Tests that guard the contract

`tests/presentation/test_about_contract.py` fails if a standard section is
missing or out of order, or if any `{{token}}` doesn't resolve against a trained
`get_model_info()`. Keep it green as you replace the placeholders.

```sh
make test-unit
```

## Deploying (per Phase 3 plan)

1. Add the service to `deployment/nlp/docker-compose.dev.yml` (IP/port from the
   script's output, `MLFLOW_TRACKING_URI: http://nlp-mlflow:5000`, depends_on
   `nlp-mlflow` only).
2. Build the image, `up -d --no-deps <service>`.
3. **Only after the container is up**, add its upstream + `location /nlp/<slug>/`
   to `deployment/nginx/nginx.conf` (Nginx resolves upstreams at startup), add the
   slug to the `/nlp/` listing, rebuild Nginx with `--no-cache` + `--force-recreate`.

Baked data goes under `db-logic/data/` — `/data/` at the project root is both
gitignored and dockerignored.
