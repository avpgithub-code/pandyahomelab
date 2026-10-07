"""Wikidata + Commons enrichment of players (P0.5), weekly after `register`.

1. People: every player's ESPNcricinfo id (from the Register) is looked up on Wikidata (P2697), in
   batches, for the English name, date of birth, birthplace, country for sport and photo (P18).
   Ids never looked up, or last looked up over ENRICH_REFRESH_DAYS ago, are due; each batch is
   committed on its own, so an interrupted run resumes where it stopped.
2. Photos: each photo's licence, author and file page come from the Commons API. Only public
   domain, CC0, CC BY and CC BY-SA are kept, as one 330 px thumbnail under PHOTO_DIR (self-hosted:
   visitors' browsers never contact Wikimedia). No photo is fetched for anyone under 18.
The serving-DB build turns this into player_bio (and applies the age rule again, on its date).
"""
import datetime
import hashlib
import json
import os
import sqlite3
import time
from typing import Dict, List, Optional

from db_logic.loaders import wikimedia
from db_logic.repository.raw_store import RawStore, connect, migrate
from shared.exceptions import DownloadError
from shared.logger import get_logger

log = get_logger("enrich")
COMMONS_BATCH = 50


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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
    except ValueError:                                  # e.g. 31 in a 30-day month
        born = datetime.date(y, m, 28)
    eighteenth = born.replace(year=born.year + 18) if not (born.month == 2 and born.day == 29) \
        else datetime.date(born.year + 18, 3, 1)
    return on < eighteenth


def thumb_name(image_file: str, ext: str) -> str:
    return "%s.%s" % (hashlib.sha1(image_file.encode("utf-8")).hexdigest()[:16], ext)


def _player_ids(serving_db: str) -> Optional[set]:
    """Register identifiers that appear in matches (from the last build), so umpires and people
    who never played aren't looked up. None when there is no serving DB yet: look up everyone."""
    if not os.path.exists(serving_db):
        return None
    conn = sqlite3.connect("file:%s?mode=ro" % serving_db, uri=True)
    try:
        return {r[0] for r in conn.execute("SELECT player_id FROM players")}
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _cricinfo_ids(store: RawStore, players: Optional[set]) -> List[str]:
    ids = set()
    for identifier, _name, _unique, keys_json in store.register_people():
        if players is not None and identifier not in players:
            continue
        for cid in (json.loads(keys_json or "{}").get("cricinfo") or []):
            if cid.isdigit():
                ids.add(cid)
    return sorted(ids, key=int)


def _stale(fetched_at: Optional[str], days: int, now: datetime.datetime) -> bool:
    if not fetched_at:
        return True
    then = datetime.datetime.strptime(fetched_at, "%Y-%m-%dT%H:%M:%SZ")
    return (now - then).days >= days


def run(cfg, client: Optional[wikimedia.Client] = None,
        today: Optional[datetime.date] = None) -> dict:
    t0 = time.time()
    client = client or wikimedia.Client(cfg.WIKIMEDIA_USER_AGENT, timeout=cfg.HTTP_TIMEOUT,
                                        retries=cfg.HTTP_RETRIES, backoff=cfg.HTTP_BACKOFF,
                                        pause=cfg.ENRICH_PAUSE)
    now = datetime.datetime.utcnow()
    today = today or now.date()
    started = utcnow()
    counts: Dict[str, int] = dict(ids=0, due=0, looked_up=0, on_wikidata=0, photos_due=0,
                                  photos_ok=0, photos_rejected=0, photos_failed=0,
                                  photos_skipped_minor=0)
    conn = connect(cfg.RAW_DB)
    try:
        migrate(conn, started)
        store = RawStore(conn)
        run_id = store.start_run("enrich", "wikidata + commons", started)
        summary = {"mode": "enrich", "run_id": run_id, "started_at": started}
        try:
            ids = _cricinfo_ids(store, _player_ids(cfg.SERVING_DB))
            known = store.wikidata_people()
            due = [c for c in ids if c not in known
                   or _stale(known[c]["fetched_at"], cfg.ENRICH_REFRESH_DAYS, now)]
            counts.update(ids=len(ids), due=len(due))
            for i in range(0, len(due), cfg.ENRICH_BATCH):
                batch = due[i:i + cfg.ENRICH_BATCH]
                found = wikimedia.fetch_people(client, batch)
                store.begin()
                store.upsert_wikidata([dict(found.get(c, {}), cricinfo_id=c) for c in batch],
                                      utcnow())
                store.commit()
                counts["looked_up"] += len(batch)
                counts["on_wikidata"] += len(found)
                log.info("wikidata: %d/%d ids looked up (%d on Wikidata so far)",
                         counts["looked_up"], len(due), counts["on_wikidata"])
            _photos(cfg, client, store, set(ids), today, now, counts)
            store.begin()
            store.finish_run(run_id, {"status": "success", "finished_at": utcnow(),
                                      "added": counts["on_wikidata"],
                                      "notes": json.dumps(counts)})
            store.commit()
        except BaseException as exc:
            if conn.in_transaction:
                store.rollback()
            store.begin()
            store.finish_run(run_id, {"status": "error", "finished_at": utcnow(),
                                      "notes": json.dumps(dict(counts, error=str(exc)))})
            store.commit()
            summary.update(counts, status="error", error=str(exc),
                           duration_s=round(time.time() - t0, 1))
            exc.summary = summary
            raise
    finally:
        conn.close()
    summary.update(counts, status="success", requests=client.requests,
                   duration_s=round(time.time() - t0, 1))
    log.info("enrich run %d: %d ids, %d looked up, %d on Wikidata; photos %d ok, %d rejected,"
             " %d failed, %d skipped (minor)", run_id, counts["ids"], counts["looked_up"],
             counts["on_wikidata"], counts["photos_ok"], counts["photos_rejected"],
             counts["photos_failed"], counts["photos_skipped_minor"])
    return summary


def _photos(cfg, client, store: RawStore, ids: set, today, now, counts: Dict[str, int]):
    people = [p for c, p in store.wikidata_people().items() if c in ids and p["image_file"]]
    images = store.commons_images()
    wanted, minors = set(), set()
    for p in people:
        if is_minor(p["date_of_birth"], today):
            minors.add(p["image_file"])
        else:
            wanted.add(p["image_file"])
    counts["photos_skipped_minor"] = len(minors - wanted)

    def due(name: str) -> bool:
        img = images.get(name)
        if img is None or img["status"] == "error" \
                or _stale(img["fetched_at"], cfg.ENRICH_REFRESH_DAYS, now):
            return True                         # failures retry on the next run
        return img["status"] == "ok" and not os.path.exists(
            os.path.join(cfg.PHOTO_DIR, img["thumb_path"] or ""))
    todo = sorted(n for n in wanted if due(n))[:cfg.ENRICH_MAX_PHOTOS]
    counts["photos_due"] = len(todo)
    os.makedirs(cfg.PHOTO_DIR, exist_ok=True)
    for i in range(0, len(todo), COMMONS_BATCH):
        batch = todo[i:i + COMMONS_BATCH]
        info = wikimedia.fetch_imageinfo(client, batch)
        for name in batch:
            rec = dict(info.get(name) or {"status": "error", "note": "not returned by Commons"})
            if rec["status"] == "ok":
                try:
                    body, ext = wikimedia.fetch_thumbnail(client, rec["thumb_url"])
                    rec["thumb_path"] = thumb_name(name, ext)
                    path = os.path.join(cfg.PHOTO_DIR, rec["thumb_path"])
                    with open(path + ".part", "wb") as f:
                        f.write(body)
                    os.replace(path + ".part", path)
                except DownloadError as exc:
                    rec.update(status="error", note=str(exc)[:200])
            key = {"ok": "photos_ok", "rejected": "photos_rejected"}.get(rec["status"],
                                                                         "photos_failed")
            counts[key] += 1
            store.begin()
            store.upsert_image(name, rec, utcnow())
            store.commit()
        log.info("commons: %d/%d photos checked (%d ok)", min(i + COMMONS_BATCH, len(todo)),
                 len(todo), counts["photos_ok"])
