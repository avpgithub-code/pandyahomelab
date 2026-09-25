"""The lecture's four-document toy corpus, encoded every way, as small dense tables.

Static: fit on four tiny documents, so it is cheap to compute per request and needs
no training. Powers the "Worked example" card and the About `representations` section.
"""
from typing import Dict, List

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

CORPUS = [
    "people watch campusx",
    "campusx watch campusx",
    "people write comment",
    "campusx write comment",
]


def _table(vectorizer, docs: List[str]) -> Dict:
    X = vectorizer.fit_transform(docs)
    return {
        "columns": [str(c) for c in vectorizer.get_feature_names_out()],
        "rows": [[round(float(v), 3) for v in row] for row in X.toarray()],
    }


def worked_example() -> Dict:
    vocab = CountVectorizer().fit(CORPUS).get_feature_names_out()
    first = CORPUS[0].split()
    return {
        "corpus": CORPUS,
        # True one-hot: one row per word of document 1, one column per vocabulary word.
        "one_hot_doc1": {
            "tokens": first,
            "columns": [str(c) for c in vocab],
            "rows": [[1 if w == c else 0 for c in vocab] for w in first],
        },
        "bow": _table(CountVectorizer(), CORPUS),
        "ngram": _table(CountVectorizer(ngram_range=(1, 2)), CORPUS),
        "tfidf": _table(TfidfVectorizer(), CORPUS),
    }
