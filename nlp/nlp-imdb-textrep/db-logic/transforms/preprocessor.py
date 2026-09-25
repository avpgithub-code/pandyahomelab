"""Text preprocessing — the L3 recipe, as named, pure str -> str steps.

The same pipeline feeds three consumers: the representations (transform), the
UI's "show the pipeline" panel (trace), and the About drawer's `text-pipeline`
section (step names via /model-info).

Stopword removal is deliberately NOT a step here. It is shown per token in the
token panel (tokens.py) instead, because dropping stopwords throws away "not",
"no" and "never", which carry most of a movie review's negation.
"""
import re
from typing import Callable, Dict, List, Tuple

_HTML = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://\S+|www\.\S+")
# Pictographs, dingbats, flags and the emoji presentation selector.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U0000FE0F]"
)
_PUNCT = re.compile(r"[^\w\s]")
_SPACE = re.compile(r"\s+")

# The lecture's "chat word treatment": expand the short forms reviewers type.
CHAT_WORDS = {
    "afaik": "as far as i know", "asap": "as soon as possible", "btw": "by the way",
    "fyi": "for your information", "gr8": "great", "idk": "i do not know",
    "imho": "in my humble opinion", "imo": "in my opinion", "irl": "in real life",
    "lol": "laughing out loud", "omg": "oh my god", "tbh": "to be honest",
    "thx": "thanks", "u": "you", "w8": "wait", "wtf": "what the heck",
}


def lowercase(text: str) -> str:
    return text.lower()


def strip_html(text: str) -> str:
    # IMDB reviews carry <br /> line breaks inside the text.
    return _HTML.sub(" ", text)


def strip_urls(text: str) -> str:
    return _URL.sub(" ", text)


def strip_emojis(text: str) -> str:
    return _EMOJI.sub(" ", text)


_CHAT = re.compile(r"\b(" + "|".join(map(re.escape, CHAT_WORDS)) + r")\b")


def expand_chat_words(text: str) -> str:
    # Whole-word match, so "gr8!!" expands before punctuation is stripped.
    return _CHAT.sub(lambda m: CHAT_WORDS[m.group(1)], text)


def strip_punctuation(text: str) -> str:
    return _PUNCT.sub(" ", text)


def collapse_whitespace(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


STEPS: List[Tuple[str, Callable[[str], str]]] = [
    ("lowercase", lowercase),
    ("strip_html", strip_html),
    ("strip_urls", strip_urls),
    ("strip_emojis", strip_emojis),
    ("expand_chat_words", expand_chat_words),
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
