"""Text preprocessing pipeline.

Each step is a named, pure str -> str function so the same pipeline feeds three
consumers: the model (transform), the UI's "show the pipeline" panel (trace), and
the About drawer's `text-pipeline` section (step names via /model-info).

Replace or extend STEPS with what the demo's lecture teaches (contractions,
stopwords, stemming/lemmatization, ...). Keep every step deterministic.
"""
import re
from typing import Callable, Dict, List, Tuple

_HTML = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://\S+|www\.\S+")
_PUNCT = re.compile(r"[^\w\s]")
_SPACE = re.compile(r"\s+")


def lowercase(text: str) -> str:
    return text.lower()


def strip_html(text: str) -> str:
    return _HTML.sub(" ", text)


def strip_urls(text: str) -> str:
    return _URL.sub(" ", text)


def strip_punctuation(text: str) -> str:
    return _PUNCT.sub(" ", text)


def collapse_whitespace(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


STEPS: List[Tuple[str, Callable[[str], str]]] = [
    ("lowercase", lowercase),
    ("strip_html", strip_html),
    ("strip_urls", strip_urls),
    ("strip_punctuation", strip_punctuation),
    ("collapse_whitespace", collapse_whitespace),
]


class TextPreprocessor:
    """Runs STEPS in order."""

    def __init__(self, steps: List[Tuple[str, Callable[[str], str]]] = None):
        self._steps = steps if steps is not None else STEPS

    @property
    def step_names(self) -> List[str]:
        return [name for name, _ in self._steps]

    def transform(self, text: str) -> str:
        for _, fn in self._steps:
            text = fn(text)
        return text

    def transform_many(self, texts: List[str]) -> List[str]:
        return [self.transform(t) for t in texts]

    def trace(self, text: str) -> List[Dict[str, str]]:
        """Output after every step — powers the UI's pipeline panel."""
        out = []
        for name, fn in self._steps:
            text = fn(text)
            out.append({"step": name, "text": text})
        return out
