"""Golden-figure review logic (pure): merge our figures (cricstat-api /v1/admin/golden) with the
owner's references and the Wikipedia suggestions, compute each row's status, export the CSV.

Status rules are the same as cricstat-pipeline's `golden` command and cricstat-api (F4 §3):
'' no reference · match · explained · stale (Mat changed since the check: re-check, not a failure)
· DIFF (unexplained difference: a failure).
"""
import csv
import io
from typing import Dict, Iterable, List, Optional, Tuple

CSV_COLUMNS = ["kind", "name", "id", "gender", "scope", "window", "metric", "ours", "reference",
               "status", "source", "checked_on", "explanation", "ours_at_check", "mat_at_check",
               "coverage_note", "why"]
Key = Tuple[str, str, str]                      # (entity id, scope, metric)


def norm(text: Optional[str]) -> str:
    text = (text or "").strip().replace(",", "")
    if text in ("–", "—"):
        return "-"
    try:
        return "%.2f" % float(text)
    except ValueError:
        return text.replace(" ", "")


def status(ours: str, reference: str, explanation: str, mat_now: str = "",
           mat_at_check: str = "") -> str:
    if not (reference or "").strip():
        return ""
    if mat_at_check and mat_now != mat_at_check:
        return "stale"
    if norm(ours) == norm(reference):
        return "match"
    return "explained" if (explanation or "").strip() else "DIFF"


COVERAGE_EXPLANATION = ("Career predates dense Cricsheet coverage for this format: our data has %s"
                        " of %s matches.")


def wiki_note(block: dict, wiki_mat: str, as_of: str, data_as_of: str) -> str:
    """Why Wikipedia's figures for this block differ from ours, when the match counts tell us.
    Labels only; nothing becomes a reference without the owner's action."""
    ours = block.get("mat") or ""
    if not (wiki_mat.isdigit() and ours.isdigit()):
        return ""
    n = int(wiki_mat) - int(ours)
    when = "Wikipedia as of %s, our data as of %s" % (as_of or "?", data_as_of or "?")
    if n < 0:
        older = as_of and data_as_of and as_of < data_as_of
        return ("Wikipedia shows %d fewer match(es): its figures are older than ours (%s)."
                % (-n, when)) if older else "Wikipedia shows %d fewer match(es) (%s)." % (-n, when)
    if n > 0:
        if block.get("coverage_note"):
            return ("Coverage gap: Wikipedia has %d more match(es); this career starts before our"
                    " data is dense." % n)
        if as_of and data_as_of and as_of > data_as_of:
            return ("Wikipedia is newer and has %d more match(es) (%s): some may be after our"
                    " data date; any others are withheld Afghanistan matches or Cricsheet gaps."
                    % (n, when))
        return ("%d match(es) missing from our data: Cricsheet withholds Afghanistan men's"
                " matches; otherwise a Cricsheet gap (%s)." % (n, when))
    return ""


def merge(blocks: List[dict], refs: Dict[Key, dict], sugg: Dict[Key, dict],
          data_as_of: str = "") -> List[dict]:
    """Attach reference, suggestion and status to every row of every block (in place), and a
    block-level note explaining a match-count difference with Wikipedia."""
    for b in blocks:
        for row in b["rows"]:
            key = (b["id"], b["scope"], row["metric"])
            ref, sg = refs.get(key, {}), sugg.get(key, {})
            row.update(reference=ref.get("reference") or "", source=ref.get("source") or "",
                       checked_on=ref.get("checked_on") or "",
                       explanation=ref.get("explanation") or "",
                       ours_at_check=ref.get("ours_at_check") or "",
                       mat_at_check=ref.get("mat_at_check") or "",
                       suggestion=sg.get("value") or "", suggestion_as_of=sg.get("as_of") or "",
                       suggestion_url=sg.get("source_url") or "")
            row["suggestion_agrees"] = bool(row["suggestion"]) and norm(row["suggestion"]) == \
                norm(row["ours"])
            row["status"] = status(row["ours"], row["reference"], row["explanation"], b["mat"],
                                   row["mat_at_check"])
        b["statuses"] = [r["status"] for r in b["rows"]]
        mat_sugg = sugg.get((b["id"], b["scope"], "Mat"), {})
        differs = any(r["suggestion"] and not r["suggestion_agrees"] for r in b["rows"])
        b["wiki_mat"] = mat_sugg.get("value") or ""
        b["wiki_note"] = wiki_note(b, b["wiki_mat"], mat_sugg.get("as_of") or "", data_as_of) \
            if differs else ""
        if differs and not b["wiki_note"] and b["wiki_mat"] == b.get("mat"):
            b["wiki_note"] = ("Same number of matches but a figure differs: possibly a scoring"
                              " difference in one match. Worth a look.")
    return blocks


def coverage_explanations(blocks: List[dict]) -> List[tuple]:
    """(block, row, explanation) for rows to bulk-explain: the block has a coverage note,
    Wikipedia counts more matches, the row has a differing suggestion and no reference yet."""
    out = []
    for b in blocks:
        wm, om = b.get("wiki_mat") or "", b.get("mat") or ""
        if not (b.get("coverage_note") and wm.isdigit() and om.isdigit() and int(wm) > int(om)):
            continue
        for r in b["rows"]:
            if r["suggestion"] and not r["suggestion_agrees"] and not r["reference"]:
                out.append((b, r, COVERAGE_EXPLANATION % (om, wm)))
    return out


def summary(blocks: Iterable[dict]) -> Dict[str, int]:
    out = {"rows": 0, "with_reference": 0, "match": 0, "explained": 0, "stale": 0, "DIFF": 0,
           "suggested": 0, "suggestion_agrees": 0}
    for b in blocks:
        for r in b["rows"]:
            out["rows"] += 1
            if r["status"]:
                out["with_reference"] += 1
                out[r["status"]] += 1
            if r["suggestion"]:
                out["suggested"] += 1
                out["suggestion_agrees"] += r["suggestion_agrees"]
    return out


def suggestion_rows(results: Dict[str, dict], blocks: List[dict]) -> List[dict]:
    """Flatten fetched infoboxes into one suggestion per golden row that Wikipedia covers."""
    out = []
    for b in blocks:
        res = results.get(b["id"])
        if b["kind"] != "player" or not res or "scopes" not in res:
            continue
        figures = res["scopes"].get(b["scope"], {})
        for row in b["rows"]:
            if row["metric"] in figures:
                out.append({"entity_id": b["id"], "scope": b["scope"], "metric": row["metric"],
                            "value": figures[row["metric"]], "source_url": res.get("url"),
                            "as_of": res.get("as_of")})
    return out


def to_csv(blocks: List[dict]) -> str:
    """Same columns as cricstat/docs/validation/golden-figures.csv (commit it to keep a record)."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, CSV_COLUMNS, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for b in blocks:
        for r in b["rows"]:
            w.writerow(dict(r, kind=b["kind"], name=b["name"], id=b["id"],
                            gender=b.get("gender", ""), scope=b["scope"], window=b["window"],
                            coverage_note=b.get("coverage_note", ""), why=b.get("why", "")))
    return buf.getvalue()
