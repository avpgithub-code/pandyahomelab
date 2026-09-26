"""Universal Dependencies UPOS (17 tags) -> Petrov et al. (2012) universal tagset (12 tags).

Both EWT's gold tags and spaCy's `token.pos_` are UPOS, so one mapping puts both
taggers on the same 12 labels. SCONJ -> ADP follows NLTK's Penn Treebank mapping
(IN -> ADP), so the tags mean what they mean in NLTK's `tagset="universal"`.
"""
from typing import Dict, List

UNIVERSAL12: List[str] = [
    "NOUN", "VERB", "ADJ", "ADV", "PRON", "DET", "ADP", "NUM", "CONJ", "PRT", ".", "X",
]

UPOS_TO_12: Dict[str, str] = {
    "NOUN": "NOUN", "PROPN": "NOUN",
    "VERB": "VERB", "AUX": "VERB",
    "ADJ": "ADJ",
    "ADV": "ADV",
    "PRON": "PRON",
    "DET": "DET",
    "ADP": "ADP", "SCONJ": "ADP",
    "NUM": "NUM",
    "CCONJ": "CONJ",
    "PART": "PRT",
    "PUNCT": ".",
    "SYM": "X", "INTJ": "X", "X": "X", "SPACE": "X",
}

TAG_NAMES: Dict[str, str] = {
    "NOUN": "noun (incl. proper nouns)",
    "VERB": "verb (incl. auxiliaries)",
    "ADJ": "adjective",
    "ADV": "adverb",
    "PRON": "pronoun",
    "DET": "determiner / article",
    "ADP": "adposition / subordinator",
    "NUM": "numeral",
    "CONJ": "coordinating conjunction",
    "PRT": "particle (to, not, 's)",
    ".": "punctuation",
    "X": "other (symbols, interjections, foreign)",
}


def to_universal12(upos: str) -> str:
    return UPOS_TO_12.get(upos, "X")
