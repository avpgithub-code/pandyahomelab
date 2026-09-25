# nlp-imdb-textrep

Phase 3b: a text preprocessing and representation lab. Type any text and see every
cleaning step, stems vs lemmas, and four vector representations, each scored by the
same logistic regression trained on IMDB movie reviews.

Built from lectures L3 (preprocessing) and L4 (text representation) of the End-to-End
NLP course. See `docs/PHASE_3_MASTER_PLAN.md`.

| | |
|---|---|
| Container | `nlp-imdb-textrep` · 172.22.0.11:8000 · `127.0.0.1:8021` |
| Route | `/nlp/imdb-textrep/` |
| MLflow | experiment `nlp-imdb-textrep` on `mlflow-nlp.pandyahomelab.com` (parent run + one child run per representation) |

## Status

Shipped as 1.0.0 on 2026-09-25 (see CHANGELOG.md).

| Representation | IMDB test accuracy |
|---|---|
| One-hot (binary BoW) | 87.0% |
| Bag-of-words (counts) | 86.6% |
| N-grams (1-2, counts) | 89.3% |
| TF-IDF (1-2 grams) | 89.9% |

## Develop

```sh
make data        # ~41 MB into data/imdb/, checksum-verified (no make on the NAS: python3 scripts/fetch_imdb.py)
make test-unit
make docker-build
```

Tests run on a synthetic IMDB written by `tests/conftest.py`. The token-panel tests
need spaCy + `en_core_web_sm` and skip without spaCy.

## Data mount and the Synology ACL

The container runs as `appuser` (uid 1000) and mounts `data/imdb` read-only. The IMDB
dataset card states no licence, so the data is never baked into the image. On
`/volume1` the Synology ACL only grants administrators by default, so after
`make data` on a fresh checkout:

```sh
synoacltool -add data/imdb "everyone:*:allow:r-x---a-R-c--:fd--"
```
