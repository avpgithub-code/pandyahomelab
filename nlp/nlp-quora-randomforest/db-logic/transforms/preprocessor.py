"""Question preprocessing — the L8 recipe.

Each step is a named, pure str -> str function so the same pipeline feeds three
consumers: the feature builder (transform), the UI's "show the pipeline" panel
(trace), and the About drawer's `text-pipeline` section (step names via /model-info).

Order follows the lecture's preprocess(): lowercase, spell out symbols, drop
[math] tags, shorten big numbers, expand contractions, strip HTML, then drop
punctuation. HTML is stripped with a regex rather than BeautifulSoup; Quora
questions only carry the odd stray tag.
"""
import re
from typing import Callable, Dict, List, Tuple

_SYMBOLS = [("%", " percent"), ("$", " dollar "), ("₹", " rupee "), ("€", " euro "), ("@", " at ")]
_MATH = re.compile(r"\[math\]")
# 1,000,000,000 -> 1b before 1,000,000 -> 1m before 1,000 -> 1k (the lecture's order).
_NUMBERS = [
    (re.compile(r"([0-9]+)000000000"), r"\1b"),
    (re.compile(r"([0-9]+)000000"), r"\1m"),
    (re.compile(r"([0-9]+)000"), r"\1k"),
]
_HTML = re.compile(r"<[^>]+>")
_NON_WORD = re.compile(r"\W")
_SPACE = re.compile(r"\s+")

# The common English contractions from the lecture's table (trimmed of archaic
# forms like "y'all'd've" that never occur in QQP).
CONTRACTIONS = {
    "ain't": "am not", "aren't": "are not", "can't": "can not", "can't've": "can not have",
    "'cause": "because", "could've": "could have", "couldn't": "could not",
    "didn't": "did not", "doesn't": "does not", "don't": "do not", "hadn't": "had not",
    "hasn't": "has not", "haven't": "have not", "he'd": "he would", "he'll": "he will",
    "he's": "he is", "how'd": "how did", "how'll": "how will", "how's": "how is",
    "i'd": "i would", "i'll": "i will", "i'm": "i am", "i've": "i have",
    "isn't": "is not", "it'd": "it would", "it'll": "it will", "it's": "it is",
    "let's": "let us", "might've": "might have", "mightn't": "might not",
    "must've": "must have", "mustn't": "must not", "needn't": "need not",
    "o'clock": "of the clock", "shan't": "shall not", "she'd": "she would",
    "she'll": "she will", "she's": "she is", "should've": "should have",
    "shouldn't": "should not", "that'd": "that would", "that's": "that is",
    "there'd": "there would", "there's": "there is", "they'd": "they would",
    "they'll": "they will", "they're": "they are", "they've": "they have",
    "wasn't": "was not", "we'd": "we would", "we'll": "we will", "we're": "we are",
    "we've": "we have", "weren't": "were not", "what'll": "what will",
    "what're": "what are", "what's": "what is", "what've": "what have",
    "when's": "when is", "where'd": "where did", "where's": "where is",
    "who'll": "who will", "who's": "who is", "who've": "who have", "why's": "why is",
    "won't": "will not", "would've": "would have", "wouldn't": "would not",
    "y'all": "you all", "you'd": "you would", "you'll": "you will",
    "you're": "you are", "you've": "you have",
}


def lowercase(text: str) -> str:
    return text.lower().strip()


def replace_symbols(text: str) -> str:
    for symbol, word in _SYMBOLS:
        text = text.replace(symbol, word)
    return text


def strip_math_tags(text: str) -> str:
    return _MATH.sub("", text)


def shorten_numbers(text: str) -> str:
    text = text.replace(",000,000,000 ", "b ").replace(",000,000 ", "m ").replace(",000 ", "k ")
    for pattern, repl in _NUMBERS:
        text = pattern.sub(repl, text)
    return text


def expand_contractions(text: str) -> str:
    text = text.replace("’", "'")
    return " ".join(CONTRACTIONS.get(word, word) for word in text.split())


def strip_html(text: str) -> str:
    return _HTML.sub(" ", text)


def strip_punctuation(text: str) -> str:
    return _NON_WORD.sub(" ", text)


def collapse_whitespace(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


STEPS: List[Tuple[str, Callable[[str], str]]] = [
    ("lowercase", lowercase),
    ("replace_symbols", replace_symbols),
    ("strip_math_tags", strip_math_tags),
    ("shorten_numbers", shorten_numbers),
    ("expand_contractions", expand_contractions),
    ("strip_html", strip_html),
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
