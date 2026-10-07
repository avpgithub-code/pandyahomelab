"""player_bio rules (P0.5): which cricinfo id wins, minors, blocklist, missing thumbnails."""
import datetime

from db_logic.repository import bio_store

TODAY = datetime.date(2026, 10, 7)
WIKI = {"11": {"qid": "Q1", "label_en": "Alpha", "date_of_birth": "1990", "birthplace": "X",
               "country_for_sport": "India", "image_file": "a.jpg", "fetched_at": "t"},
        "5": {"qid": "Q5", "label_en": "Five", "date_of_birth": None, "birthplace": None,
              "country_for_sport": None, "image_file": None, "fetched_at": "t"}}
IMAGES = {"a.jpg": {"thumb_path": "a1.jpg", "width": 320, "height": 400, "licence": "CC0",
                    "licence_url": None, "author": "Jane", "description_url": "u"}}
PEOPLE = [("p1", "A", "A", {"cricinfo": ["11"]}), ("p2", "B", "B", {"cricinfo": ["11", "5"]}),
          ("p3", "C", "C", {"cricinfo": ["999"]}), ("p4", "D", "D", {})]


def test_rows_and_lowest_id_wins():
    rows, n = bio_store.bio_rows(PEOPLE, WIKI, IMAGES, None, (set(), set()), TODAY)
    by = {r[0]: r for r in rows}
    assert set(by) == {"p1", "p2"} and by["p2"][1] == "Q5"     # "5" < "11" numerically
    assert by["p1"][6] == "Alpha" and by["p1"][7] == "a1.jpg"
    assert n == dict(bio=2, full_names=2, photos=1, minors=0, blocked=0, photo_missing=0)


def test_blocklist_and_missing_file(tmp_path):
    rows, n = bio_store.bio_rows(PEOPLE[:1], WIKI, IMAGES, None, ({"Q1"}, set()), TODAY)
    assert rows[0][7] is None and n["blocked"] == 1
    rows, n = bio_store.bio_rows(PEOPLE[:1], WIKI, IMAGES, None, (set(), {"a.jpg"}), TODAY)
    assert rows[0][7] is None and n["blocked"] == 1
    rows, n = bio_store.bio_rows(PEOPLE[:1], WIKI, IMAGES, str(tmp_path), (set(), set()), TODAY)
    assert rows[0][7] is None and n["photo_missing"] == 1
    (tmp_path / "a1.jpg").write_bytes(b"x")
    rows, _ = bio_store.bio_rows(PEOPLE[:1], WIKI, IMAGES, str(tmp_path), (set(), set()), TODAY)
    assert rows[0][7] == "a1.jpg"


def test_read_blocklist(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text("qid,image_file,reason,added\nQ7,,request,2026-10-07\n,x.jpg,request,2026-10-07\n")
    assert bio_store.read_blocklist(str(p)) == ({"Q7"}, {"x.jpg"})
    assert bio_store.read_blocklist(str(tmp_path / "none.csv")) == (set(), set())
