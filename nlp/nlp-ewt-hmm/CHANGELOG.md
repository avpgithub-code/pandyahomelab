# Changelog — nlp-ewt-hmm

## [Unreleased] — 2026-09-28

### Changed
- `ui.html`: the About panel's Mermaid 10.9.8 now loads from the site's own `/vendor/` copy instead of cdn.jsdelivr.net, so visitors' browsers contact no third party (see `website/vendor/README.md`).

## [1.0.0] — 2026-09-26 (ship, tag `v.nlp-ewt-hmm-1.0.0`)

### Added
- db-logic: `EwtLoader` + CoNLL-U reader over UD English EWT r2.16 (pinned commit `4c89b58`, sha256-checked by `scripts/fetch_ewt.py`), mounted read-only. UPOS 17 → universal 12 mapping (SCONJ → ADP, as in NLTK's PTB mapping), applied to gold and spaCy alike.
- application-logic: `HmmTagger`, a bigram HMM in numpy (log-space start / add-1 transitions / emissions) with Viterbi returning the full trellis and backpointers; three unknown-word strategies (add-1 + shared `<UNK>`, rare words → `<UNK>`, rare words → suffix/shape classes). `SpacyTagger` wraps `en_core_web_sm` 3.7.1 (tok2vec → tagger → attribute_ruler + sentencizer) as tokenizer and reference tagger.
- presentation-logic: `/predict` returns both taggers' tags, unknown-word classes, emission-only tags and the trellis per sentence (≤ 80 tokens). UI with tag chips, a trellis heat map with the best path outlined, a model card (unknown-word strategies, top disagreements) and the HMM's transition/emission tables. About drawer with the standard sections plus `hmm`, `viterbi`, `unknown-words` and `spacy-comparison`; 12 × 12 confusion matrix.
- MLflow: parent run + nested child run per unknown-word strategy + `spacy-sm`; `hmm.npz` + `evaluation.json` artifacts.
- `scripts/benchmark_gate.py` reproduces the 3d gate benchmark (EWT 12/17 tags; Brown and the treebank sample with `--nltk-data`).
- Deployment: compose service at 172.22.0.13 / `127.0.0.1:8023` (non-root, Synology read ACE on `data/ewt`), Nginx route `/nlp/ewt-hmm/`, landing card ✓ Live.

### Ship metrics (EWT test: 2,077 sentences, 25,094 words, 9.1% unknown)
- HMM (suffix/shape classes) 94.4%, unknown words 82.8%, sentences 58.9%. spaCy sm 95.1% / 88.1% / 62.2%. Agreement 92.8%; on disagreements spaCy is right 53.1%, the HMM 42.9%.
- Unknown-word ladder: add-1 87.4% (36.7% unknown) → `<UNK>` 92.7% (69.0%) → classes 94.4% (82.8%).
- Warm-up ~20 s (HMM fit ~1 s); container ~0.24 GB RSS; saved HMM 0.1 MB; `/predict` ~75 ms.

### Known limitations
- One tag of left context: "Time flies like an arrow" (flies → NOUN), "The can of fish" (can → VERB, frequency beats context), "They can fish" (AUX merged into VERB hides the modal + verb rule), imperatives ("Book a table").
