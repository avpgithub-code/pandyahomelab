# Changelog — nlp-quora-randomforest

## [1.0.0] — 2026-09-25 (ship, tag `v.nlp-quora-randomforest-1.0.0`)

### Added
- db-logic: `loaders/quora.py` `QuoraPairLoader` over GLUE QQP (`nyu-mll/glue`, pinned revision); GLUE train → train, GLUE validation → test (GLUE test is unlabelled); stratified subsampling. `scripts/fetch_qqp.py` (`make data`) downloads with sha256 checks. The data is non-commercial, so `data/qqp/` is mounted read-only at runtime and never baked into the image.
- db-logic: `transforms/preprocessor.py` rewritten to the L8 steps (symbols, `[math]`, number shortening, contractions, HTML, punctuation); `transforms/features.py` builds the 22 L8 features (7 basic / 8 token / 3 length / 4 fuzzy) with NLTK stopwords and rapidfuzz.
- application-logic: `DuplicateClassifier` — shared-vocabulary BoW (3000 × 2) + features, kept sparse, into `RandomForestClassifier(100 trees, min_samples_leaf=2)`. Reports accuracy, precision, recall, F1, ROC-AUC, log loss, a threshold sweep and feature-group importance.
- presentation-logic: `/predict` takes `{question1, question2}` and returns P(duplicate), the 22 feature values and both preprocessing traces. UI with two inputs, client-side threshold slider and a "why" panel. About drawer with the standard sections plus `features` and `threshold`.
- Deployment: compose service at 172.22.0.10 / `127.0.0.1:8020` (non-root; Synology read ACE on `data/qqp`), Nginx route `/nlp/quora-randomforest/`, landing card ✓ Live.

### Ship metrics
- Test set: all 40,430 GLUE validation pairs. Train: 100k stratified rows.
- Accuracy **80.1%** (lecture: ~78% on 3k rows; always-"Not duplicate": 63%), precision 0.740, recall 0.708, F1 0.723, ROC-AUC 0.886, log loss 0.421.
- Warm-up ~5 min on the NAS (features ~65 s, forest ~200 s); container ~0.5 GB RSS; saved model 19 MB.
- `/predict`: ~0.08 s.

### Known limitations
- Overlap-based: misses paraphrases with few shared words and flags near-misses and negations as duplicates (see the About drawer).
- A `/predict` during the warm-up window waits for training; Cloudflare's 100 s origin limit can return an error in that window.
