"""Token-level view for the playground: tokenization, stopwords, stemming vs lemmatization.

spaCy (en_core_web_sm, parser and NER disabled) tokenizes and lemmatizes; NLTK's
PorterStemmer stems. Lemmas use the part-of-speech tag ("better" -> "well" as an
adverb), stems just cut suffixes ("studies" -> "studi"). Only the text a visitor
submits goes through here; the representations train on the regex pipeline alone,
so warm-up never runs spaCy over 50k reviews.
"""
from typing import Dict, List, Optional

MAX_TOKENS = 60


class TokenAnalyzer:
    """Loads spaCy once (eager warm-up calls load()), then analyzes short texts."""

    def __init__(self, model: str = "en_core_web_sm"):
        self._model_name = model
        self._nlp = None
        self._stemmer = None

    def load(self) -> None:
        if self._nlp is None:
            import spacy
            from nltk.stem import PorterStemmer

            self._nlp = spacy.load(self._model_name, disable=["parser", "ner"])
            self._stemmer = PorterStemmer()

    @property
    def is_loaded(self) -> bool:
        return self._nlp is not None

    def analyze(self, text: str, limit: Optional[int] = MAX_TOKENS) -> Dict:
        self.load()
        rows: List[Dict] = []
        for tok in self._nlp(text):
            if tok.is_space or tok.is_punct:
                continue
            rows.append({
                "token": tok.text,
                "stem": self._stemmer.stem(tok.text),
                "lemma": tok.lemma_,
                "pos": tok.pos_,
                "is_stop": bool(tok.is_stop),
            })
        return {
            "tokens": rows[:limit] if limit else rows,
            "total": len(rows),
            "stopwords": sum(r["is_stop"] for r in rows),
            "stem_vocab": len({r["stem"] for r in rows}),
            "lemma_vocab": len({r["lemma"] for r in rows}),
        }
