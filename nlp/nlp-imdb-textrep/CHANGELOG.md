# Changelog — nlp-imdb-textrep

## [1.0.0] — 2026-09-25 (ship, tag `v.nlp-imdb-textrep-1.0.0`)

### Added
- db-logic: `ImdbLoader` over `stanfordnlp/imdb` (pinned revision), `scripts/fetch_imdb.py` with sha256 checks; data mounted at runtime, never baked in (no stated licence). L3 preprocessing (HTML, URLs, emoji, chat words, punctuation; stopwords shown but kept). `TokenAnalyzer`: spaCy `en_core_web_sm` lemmas + POS vs NLTK Porter stems.
- application-logic: `RepresentationSuite` — one-hot and BoW share a unigram vocabulary (min_df 2), n-grams and TF-IDF share a 1-2 gram vocabulary (top 100k); an identical liblinear `LogisticRegression` per representation; per-text explanation (largest entries, words pushing each way). `worked_example()` encodes the lecture's four-document corpus every way.
- presentation-logic: `/predict` returns the pipeline trace, token table and all four representations; `/worked-example`; UI with token table, four representation cards, comparison table and worked-example tables. About drawer with the standard sections plus `representations` and `sparsity`.
- MLflow: parent run + nested child run per representation; `representations.joblib` + `comparison.json` artifacts.
- Deployment: compose service at 172.22.0.11 / `127.0.0.1:8021` (non-root, Synology read ACE on `data/imdb`), Nginx route `/nlp/imdb-textrep/`, landing card ✓ Live.

### Ship metrics (25k train / 25k test)
- TF-IDF 89.9% (ROC-AUC 0.963) · n-grams 89.3% · one-hot 87.0% · BoW counts 86.6%.
- Warm-up ~5 min; container ~0.75 GB RSS after warm-up (1.2 GB peak while training); saved models 14.8 MB.
- `/predict` ~25 ms in-process.

### Known limitations
- Word weights only: negation beyond adjacent word pairs, mixed reviews and sarcasm fail (see the About drawer). No neutral class.
