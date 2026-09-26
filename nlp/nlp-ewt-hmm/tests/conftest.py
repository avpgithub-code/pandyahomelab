"""Pytest configuration — adds project root to sys.path so the symlinked
db_logic / application_logic / presentation_logic packages resolve without
needing PYTHONPATH=/app in the environment.

EWT_DATA_DIR points at a small synthetic treebank in CoNLL-U, written once per
session, so tests never need `make data`. It includes comment lines and a
multi-word token range, like the real files.

MLflow points at a closed local port with retries off, so every test exercises
the graceful-degradation path quickly instead of waiting on HTTP back-off.
"""
import os
import random
import sys
import tempfile

os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:9"
os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] = "0"
os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] = "2"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (word, UPOS) templates. "can" is a noun after "the" and an auxiliary after a pronoun,
# so only the transitions can tell them apart.
_NOUNS = ["dog", "cat", "report", "meeting", "can", "house", "email"]
_ADJS = ["big", "quick", "old", "useful"]
_VERBS = ["saw", "sent", "liked", "opened"]
_NAMES = ["Alice", "Boston", "Google"]
_PRONS = ["I", "we", "they"]


def _sentence(rng):
    kind = rng.randrange(3)
    if kind == 0:
        return [("the", "DET"), (rng.choice(_ADJS), "ADJ"), (rng.choice(_NOUNS), "NOUN"),
                (rng.choice(_VERBS), "VERB"), ("the", "DET"), (rng.choice(_NOUNS), "NOUN"),
                (".", "PUNCT")]
    if kind == 1:
        return [(rng.choice(_PRONS), "PRON"), ("can", "AUX"), ("see", "VERB"),
                (rng.choice(_NAMES), "PROPN"), ("and", "CCONJ"), ("the", "DET"),
                (rng.choice(_NOUNS), "NOUN"), ("!", "PUNCT")]
    return [(rng.choice(_NAMES), "PROPN"), (rng.choice(_VERBS), "VERB"), ("3", "NUM"),
            (rng.choice(_NOUNS) + "s", "NOUN"), ("in", "ADP"), (rng.choice(_NAMES), "PROPN"),
            ("quickly", "ADV"), (".", "PUNCT")]


def _write_conllu(path, n, seed):
    rng = random.Random(seed)
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(f"# sent_id = synth-{seed}-{i}\n")
            if i == 0:
                # Multi-word token range: only the syntactic words 2-3 are tagged.
                f.write("1\tWe\twe\tPRON\t_\t_\t0\t_\t_\t_\n")
                f.write("2-3\tcan't\t_\t_\t_\t_\t_\t_\t_\t_\n")
                f.write("2\tca\tcan\tAUX\t_\t_\t0\t_\t_\t_\n")
                f.write("3\tn't\tnot\tPART\t_\t_\t0\t_\t_\t_\n")
                f.write("4\tgo\tgo\tVERB\t_\t_\t0\t_\t_\t_\n\n")
                continue
            for j, (w, t) in enumerate(_sentence(rng), 1):
                f.write(f"{j}\t{w}\t{w.lower()}\t{t}\t_\t_\t0\t_\t_\t_\n")
            f.write("\n")


_EWT_DIR = tempfile.mkdtemp(prefix="ewt-test-")
_write_conllu(os.path.join(_EWT_DIR, "en_ewt-ud-train.conllu"), 300, seed=1)
_write_conllu(os.path.join(_EWT_DIR, "en_ewt-ud-test.conllu"), 60, seed=2)
os.environ["EWT_DATA_DIR"] = _EWT_DIR
