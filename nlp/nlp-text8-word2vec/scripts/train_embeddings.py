"""Train CBOW, skip-gram and fastText on text8, trim GloVe, evaluate all four, save, log.

Takes ~35 min on the NAS, so it runs offline rather than at container start. Run it
inside the image, on nlp-network, so the run lands in nlp-mlflow:

    docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm \\
        --user 0:0 -v <project>/data:/app/data nlp-text8-word2vec \\
        python scripts/train_embeddings.py --data-dir /app/data

Writes data/models/<model>.kv (+ .npy) and data/models/metrics.json, which the
service loads at startup.
"""
import argparse
import json
import logging
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gensim.models import KeyedVectors  # noqa: E402
from gensim.models.word2vec import Text8Corpus  # noqa: E402
from gensim.test.utils import datapath  # noqa: E402

from application_logic.model.embeddings import (  # noqa: E402
    EPOCHS, FASTTEXT_BUCKET, GLOVE_KEEP, METRICS_FILE, MIN_COUNT, MODELS, NEGATIVE, TRAINED,
    VECTOR_SIZE, WINDOW, evaluate, train_model, trim,
)
from db_logic.loaders.sources import GLOVE_REPO, GLOVE_REVISION, TEXT8, models_dir, raw_dir  # noqa: E402

EXPERIMENT = "nlp-text8-word2vec"


def main(data_dir: str, workers: int) -> None:
    raw, out = raw_dir(data_dir), models_dir(data_dir)
    os.makedirs(out, exist_ok=True)
    corpus = Text8Corpus(os.path.join(raw, "text8"))
    analogies, wordsim = datapath("questions-words.txt"), datapath("wordsim353.tsv")
    results = {}
    for name in TRAINED:
        print(f"[train] {name} …", flush=True)
        kv, seconds = train_model(name, corpus, workers=workers)
        kv.save(os.path.join(out, f"{name}.kv"))
        results[name] = {"train_seconds": round(seconds, 1),
                         "vocabulary_size": len(kv.key_to_index), **evaluate(kv, analogies, wordsim)}
        print(f"[train] {name} done: {results[name]}", flush=True)
        del kv
    print("[glove] trimming …", flush=True)
    glove = trim(KeyedVectors.load(os.path.join(raw, "glove-wiki-gigaword-100.model"), mmap="r"))
    glove.save(os.path.join(out, "glove.kv"))
    results["glove"] = {"train_seconds": None, "vocabulary_size": len(glove.key_to_index),
                        **evaluate(glove, analogies, wordsim)}
    for name in MODELS:
        files = [f for f in os.listdir(out) if f.startswith(f"{name}.kv")]
        results[name]["size_mb"] = round(sum(os.path.getsize(os.path.join(out, f)) for f in files) / 1e6, 1)
    metrics = {
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "corpus": {"name": "text8", "url": TEXT8["url"], "tokens": sum(len(s) for s in corpus)},
        "reference": {"name": "GloVe 6B 100d", "source": f"{GLOVE_REPO}@{GLOVE_REVISION[:7]}",
                      "kept_words": GLOVE_KEEP},
        "params": {"vector_size": VECTOR_SIZE, "window": WINDOW, "min_count": MIN_COUNT,
                   "negative": NEGATIVE, "epochs": EPOCHS, "fasttext_bucket": FASTTEXT_BUCKET,
                   "workers": workers},
        "models": results,
    }
    with open(os.path.join(out, METRICS_FILE), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[done] wrote {out}/{METRICS_FILE}", flush=True)
    log_to_mlflow(metrics, out)


def log_to_mlflow(metrics: dict, out: str) -> None:
    """Parent run + one child run per model; classic log_artifact path (Phase 2b.10)."""
    try:
        import mlflow
        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://nlp-mlflow:5000"))
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name="train-text8") as run:
            mlflow.log_params({**metrics["params"], "corpus": "text8",
                               "corpus_tokens": metrics["corpus"]["tokens"],
                               "reference": metrics["reference"]["source"]})
            for name, r in metrics["models"].items():
                with mlflow.start_run(run_name=name, nested=True):
                    mlflow.log_params({"model": MODELS[name]})
                    mlflow.log_metrics({k: v for k, v in r.items() if isinstance(v, (int, float))})
            try:
                mlflow.log_artifact(os.path.join(out, METRICS_FILE), artifact_path="evaluation")
                for f in sorted(os.listdir(out)):
                    if f.startswith(("cbow.kv", "skipgram.kv")):
                        mlflow.log_artifact(os.path.join(out, f), artifact_path="model")
            except Exception as e:
                logging.warning(f"MLflow artifact logging skipped: {e}")
            print(f"[mlflow] run {run.info.run_id}", flush=True)
    except Exception as e:
        logging.warning(f"MLflow logging skipped: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    main(args.data_dir, args.workers)
