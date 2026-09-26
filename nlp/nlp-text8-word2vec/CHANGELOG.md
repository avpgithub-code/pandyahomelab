# Changelog — nlp-text8-word2vec

## [1.0.0] — 2026-09-25 (ship, tag `v.nlp-text8-word2vec-1.0.0`)

### Added
- `scripts/fetch_data.py`: text8 (CC BY-SA) and GloVe 6B 100d (PDDL, `fse/glove-wiki-gigaword-100` pinned) with sha256 checks.
- `scripts/train_embeddings.py`: Word2Vec CBOW, skip-gram and fastText (100-d, window 5, min_count 5, 5 epochs, negative 5; fastText n-grams 3–6 with bucket 200k instead of 2M, 830 MB → 111 MB), GloVe trimmed to 50k; all four evaluated on the Google analogy set (split meaning/grammar, top 30k words) and WordSim-353; KeyedVectors + `metrics.json` saved; parent + 4 child runs in nlp-mlflow with the CBOW/skip-gram vectors as artifacts.
- Service loads the saved vectors at startup (seconds); `/neighbors`, `/analogy`, `/similarity`, `/map` (per-model PCA) answer for all four models; fastText answers for unseen words.
- UI with four columns per query and a comparison table; About drawer with `word2vec` and `embedding-space` sections.
- Deployment: compose service at 172.22.0.12 / `127.0.0.1:8022` (non-root, `data/` mounted read-only, Synology read ACE), Nginx route `/nlp/text8-word2vec/`, landing card ✓ Live.

### Ship metrics (text8, 17,005,207 words; 12,217 analogy questions in the top-30k vocabulary)
- Meaning analogies: GloVe 65.5% · skip-gram 29.7% · fastText 23.5% · CBOW 19.9%.
- Grammar analogies: fastText 71.9% · GloVe 65.5% · skip-gram 40.9% · CBOW 37.2%.
- WordSim-353: skip-gram 0.685 · CBOW 0.625 · fastText 0.622 · GloVe 0.555.
- Training: CBOW 222 s, skip-gram 661 s, fastText 1,275 s (3 workers). Container ~0.26 GB; queries ~50 ms.

### Known limitations
- One vector per word (no senses), antonyms close together, small 2006 corpus, stereotypes absorbed from the text. fastText's unseen-word vectors can be confident nonsense for look-alike words.
