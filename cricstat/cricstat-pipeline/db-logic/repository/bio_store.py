"""player_bio from the Wikidata/Commons enrichment (P0.5), re-applied on every build.

Kept out of serving_store.py on purpose: that file is hashed into rules_sha, and these rules (age,
blocklist, which id wins) may be tuned without forcing a 12-minute full rebuild.
"""
import csv
import datetime
import os
import sqlite3
from typing import Dict, Iterable, List, Optional, Set, Tuple


def is_minor(date_of_birth: Optional[str], on: datetime.date) -> bool:
    """Under 18 on `on`. With only a year (or year-month) known, assume the latest possible
    birthday, so anyone who might be under 18 counts as a minor."""
    if not date_of_birth:
        return False
    parts = [int(x) for x in date_of_birth.split("-")]
    y = parts[0]
    m = parts[1] if len(parts) > 1 else 12
    d = parts[2] if len(parts) > 2 else 31
    try:
        born = datetime.date(y, m, d)
    except ValueError:                                  # e.g. day 31 in a 30-day month
        born = datetime.date(y, m, 28)
    if born.month == 2 and born.day == 29:
        return on < datetime.date(born.year + 18, 3, 1)
    return on < born.replace(year=born.year + 18)


def read_blocklist(path: Optional[str]) -> Tuple[Set[str], Set[str]]:
    """sql/photo_blocklist.csv (qid,image_file,reason,added) → (qids, image files) whose photo
    is never shown, e.g. after a removal request."""
    if not path or not os.path.exists(path):
        return set(), set()
    qids, files = set(), set()
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("qid") or "").strip():
                qids.add(row["qid"].strip())
            if (row.get("image_file") or "").strip():
                files.add(row["image_file"].strip())
    return qids, files


def read_enrichment(raw: sqlite3.Connection) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """(wikidata_people by cricinfo id, commons_images by file). Empty before the first `enrich`
    (or on a raw store that predates migration 0003)."""
    def rows(sql):
        try:
            cur = raw.execute(sql)
        except sqlite3.OperationalError:
            return {}
        cols = [d[0] for d in cur.description]
        return {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}
    return (rows("SELECT * FROM wikidata_people WHERE qid IS NOT NULL"),
            rows("SELECT * FROM commons_images WHERE status = 'ok'"))


def bio_rows(people: Iterable[tuple], wiki: Dict[str, dict], images: Dict[str, dict],
             photo_dir: Optional[str], blocklist: Tuple[Set[str], Set[str]],
             today: datetime.date) -> Tuple[List[tuple], Dict[str, int]]:
    """One row per Register person with a Wikidata item, keyed by player_id (the build joins it to
    players). When a person has several cricinfo ids, the lowest one with an item wins."""
    out, n = [], dict(bio=0, full_names=0, photos=0, minors=0, blocked=0, photo_missing=0)
    block_q, block_f = blocklist
    for ident, _name, _unique, ids in people:
        cids = sorted((c for c in ids.get("cricinfo", []) if c in wiki), key=int)
        if not cids:
            continue
        w = wiki[cids[0]]
        minor = is_minor(w["date_of_birth"], today)
        img = images.get(w["image_file"]) if w["image_file"] else None
        if img and (minor or w["qid"] in block_q or w["image_file"] in block_f):
            n["blocked" if not minor else "minors"] += 1
            img = None
        elif minor:
            n["minors"] += 1
        if img and photo_dir and not os.path.exists(os.path.join(photo_dir, img["thumb_path"])):
            n["photo_missing"] += 1
            img = None
        out.append((ident, w["qid"], None if minor else w["date_of_birth"],
                    None if minor else w["birthplace"], w["country_for_sport"], w["fetched_at"],
                    w["label_en"],
                    img and img["thumb_path"], img and img["width"], img and img["height"],
                    img and img["licence"], img and img["licence_url"], img and img["author"],
                    img and img["description_url"]))
        n["bio"] += 1
        n["full_names"] += bool(w["label_en"])
        n["photos"] += bool(img)
    return out, n


def apply_bio(conn: sqlite3.Connection, rows: List[tuple]) -> None:
    """Replace player_bio inside the caller's transaction (players must be loaded already)."""
    conn.execute("DELETE FROM player_bio")
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _bio (player_id TEXT, wikidata_qid TEXT,"
                 " date_of_birth TEXT, birthplace TEXT, country_for_sport TEXT, fetched_at TEXT,"
                 " full_name TEXT, photo_file TEXT, photo_width INTEGER, photo_height INTEGER,"
                 " photo_licence TEXT, photo_licence_url TEXT, photo_author TEXT,"
                 " photo_source_url TEXT)")
    conn.execute("DELETE FROM _bio")
    conn.executemany("INSERT INTO _bio VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("INSERT INTO player_bio (player_key, wikidata_qid, date_of_birth, birthplace,"
                 " country_for_sport, fetched_at, full_name, photo_file, photo_width, photo_height,"
                 " photo_licence, photo_licence_url, photo_author, photo_source_url)"
                 " SELECT p.player_key, b.wikidata_qid, b.date_of_birth, b.birthplace,"
                 " b.country_for_sport, b.fetched_at, b.full_name, b.photo_file, b.photo_width,"
                 " b.photo_height, b.photo_licence, b.photo_licence_url, b.photo_author,"
                 " b.photo_source_url FROM _bio b JOIN players p USING (player_id)")
    conn.execute("DROP TABLE _bio")
