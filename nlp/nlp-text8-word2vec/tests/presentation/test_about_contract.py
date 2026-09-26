"""About drawer contract (docs/PHASE_3_MASTER_PLAN.md, "About drawer: section outline").

1. The standard sections exist, in order (demo-specific ones may sit between).
2. Every {{token}} in about.json resolves against a trained service's
   get_model_info() — otherwise the drawer shows raw braces.
"""
import json
import re
from pathlib import Path

import pytest

from application_logic.services.prediction_service import PredictionService

ABOUT = json.loads(
    (Path(__file__).resolve().parents[2] / "presentation-logic" / "api" / "about.json").read_text()
)
STANDARD_ORDER = [
    "problem", "approach", "text-pipeline", "architecture", "service-architecture",
    "network", "stack", "dataset", "limitations", "walkthrough", "metrics", "learn",
]
TOKEN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)


def _resolve(data, path):
    for key in path.split("."):
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


@pytest.fixture(scope="module")
def model_info():
    service = PredictionService()
    service.train()
    return service.get_model_info()


def test_standard_sections_in_order():
    ids = [s["id"] for s in ABOUT["sections"]]
    present = [i for i in ids if i in STANDARD_ORDER]
    assert present == STANDARD_ORDER, f"got {present}"


def test_every_section_has_title_and_icon():
    for s in ABOUT["sections"]:
        assert s.get("title") and s.get("icon"), s["id"]


def test_every_token_resolves(model_info):
    tokens = {m for s in _strings(ABOUT) for m in TOKEN.findall(s)}
    assert tokens, "about.json should use at least one live token"
    missing = sorted(t for t in tokens if _resolve(model_info, t) is None)
    assert not missing, f"unresolved tokens: {missing}"


def test_learn_links_mlflow_nlp():
    learn = next(s for s in ABOUT["sections"] if s["id"] == "learn")
    assert any("mlflow-nlp.pandyahomelab.com" in link["url"] for link in learn["links"])


def test_no_template_todos_left():
    leftovers = [s for s in _strings(ABOUT) if "TODO" in s]
    assert not leftovers, leftovers[:3]


def test_demo_specific_sections_present():
    ids = [s["id"] for s in ABOUT["sections"]]
    assert {"word2vec", "embedding-space"} <= set(ids)
