# nlp-text8-word2vec

Phase 3c: a Word2Vec explorer. CBOW, skip-gram and fastText trained on the same 17M
words of text8 (Wikipedia), next to GloVe 6B as a pretrained reference: nearest
neighbours, analogies, similarity and a 2-D map, answered by all four at once.

Built from lecture L5 of the End-to-End NLP course. See `docs/PHASE_3_MASTER_PLAN.md`.

| | |
|---|---|
| Container | `nlp-text8-word2vec` · 172.22.0.12:8000 · `127.0.0.1:8022` |
| Route | `/nlp/text8-word2vec/` |
| MLflow | experiment `nlp-text8-word2vec` on `mlflow-nlp.pandyahomelab.com` (parent run `train-text8` + one child run per model) |

## Status

Shipped as 1.0.0 on 2026-09-25 (see CHANGELOG.md).

| Model | Analogy · meaning | Analogy · grammar | WordSim-353 | Training |
|---|---|---|---|---|
| Word2Vec CBOW | 19.9% | 37.2% | 0.625 | 3.7 min |
| Word2Vec skip-gram | 29.7% | 40.9% | 0.685 | 11.0 min |
| fastText (skip-gram + subwords) | 23.5% | 71.9% | 0.622 | 21.3 min |
| GloVe 6B 100d (reference, top 50k) | 65.5% | 65.5% | 0.555 | pretrained |

## Training is offline

Training takes ~35 min on the NAS, so the service only loads saved vectors at
startup. Data and models live under `data/` (gitignored, dockerignored), mounted
read-only.

```sh
python3 scripts/fetch_data.py --data-dir data     # text8 + GloVe, checksum-verified (make data)
synoacltool -add data "everyone:*:allow:r-x---a-R-c--:fd--"   # once, so the non-root container can read
```

Train inside the image on nlp-network, so the run lands in nlp-mlflow (root only to
write data/models; files are handed back to avpadmin afterwards):

```sh
cd deployment/nlp
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps \
  --user 0:0 -v /volume1/pandya-homelab/nlp/nlp-text8-word2vec/data:/train-data \
  nlp-text8-word2vec sh -c "python scripts/train_embeddings.py --data-dir /train-data \
  && chown -R 1026:100 /train-data/models"
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --no-deps --force-recreate nlp-text8-word2vec
```

## Develop

```sh
make test-unit     # tiny models trained in tests/conftest.py; no text8 needed
make docker-build
```
