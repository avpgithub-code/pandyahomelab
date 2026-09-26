"""Prediction service: EWT -> three HMMs (one per unknown-word strategy) + spaCy -> MLflow.

Same shape as the other Phase 3 demos: thread-safe lazy training (eager warm-up at
startup; concurrent calls during the train window block on a lock), a /model-info
payload that fills the About drawer's {{tokens}}, and MLflow logging that degrades
gracefully if nlp-mlflow is briefly unreachable.

Warm-up is well under a minute: counting the HMM tables takes ~1.5 s, and tagging
the 2,077 test sentences with spaCy ~30 s (gate benchmark, 2026-09-26).
"""
import json
import logging
import os
import tempfile
import threading
import time
from collections import Counter
from typing import Dict, List, Optional, Sequence

import numpy as np

from application_logic.model.hmm import (
    DEFAULT_STRATEGY,
    UNKNOWN_STRATEGIES,
    HmmTagger,
)
from application_logic.model.spacy_tagger import SpacyTagger
from db_logic.loaders.ewt import EWT_COMMIT, EWT_RELEASE, EwtLoader, Sentence
from db_logic.transforms.tagset import TAG_NAMES, UNIVERSAL12
from shared.config import get_config

logger = logging.getLogger(__name__)

_config = get_config()
_MLFLOW_URI = _config.MLFLOW_TRACKING_URI
_MLFLOW_PUBLIC_BASE = _config.MLFLOW_PUBLIC_BASE_URL
# Experiment per demo, named after the container (Phase 3 plan).
_EXPERIMENT = "nlp-ewt-hmm"
_DATASET = f"UD English EWT {EWT_RELEASE} (UniversalDependencies/UD_English-EWT@{EWT_COMMIT[:7]})"
ARCHITECTURE = "Bigram HMM (12 hidden tags, add-1 transitions) + Viterbi; spaCy en_core_web_sm as reference"
MAX_TOKENS = 80


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _score(gold: Sequence[Sentence], pred: Sequence[Sequence[str]], known: set) -> Dict:
    ok = tot = unk_ok = unk_tot = sent_ok = 0
    for s, p in zip(gold, pred):
        all_right = True
        for (w, g), t in zip(s, p):
            tot += 1
            ok += g == t
            all_right &= g == t
            if w not in known:
                unk_tot += 1
                unk_ok += g == t
        sent_ok += all_right
    known_tot = tot - unk_tot
    return {
        "accuracy": ok / tot,
        "unknown_accuracy": unk_ok / unk_tot if unk_tot else 0.0,
        "known_accuracy": (ok - unk_ok) / known_tot if known_tot else 0.0,
        "sentence_accuracy": sent_ok / len(gold),
    }


class PredictionService:
    """End-to-end orchestration for the nlp-ewt-hmm demo."""

    def __init__(self, loader: Optional[EwtLoader] = None, spacy: Optional[SpacyTagger] = None):
        self._loader = loader or EwtLoader(_config.EWT_DATA_DIR)
        self._spacy = spacy or SpacyTagger()
        self._hmm: Optional[HmmTagger] = None
        self._ladder: Dict = {}
        self._metrics: Dict = {}
        self._spacy_metrics: Dict = {}
        self._comparison: Dict = {}
        self._confusion: List[List[int]] = []
        self._split: Dict = {}
        self._training: Dict = {}
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False
        self._train_lock = threading.Lock()

    # ——— training ———
    def train(self) -> Dict:
        """Count three HMMs on EWT train, tag EWT test with each and with spaCy, log to MLflow.

        Thread-safe — concurrent callers during the warm-up window block here
        and pick up the cached results once the first caller finishes.
        """
        with self._train_lock:
            if self._ready:
                return self._metrics

            start = time.perf_counter()
            train = self._loader.load("train")
            test = self._loader.load("test")
            test_words = [[w for w, _ in s] for s in test]
            n_test_tokens = sum(map(len, test))

            for strategy in UNKNOWN_STRATEGIES:
                t0 = time.perf_counter()
                hmm = HmmTagger(strategy).fit(train, tags=UNIVERSAL12)
                fit_s = time.perf_counter() - t0
                t0 = time.perf_counter()
                pred = [hmm.tag(ws) for ws in test_words]
                decode_s = time.perf_counter() - t0
                self._ladder[strategy] = {
                    "name": UNKNOWN_STRATEGIES[strategy],
                    **_score(test, pred, hmm.known),
                    "fit_seconds": fit_s,
                    "sentences_per_second": len(test) / decode_s,
                }
                if strategy == DEFAULT_STRATEGY:
                    self._hmm, hmm_pred = hmm, pred

            t0 = time.perf_counter()
            spacy_pred = self._spacy.tag_many(test_words)
            spacy_s = time.perf_counter() - t0

            self._metrics = self._ladder[DEFAULT_STRATEGY]
            self._spacy_metrics = {
                **_score(test, spacy_pred, self._hmm.known),
                "sentences_per_second": len(test) / spacy_s,
            }
            self._confusion = self._confusion_matrix(test, hmm_pred)
            self._comparison = self._compare(test, hmm_pred, spacy_pred)

            n_unknown = sum(1 for s in test for w, _ in s if w not in self._hmm.known)
            self._split = {
                "train_sentences": len(train),
                "train_tokens": sum(map(len, train)),
                "test_sentences": len(test),
                "test_tokens": n_test_tokens,
                "unknown_tokens": n_unknown,
                "unknown_rate": n_unknown / n_test_tokens,
            }
            self._training = {"seconds": time.perf_counter() - start}

            with tempfile.TemporaryDirectory() as tmp:
                model_path = os.path.join(tmp, "hmm.npz")
                self._hmm.save(model_path)
                self._training["model_size_mb"] = os.path.getsize(model_path) / 1e6
                self._ready = True
                self._log_to_mlflow(model_path)
            return self._metrics

    def _confusion_matrix(self, gold: Sequence[Sentence], pred) -> List[List[int]]:
        idx = {t: i for i, t in enumerate(UNIVERSAL12)}
        cm = np.zeros((len(UNIVERSAL12), len(UNIVERSAL12)), dtype=int)
        for s, p in zip(gold, pred):
            for (_, g), t in zip(s, p):
                cm[idx[g], idx[t]] += 1
        return cm.tolist()

    def _compare(self, gold: Sequence[Sentence], hmm_pred, spacy_pred) -> Dict:
        """Where the two taggers disagree, and who was right."""
        agree = total = hmm_right = spacy_right = neither = 0
        pairs: Counter = Counter()
        words: Dict = {}
        for s, hp, sp in zip(gold, hmm_pred, spacy_pred):
            for (w, g), h, x in zip(s, hp, sp):
                total += 1
                if h == x:
                    agree += 1
                    continue
                pairs[(h, x)] += 1
                words.setdefault((h, x), Counter())[w.lower()] += 1
                if h == g:
                    hmm_right += 1
                elif x == g:
                    spacy_right += 1
                else:
                    neither += 1
        disagree = total - agree
        top = [
            {"hmm": h, "spacy": x, "count": n,
             "examples": ", ".join(w for w, _ in words[(h, x)].most_common(4))}
            for (h, x), n in pairs.most_common(8)
        ]
        return {
            "agreement": agree / total,
            "disagreements": disagree,
            "hmm_right": hmm_right,
            "spacy_right": spacy_right,
            "neither_right": neither,
            "hmm_right_pct": _pct(hmm_right / disagree) if disagree else "0.0%",
            "spacy_right_pct": _pct(spacy_right / disagree) if disagree else "0.0%",
            "neither_right_pct": _pct(neither / disagree) if disagree else "0.0%",
            "top_pairs": top,
        }

    # ——— inference ———
    def predict(self, text: str) -> Dict:
        """Tokenise with spaCy, tag every sentence with both taggers, return the trellises."""
        if not self._ready:
            self.train()
        sentences = self._spacy.analyze(text)
        budget = MAX_TOKENS
        out, truncated = [], False
        for s in sentences:
            if budget <= 0:
                truncated = True
                break
            if len(s["words"]) > budget:
                s = {k: v[:budget] for k, v in s.items()}
                truncated = True
            budget -= len(s["words"])
            out.append(self._explain(s))
        n_tokens = sum(len(s["tokens"]) for s in out)
        n_agree = sum(t["agree"] for s in out for t in s["tokens"])
        return {
            "tags": UNIVERSAL12,
            "sentences": out,
            "summary": {
                "tokens": n_tokens,
                "agree": n_agree,
                "unknown": sum(not t["known"] for s in out for t in s["tokens"]),
                "truncated": truncated,
            },
        }

    def _explain(self, s: Dict) -> Dict:
        words = s["words"]
        v = self._hmm.viterbi(words)
        trellis = v["trellis"]
        # Per column, each tag's share of the column's probability mass (softmax of
        # the Viterbi log scores). Only the ranking matters to Viterbi; shares make
        # the heat map readable.
        shares = np.exp(trellis - trellis.max(1, keepdims=True))
        shares = shares / shares.sum(1, keepdims=True)
        tokens = []
        for i, w in enumerate(words):
            known = w in self._hmm.known
            obs = self._hmm.observation(w)
            tokens.append({
                "word": w,
                "hmm": v["tags"][i],
                "spacy": s["tags"][i],
                "spacy_upos": s["upos"][i],
                "spacy_ptb": s["ptb"][i],
                "agree": v["tags"][i] == s["tags"][i],
                "known": known,
                "observation": obs if obs != w else None,
                "emission_best": self._hmm.emission_best(w),
            })
        return {
            "tokens": tokens,
            "trellis": {
                "shares": shares.round(4).tolist(),
                "log_scores": trellis.round(2).tolist(),
                "backpointers": v["back"].tolist(),
                "path": v["path"],
            },
        }

    # ——— metadata ———
    def get_model_info(self) -> Dict:
        """Model metadata for the About drawer and Model Card.

        DOES NOT trigger training — Cloudflare caps origin responses at 100s, so
        a metadata endpoint never trains (Phase 2a lesson). Before training it
        returns the static fields with empty metrics.
        """
        info = {
            "model_type": "Hidden Markov model (bigram) + Viterbi",
            "architecture": ARCHITECTURE,
            "dataset": _DATASET,
            "target": "Universal part-of-speech tag per token (12 tags)",
            "parameters": {
                "unknown_words": DEFAULT_STRATEGY,
                "transition_smoothing": "add-1",
                "max_tokens_per_request": MAX_TOKENS,
            },
            "tagset": {"labels": UNIVERSAL12, "names": TAG_NAMES},
            "metrics": {},
            "metrics_display": {},
            "unknown_ladder": None,
            "spacy_comparison": None,
            "hmm_tables": None,
            "confusion_matrix": None,
            "split": None,
            "training": None,
            "run_id": None,
            "experiment_id": None,
            "mlflow_url": None,
        }
        if not self._ready:
            return info
        m, sm = self._metrics, self._spacy_metrics
        lad = self._ladder
        info.update({
            "metrics": {"hmm": {k: v for k, v in m.items() if k != "name"}, "spacy": sm},
            "metrics_display": {
                "accuracy": _pct(m["accuracy"]),
                "unknown_accuracy": _pct(m["unknown_accuracy"]),
                "known_accuracy": _pct(m["known_accuracy"]),
                "sentence_accuracy": _pct(m["sentence_accuracy"]),
                "spacy_accuracy": _pct(sm["accuracy"]),
                "spacy_unknown_accuracy": _pct(sm["unknown_accuracy"]),
                "spacy_sentence_accuracy": _pct(sm["sentence_accuracy"]),
                "agreement": _pct(self._comparison["agreement"]),
                "gap": f"{(sm['accuracy'] - m['accuracy']) * 100:+.1f} points",
                "unknown_gap": f"{(sm['unknown_accuracy'] - m['unknown_accuracy']) * 100:+.1f} points",
                "hmm_speed": f"{m['sentences_per_second']:,.0f} sentences/s",
                "spacy_speed": f"{sm['sentences_per_second']:,.0f} sentences/s",
            },
            "unknown_ladder": {
                k: {
                    "name": r["name"],
                    "accuracy": _pct(r["accuracy"]),
                    "unknown_accuracy": _pct(r["unknown_accuracy"]),
                    "known_accuracy": _pct(r["known_accuracy"]),
                } for k, r in lad.items()
            },
            "spacy_comparison": {
                **{k: v for k, v in self._comparison.items() if k != "agreement"},
                "agreement": _pct(self._comparison["agreement"]),
                "disagreements": f"{self._comparison['disagreements']:,}",
                "model": self._spacy.version,
            },
            "hmm_tables": {
                "labels": UNIVERSAL12,
                "start": self._hmm.start_probs(),
                "transitions": self._hmm.transition_matrix(),
                "top_emissions": self._hmm.top_emissions(),
                "top_signatures": self._hmm.top_signatures(),
            },
            "confusion_matrix": {"labels": UNIVERSAL12, "matrix": self._confusion},
            "split": {
                **self._split,
                "train_sentences": f"{self._split['train_sentences']:,}",
                "train_tokens": f"{self._split['train_tokens']:,}",
                "test_sentences": f"{self._split['test_sentences']:,}",
                "test_tokens": f"{self._split['test_tokens']:,}",
                "unknown_tokens": f"{self._split['unknown_tokens']:,}",
                "unknown_rate": _pct(self._split["unknown_rate"]),
            },
            "training": {
                "seconds": f"{self._training['seconds']:.1f}s",
                "hmm_fit_seconds": f"{m['fit_seconds']:.1f}s",
                "model_size": f"{self._training['model_size_mb']:.1f} MB",
                "vocabulary_size": f"{self._hmm.vocabulary_size:,}",
                "emission_columns": f"{self._hmm.n_columns:,}",
            },
            "run_id": self._run_id,
            "experiment_id": self._experiment_id,
            "mlflow_url": (
                f"{_MLFLOW_PUBLIC_BASE}/#/experiments/{self._experiment_id}/runs/{self._run_id}"
                if self._run_id else None
            ),
        })
        return info

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _log_to_mlflow(self, model_path: str) -> None:
        """One parent run plus a nested child run per unknown-word strategy and one for
        spaCy, so MLflow's compare view lines them up. Classic `mlflow.log_artifact`
        path, NOT the LoggedModel API (Phase 2b.10 lesson, see mlflow_operational_lessons)."""
        try:
            import mlflow
            mlflow.set_tracking_uri(_MLFLOW_URI)
            mlflow.set_experiment(_EXPERIMENT)
            with mlflow.start_run() as run:
                mlflow.log_params({
                    "architecture": ARCHITECTURE,
                    "unknown_words": DEFAULT_STRATEGY,
                    "tagset": "universal-12",
                    "n_train_sentences": self._split["train_sentences"],
                    "n_test_sentences": self._split["test_sentences"],
                    "vocabulary_size": self._hmm.vocabulary_size,
                    "dataset": _DATASET,
                    "spacy_model": self._spacy.version,
                })
                mlflow.log_metrics({
                    "train_seconds": round(self._training["seconds"], 3),
                    "model_size_mb": round(self._training["model_size_mb"], 3),
                    **{f"hmm_{k}": v for k, v in self._metrics.items() if k != "name"},
                    **{f"spacy_{k}": v for k, v in self._spacy_metrics.items()},
                    "agreement": self._comparison["agreement"],
                })
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
                for strategy, r in self._ladder.items():
                    with mlflow.start_run(run_name=f"hmm-{strategy}", nested=True):
                        mlflow.log_params({"unknown_words": r["name"]})
                        mlflow.log_metrics({k: v for k, v in r.items() if k != "name"})
                with mlflow.start_run(run_name="spacy-sm", nested=True):
                    mlflow.log_params({"model": self._spacy.version})
                    mlflow.log_metrics(self._spacy_metrics)
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        mlflow.log_artifact(model_path, artifact_path="model")
                        ev_path = os.path.join(tmp, "evaluation.json")
                        with open(ev_path, "w") as f:
                            json.dump({
                                "labels": UNIVERSAL12, "confusion_matrix": self._confusion,
                                "ladder": self._ladder, "spacy": self._spacy_metrics,
                                "comparison": self._comparison,
                            }, f)
                        mlflow.log_artifact(ev_path, artifact_path="evaluation")
                except Exception as artifact_err:
                    logger.warning(f"MLflow artifact logging skipped: {artifact_err}")
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")
