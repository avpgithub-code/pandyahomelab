"""Parse ``{{Single-innings cricket match …}}`` boxes from series and tournament articles.

This is the second, independently edited Wikipedia source for each supplement row: the season page's
results table is one edit trail, the series article's match box another. A row is "confirmed" when
both agree on the date, the two teams and the outcome.
"""
import re
from typing import Dict, List, Optional

from db_logic.sources.season_pages import MONTHS, team_tokens

# Template names used over the years for one limited-overs match.
_START = re.compile(r"\{\{\s*(?:Single-innings cricket match|Limited overs matches|"
                    r"Limited overs international|Cricket match summary)\s*\n", re.I)
_FIELD = re.compile(r"^\|\s*([a-z0-9_]+)\s*=\s*(.*)$", re.I)
_REPORT_ID = re.compile(r"(?:match/|/[a-z0-9-]+-)(\d{5,8})(?:\.html?|/|\s|\]|$)")
_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")
_SUB_ARTICLE = re.compile(r"\{\{\s*(?:main|further|see also)\s*\|\s*([^|}]+)", re.I)


def _template_body(text: str, start: int) -> str:
    """Text of the template starting at `start`, matching nested {{ }}."""
    depth, i = 0, start
    while i < len(text) - 1:
        two = text[i:i + 2]
        if two == "{{":
            depth += 1
            i += 2
            continue
        if two == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return text[start:i]
            continue
        i += 1
    return text[start:]


def _date(value: str) -> Optional[str]:
    """Full date → 'YYYY-MM-DD'; a date without a year ('1 April') → '--MM-DD'."""
    value = re.sub(r"\{\{\s*dts\s*\|", "", value, flags=re.I)
    m = re.search(r"(\d{1,2})(?:\s*[–-]\s*\d{1,2})?\s+([A-Za-z]+)\s+(\d{4})", value)
    if m and m.group(2).lower() in MONTHS:
        return "%s-%02d-%02d" % (m.group(3), MONTHS[m.group(2).lower()], int(m.group(1)))
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", value)
    if m and m.group(1).lower() in MONTHS:
        return "%s-%02d-%02d" % (m.group(3), MONTHS[m.group(1).lower()], int(m.group(2)))
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)", value)
    if m and m.group(2).lower() in MONTHS:
        return "--%02d-%02d" % (MONTHS[m.group(2).lower()], int(m.group(1)))
    return None


def same_date(box_date: Optional[str], iso: str) -> bool:
    """A yearless box date matches on month and day."""
    if not box_date:
        return False
    return box_date == iso or (box_date.startswith("--") and iso.endswith(box_date[1:]))


def parse_boxes(wikitext: str) -> List[Dict[str, Optional[str]]]:
    boxes = []
    for m in _START.finditer(wikitext):
        body = _template_body(wikitext, m.start())
        fields: Dict[str, str] = {}
        key = None
        for line in body.split("\n")[1:]:
            fm = _FIELD.match(line.strip())
            if fm:
                key = fm.group(1).lower()
                fields[key] = fm.group(2).strip()
            elif key and not line.strip().startswith("}}"):
                fields[key] += "\n" + line
        t1, t2 = team_tokens(fields.get("team1", "")), team_tokens(fields.get("team2", ""))
        rid = _REPORT_ID.search(fields.get("report", ""))
        boxes.append({
            "date": _date(fields.get("date", "")),
            "team1": t1[0] if t1 else None, "team2": t2[0] if t2 else None,
            "result_text": _LINK.sub(lambda x: x.group(1), fields.get("result", "")).strip(),
            "match_id": rid.group(1) if rid else None,
            "venue": _LINK.sub(lambda x: x.group(1), fields.get("venue", "")).strip(),
        })
    return boxes


def sub_articles(wikitext: str) -> List[str]:
    """Articles a tournament page delegates its matches to ({{main|2023 Cricket World Cup group
    stage}} …), in page order, without duplicates."""
    seen: List[str] = []
    for m in _SUB_ARTICLE.finditer(wikitext):
        t = m.group(1).strip()
        if t not in seen:
            seen.append(t)
    return seen


def box_outcome(result_text: str, names: Dict[str, str]) -> Dict[str, Optional[str]]:
    """'India won by 7 wickets' / 'Match abandoned' / 'Match tied' → {result, winner}.
    `names` maps every token and team name to a cricstat team name (team_codes.csv)."""
    low = result_text.lower()
    if "abandon" in low or "no result" in low or "cancel" in low:
        return {"result": "no_result", "winner": None}
    if "tied" in low:
        return {"result": "tie", "winner": None}
    toks = team_tokens(result_text)
    if toks and toks[0] in names:
        return {"result": "win", "winner": names[toks[0]]}
    m = re.match(r"\s*(.+?)\s+won\b", result_text)
    if m:
        cand = re.sub(r"\[\[|\]\]", "", m.group(1)).strip()
        return {"result": "win", "winner": names.get(cand, cand)}
    return {"result": None, "winner": None}
