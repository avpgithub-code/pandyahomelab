"""spaCy en_core_web_sm as the reference tagger.

The small English pipeline's tagger is a CNN over hashed word features, trained on
OntoNotes 5 (news, broadcast, web text), not on EWT. Its UPOS `token.pos_` is mapped to
the same 12 tags as the gold data, and it tags exactly the tokens the HMM sees:
evaluation passes pre-split words, and the demo splits raw text with spaCy's
tokenizer plus a rule-based sentencizer before either tagger runs.
"""
from typing import Dict, List, Sequence

from db_logic.transforms.tagset import to_universal12

SPACY_MODEL = "en_core_web_sm"
# Only what `pos_` needs: tok2vec -> tagger -> attribute_ruler.
_EXCLUDE = ["parser", "ner", "lemmatizer"]


class SpacyTagger:
    def __init__(self):
        self._nlp = None

    def load(self) -> None:
        if self._nlp is None:
            import spacy
            nlp = spacy.load(SPACY_MODEL, exclude=_EXCLUDE)
            nlp.add_pipe("sentencizer")
            self._nlp = nlp

    @property
    def version(self) -> str:
        self.load()
        return f"{SPACY_MODEL} {self._nlp.meta.get('version', '')}".strip()

    def tag_upos_many(self, sentences: Sequence[Sequence[str]], batch_size: int = 256) -> List[List[str]]:
        """spaCy's own UPOS (17-tag) tags for pre-tokenised sentences."""
        from spacy.tokens import Doc
        self.load()
        docs = (Doc(self._nlp.vocab, words=list(words)) for words in sentences)
        return [[t.pos_ for t in doc] for doc in self._nlp.pipe(docs, batch_size=batch_size)]

    def tag_many(self, sentences: Sequence[Sequence[str]], batch_size: int = 256) -> List[List[str]]:
        """Universal-12 tags for pre-tokenised sentences."""
        return [[to_universal12(t) for t in s] for s in self.tag_upos_many(sentences, batch_size)]

    def analyze(self, text: str) -> List[Dict]:
        """Split raw text into sentences of tokens, with spaCy's tags for each token."""
        self.load()
        out = []
        for sent in self._nlp(text).sents:
            toks = [t for t in sent if not t.is_space]
            if toks:
                out.append({
                    "words": [t.text for t in toks],
                    "tags": [to_universal12(t.pos_) for t in toks],
                    "upos": [t.pos_ for t in toks],
                    "ptb": [t.tag_ for t in toks],
                })
        return out
