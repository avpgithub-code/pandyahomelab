"""Read the Cricsheet Register CSVs (ODC-BY 1.0).

people.csv: identifier, name, unique_name and 21 key_* columns (cross-site ids). The key columns are
folded to {source: [ids]}, with numbered variants merged: key_cricinfo, key_cricinfo_2 and
key_cricinfo_3 all become "cricinfo" (a player can have three Cricinfo ids, F3 §3).
names.csv: identifier, name (name variants).
"""
import csv
import json
import re
from typing import Dict, List, Tuple

from shared.exceptions import SourceError

PEOPLE_REQUIRED = ("identifier", "name", "unique_name", "key_cricinfo")
NAMES_REQUIRED = ("identifier", "name")
_NUMBERED = re.compile(r"_\d+$")


def _require(path: str, reader: csv.DictReader, required) -> None:
    missing = [c for c in required if c not in (reader.fieldnames or [])]
    if missing:
        raise SourceError("%s: missing columns %s" % (path, ", ".join(missing)))


def looks_like_people(path: str) -> bool:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.readline().startswith("identifier,name,unique_name,")


def looks_like_names(path: str) -> bool:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.readline().strip() == "identifier,name"


def read_people(path: str) -> List[Tuple[str, str, str, str]]:
    """[(identifier, name, unique_name, keys_json)], keys_json sorted for stable comparison."""
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        _require(path, reader, PEOPLE_REQUIRED)
        key_cols = [c for c in reader.fieldnames if c.startswith("key_")]
        rows = []
        for r in reader:
            ident = (r["identifier"] or "").strip()
            if not ident:
                continue
            keys: Dict[str, List[str]] = {}
            for col in key_cols:
                value = (r.get(col) or "").strip()
                if value:
                    keys.setdefault(_NUMBERED.sub("", col[4:]), []).append(value)
            rows.append((ident, r["name"].strip(), (r["unique_name"] or r["name"]).strip(),
                         json.dumps(keys, sort_keys=True)))
        return rows


def read_names(path: str) -> List[Tuple[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        _require(path, reader, NAMES_REQUIRED)
        return [(r["identifier"].strip(), r["name"].strip()) for r in reader
                if (r["identifier"] or "").strip() and (r["name"] or "").strip()]
