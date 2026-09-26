"""Tests for db-logic — CoNLL-U reader, EWT loader and the UPOS -> universal-12 mapping."""
import os

import pytest

from db_logic.loaders.ewt import EWT_FILES, EwtLoader, ewt_url, read_conllu
from db_logic.transforms.tagset import UNIVERSAL12, UPOS_TO_12, to_universal12

UPOS17 = ["ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM", "PART",
          "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X"]


def test_every_upos_maps_into_the_12():
    assert all(UPOS_TO_12[u] in UNIVERSAL12 for u in UPOS17)
    assert set(UNIVERSAL12) == {UPOS_TO_12[u] for u in UPOS17}


def test_mapping_choices():
    assert to_universal12("PROPN") == "NOUN"
    assert to_universal12("AUX") == "VERB"
    assert to_universal12("SCONJ") == "ADP"
    assert to_universal12("PART") == "PRT"
    assert to_universal12("PUNCT") == "."
    assert to_universal12("SOMETHING-NEW") == "X"


def test_reader_skips_comments_and_multiword_ranges():
    path = os.path.join(os.environ["EWT_DATA_DIR"], "en_ewt-ud-train.conllu")
    first = read_conllu(path)[0]
    assert first == [("We", "PRON"), ("ca", "VERB"), ("n't", "PRT"), ("go", "VERB")]
    raw = read_conllu(path, universal12=False)[0]
    assert raw[1] == ("ca", "AUX")


def test_loader_reads_both_splits():
    loader = EwtLoader(os.environ["EWT_DATA_DIR"])
    assert len(loader.load("train")) == 300
    assert len(loader.load("test")) == 60


def test_missing_file_points_at_make_data(tmp_path):
    with pytest.raises(FileNotFoundError, match="make data"):
        EwtLoader(str(tmp_path)).load("train")


def test_urls_pin_a_commit():
    assert "/4c89b58" in ewt_url("train")
    assert set(EWT_FILES) == {"train", "test"}
