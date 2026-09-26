# nlp-ewt-hmm

Phase 3d: a part-of-speech tagger. A bigram hidden Markov model counted by hand from
the Universal Dependencies English Web Treebank and decoded with Viterbi, next to
spaCy's `en_core_web_sm` tagger on the same tokens. The demo shows both taggers' tags,
the full Viterbi trellis with its best path, and the HMM's transition and emission tables.

Built from lecture L7 of the End-to-End NLP course. See `docs/PHASE_3_MASTER_PLAN.md`.

| | |
|---|---|
| Container | `nlp-ewt-hmm` · 172.22.0.13:8000 · `127.0.0.1:8023` |
| Route | `/nlp/ewt-hmm/` |
| MLflow | experiment `nlp-ewt-hmm` on `mlflow-nlp.pandyahomelab.com` (parent run + one child run per unknown-word strategy + `spacy-sm`) |

## Status

Shipped as 1.0.0 on 2026-09-26 (see CHANGELOG.md). EWT test set (2,077 sentences, 25,094 words, universal 12 tags):

| Tagger | Accuracy | Unknown words (9.1% of test) |
|---|---|---|
| HMM, add-1 smoothing | 87.4% | 36.7% |
| HMM, rare words → `<UNK>` | 92.7% | 69.0% |
| **HMM, rare words → suffix/shape classes** (the demo) | **94.4%** | **82.8%** |
| spaCy `en_core_web_sm` 3.7.1 | 95.1% | 88.1% |

## Gate decisions (2026-09-26)

- **Corpus:** UD English EWT r2.16 (CC BY-SA 4.0, official split), pinned to commit
  `4c89b58` and sha256-checked. Brown and the NLTK treebank sample were benchmarked too:
  both use Penn Treebank tagging conventions, which spaCy doesn't follow, so spaCy
  looked worse than it is; and the treebank sample is non-commercial.
- **Tags:** UPOS 17 → universal 12 (PROPN→NOUN, AUX→VERB, SCONJ→ADP, CCONJ→CONJ,
  PART→PRT, PUNCT→`.`, SYM/INTJ→X), for gold and spaCy alike.
- **Unknown words:** hapaxes rewritten to suffix/shape classes; add-1 transitions.
- **Training at warm-up:** the HMM counts in ~1.2 s; tagging the test set with spaCy
  takes most of the ~20 s warm-up.

Reproduce with `python3 scripts/benchmark_gate.py` (`--nltk-data DIR` adds Brown and
the treebank sample; see the script's docstring).

## Develop

```sh
make data        # ~16 MB into data/ewt/, checksum-verified (no make on the NAS: python3 scripts/fetch_ewt.py)
make test-unit   # synthetic CoNLL-U written by tests/conftest.py; needs spaCy + en_core_web_sm
make docker-build
```

## Data mount and the Synology ACL

The container runs as `appuser` (uid 1000) and mounts `data/ewt` read-only. EWT's
licence would allow baking it into the image, but it is mounted like every Phase 3
dataset. On `/volume1` the Synology ACL only grants administrators by default, so
after `make data` on a fresh checkout:

```sh
synoacltool -add data/ewt "everyone:*:allow:r-x---a-R-c--:fd--"
```

## Attribution

UD English EWT annotations © 2013–2021 The Board of Trustees of The Leland Stanford
Junior University, licensed CC BY-SA 4.0. The underlying texts come from the LDC
English Web Treebank.
