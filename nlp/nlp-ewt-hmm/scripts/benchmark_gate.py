"""Reproduce the Phase 3d gate benchmark (2026-09-26): which corpus, tag set and
unknown-word strategy, and is training quick enough to run at warm-up?

For each corpus: the project's HmmTagger with each unknown-word strategy, and spaCy
en_core_web_sm, on the same pre-tokenised test sentences.

    python3 scripts/benchmark_gate.py                       # EWT, 12 and 17 tags
    python3 scripts/benchmark_gate.py --nltk-data DIR       # + Brown and the treebank sample

EWT comes from data/ewt (make data). Brown and the NLTK treebank sample are only
needed to reproduce the gate's comparison; they are not part of the demo. Put
NLTK's corpora/brown.zip, corpora/treebank.zip and taggers/universal_tagset.zip
(nltk_data gh-pages, sha256 9b275f9b…, 9da92d76…, d490e1ae…) under DIR, unzipped.
They have no random split of their own: 90/10 by sentence, seed 42. The treebank
sample is non-commercial, so keep it out of the repo and the image.

Gate results on the NAS (py3.8, spaCy 3.7.5):
  EWT 12 tags   HMM laplace 87.4 · unk 92.7 · signatures 94.4 · spaCy 95.1
  EWT 17 tags   HMM signatures 91.5 · spaCy 91.3
  treebank      HMM signatures 95.2 · spaCy 94.6   (PTB conventions differ from spaCy's UD)
  Brown         HMM signatures 96.5 · spaCy 92.9   (same; plus 1960s text outside spaCy's data)
"""
import argparse
import os
import resource
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application_logic.model.hmm import UNKNOWN_STRATEGIES, HmmTagger  # noqa: E402
from application_logic.model.spacy_tagger import SpacyTagger  # noqa: E402
from db_logic.loaders.ewt import EwtLoader  # noqa: E402
from db_logic.transforms.tagset import UPOS_TO_12  # noqa: E402


def load_nltk(name, nltk_data):
    import nltk
    from nltk.tag import map_tag
    nltk.data.path.insert(0, nltk_data)
    from nltk.corpus import brown, treebank
    reader, src = (brown, "en-brown") if name == "brown" else (treebank, "en-ptb")
    # -NONE- are Penn Treebank null elements (traces), not words.
    sents = [[(w, map_tag(src, "universal", t)) for w, t in s if t != "-NONE-"]
             for s in reader.tagged_sents()]
    sents = [s for s in sents if s]
    idx = np.random.RandomState(42).permutation(len(sents))
    cut = int(len(sents) * 0.9)
    return [sents[i] for i in idx[:cut]], [sents[i] for i in idx[cut:]]


def evaluate(pred, test, known):
    ok = tot = uok = utot = 0
    for s, p in zip(test, pred):
        for (w, g), t in zip(s, p):
            tot += 1
            ok += g == t
            if w not in known:
                utot += 1
                uok += g == t
    return ok / tot, uok / max(utot, 1), utot / tot


def run(name, train, test, spacy_map):
    words = [[w for w, _ in s] for s in test]
    print(f"\n== {name}: train {len(train)} sents / {sum(map(len, train))} tok, "
          f"test {len(test)} sents / {sum(map(len, test))} tok")
    for strategy in UNKNOWN_STRATEGIES:
        t0 = time.perf_counter()
        hmm = HmmTagger(strategy).fit(train)
        fit = time.perf_counter() - t0
        t0 = time.perf_counter()
        pred = [hmm.tag(w) for w in words]
        sps = len(test) / (time.perf_counter() - t0)
        acc, uacc, urate = evaluate(pred, test, hmm.known)
        print(f"  HMM {strategy:<10} acc {acc:.4f}  unk-acc {uacc:.4f}  (unk {urate:.2%})  "
              f"fit {fit:.1f}s  {sps:.0f} sent/s")
    spacy = SpacyTagger()
    t0 = time.perf_counter()
    sp = [[spacy_map(t) for t in s] for s in spacy.tag_upos_many(words)]
    sps = len(test) / (time.perf_counter() - t0)
    acc, uacc, _ = evaluate(sp, test, hmm.known)
    agree = np.mean([a == b for x, y in zip(pred, sp) for a, b in zip(x, y)])
    print(f"  spaCy sm       acc {acc:.4f}  unk-acc {uacc:.4f}  {sps:.0f} sent/s  "
          f"agreement with HMM(signatures) {agree:.4f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", default="data/ewt")
    parser.add_argument("--nltk-data", help="directory with corpora/{brown,treebank} and taggers/universal_tagset")
    args = parser.parse_args()

    ewt = EwtLoader(args.data_dir)
    run("ewt (12 tags)", ewt.load("train"), ewt.load("test"), lambda u: UPOS_TO_12.get(u, "X"))
    run("ewt (17 tags)", ewt.load("train", universal12=False), ewt.load("test", universal12=False),
        lambda u: "X" if u == "SPACE" else u)
    if args.nltk_data:
        for name in ("treebank", "brown"):
            train, test = load_nltk(name, args.nltk_data)
            run(name, train, test, lambda u: UPOS_TO_12.get(u, "X"))
    print(f"\npeak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB")


if __name__ == "__main__":
    main()
