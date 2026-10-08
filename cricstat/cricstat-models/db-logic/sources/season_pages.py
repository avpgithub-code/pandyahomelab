"""Parse Wikipedia's "International cricket in <season>" pages (and tournament articles that use the
same tables) into one row per men's ODI.

Each match row in those wikitables links the ESPNcricinfo scorecard (the same id space as
Cricsheet's match_id) and carries the official ODI number, e.g.
``[http://…/match/592270.html ODI 3341]``.
Three layouts occur:
  * ``No. | Date | Team 1 | Team 2 | Venue | Result``       (team templates {{cr|AFG}} in the cells)
  * ``No. | Date | Team 1 | Captain 1 | Team 2 | Captain 2 | Venue | Result``   (tournaments)
  * ``No. | Date | Home captain | Away captain | Venue | Result``
    or ``<Team> captain | <Team> captain``
    (bilateral series: the teams come from the column names or the section heading,
    e.g. "===Afghanistan in Ireland===" or "===Ireland vs Afghanistan in India===")

Pure functions only (no I/O). Team names are returned as they appear in the source (template code or
name); resolving them to cricstat team identities is the crosswalk's job (team_codes.csv).
"""
import re
from typing import Dict, List, Optional, Tuple

MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"), start=1)}

_ODI_LINK = re.compile(
    r"\[(?P<url>https?://[^\s\]]+)\s+(?P<label>(?:W?ODI|Match|T20I|WT20I|Test|WODI)[^\]]*)\]")
_ODI_NO = re.compile(r"^ODI\s*(?:no\.?\s*)?(\d+[a-z]?)$", re.I)
# Only scorecard links carry a match id; a series link (…/series/643659.html) does not.
_MATCH_ID = re.compile(r"(?:match/|/[a-z0-9-]+-)(\d{5,8})(?:\.html?|/|$)")
_SERIES_LINK = re.compile(r"/series/\d+\.html?$")
_CR = re.compile(r"\{\{\s*(?:cr|cr-rt|crw|cricon|flagicon)\s*\|\s*([^|}]+?)\s*(?:\|[^}]*)?\}\}"
                 r"|\{\{([A-Z]{2,4})\}\}", re.I)
_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")
_TEAM_LINK = re.compile(r"\[\[([^\]|]+?) (?:national )?cricket team(?:\|([^\]]+))?\]\]", re.I)
_HEADING = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$")
_MAIN = re.compile(r"\{\{\s*main\s*\|\s*([^|}]+)", re.I)
_TITLE_YEARS = re.compile(r"(\d{4})(?:[–-](\d{2,4}))?")


def season_years(title: str) -> Tuple[int, Optional[int]]:
    """'International cricket in 2015–16' → (2015, 2016); '… in 2016' → (2016, None)."""
    m = _TITLE_YEARS.search(title)
    if not m:
        raise ValueError("no year in %r" % title)
    first = int(m.group(1))
    if not m.group(2):
        return first, None
    return first, first + 1


def _date(cell: str, title: str, default_year: Optional[int] = None) -> Optional[str]:
    """'1 April', '6–8 June', '{{dts|19 April 2009}}', 'April 19' → ISO date (first day)."""
    text = re.sub(r"\{\{\s*dts\s*\|", "", cell, flags=re.I)
    text = re.sub(r"[{}\[\]]", " ", text)
    m = re.search(r"(\d{1,2})(?:\s*[–-]\s*\d{1,2})?\s+([A-Za-z]+)(?:\s+(\d{4}))?", text)
    if m and m.group(2).lower() in MONTHS:
        day, month, year = int(m.group(1)), MONTHS[m.group(2).lower()], m.group(3)
    else:
        m = re.search(r"([A-Za-z]+)\s+(\d{1,2})(?:,?\s+(\d{4}))?", text)
        if not m or m.group(1).lower() not in MONTHS:
            return None
        day, month, year = int(m.group(2)), MONTHS[m.group(1).lower()], m.group(3)
    if year:
        y = int(year)
    elif default_year:
        y = default_year
    else:
        first, second = season_years(title)
        # Two-year (southern/winter) seasons run from about July to the next June.
        y = first if (second is None or month >= 7) else second
    return "%04d-%02d-%02d" % (y, month, day)


_ATTRS = re.compile(r'^\s*((?:[a-z-]+\s*=\s*(?:"[^"]*"|[^\s|\[{]+)\s*)+)\|(?!\|)', re.I)


def _strip(cell: str) -> str:
    cell = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", cell, flags=re.S)
    m = _ATTRS.match(cell)
    if m:
        cell = cell[m.end():]
    return cell.strip()


def _span(cell: str) -> int:
    m = _ATTRS.match(cell)
    s = m and re.search(r"colspan\s*=\s*\"?(\d+)", m.group(1), re.I)
    return int(s.group(1)) if s else 1


def team_tokens(cell: str) -> List[str]:
    """Team references in a cell, in order: template codes first, else linked team names."""
    toks = [(m.group(1) or m.group(2)).strip() for m in _CR.finditer(cell)
            if not re.match(r"(?i)\s*flagicon", m.group(0)[2:])]
    if toks:
        return toks
    out = []
    for m in _TEAM_LINK.finditer(cell):
        out.append(m.group(1).strip())
    return out


def parse_result(cell: str) -> Dict[str, Optional[str]]:
    """Result cell → {result, winner, method, decided_by, has_play, margin}."""
    text = _strip(cell)
    plain = _LINK.sub(lambda m: m.group(1), text)
    low = plain.lower()
    method = "D/L" if re.search(r"\bD/?L\b|DLS|Duckworth|VJD", plain) else None
    out = {"result": None, "winner": None, "method": method, "decided_by": "play",
           "has_play": "1", "margin": None}
    if "abandoned" in low or "cancelled" in low or "no play" in low:
        out.update(result="no_result", has_play="0")
        return out
    if re.search(r"\bno result\b", low):
        out.update(result="no_result")
        return out
    if "tied" in low or re.search(r"\btie\b", low):
        out["result"] = "tie"
        so = re.search(r"super over|s/o\b", low)
        if so:
            toks = team_tokens(text)
            out.update(winner=toks[0] if toks else None, decided_by="super_over")
        return out
    if "awarded" in low or "forfeit" in low or "conceded" in low:
        toks = team_tokens(text)
        out.update(result="win", winner=toks[0] if toks else None, decided_by="award",
                   has_play="0")
        return out
    toks = team_tokens(text)
    m = re.search(r"by\s+(\d+\s+(?:runs?|wickets?))", plain)
    if toks and ("by " in plain or "won" in low):
        out.update(result="win", winner=toks[0], margin=m.group(1) if m else None)
    return out


def _split_cells(row: str) -> List[str]:
    """One wikitable row (between |- markers) → data cells. Header (!) lines are ignored."""
    cells: List[str] = []
    for line in row.split("\n"):
        line = line.rstrip()
        if not line.startswith("|") or line.startswith("|}") or line.startswith("|+"):
            continue
        for part in line[1:].split("||"):
            cells.append(_strip(part))
            cells.extend([""] * (_span(part) - 1))     # keep later columns aligned
    return cells


def _header_labels(lines: List[str]) -> List[str]:
    """'! No. !! Date !! Team 1' or one '! label' per line (attributes like 'scope=col |' dropped).
    A lone '! colspan=6 | ODI series' line is a caption, not a column, and is skipped."""
    labels: List[str] = []
    for line in lines:
        parts = line[1:].split("!!")
        if len(parts) == 1 and "colspan" in parts[0]:
            continue
        for part in parts:
            text = _LINK.sub(lambda m: m.group(1), part)
            if "|" in text:                       # attributes before the label
                text = text.rsplit("|", 1)[-1]
            labels.append(text.strip())
    return labels


def _teams_from_heading(heading: str) -> List[str]:
    """'Afghanistan in Ireland' → [Afghanistan, Ireland]; 'Ireland vs Afghanistan in India' →
    [Ireland, Afghanistan]; tournament headings give []."""
    h = _LINK.sub(lambda m: m.group(1), heading)
    h = re.sub(r"\{\{[^}]*\}\}", "", h).strip()
    h = re.sub(r"\s*\([^)]*\)", "", h).strip()          # "Pakistan (April 2023)"
    m = re.match(r"^(.+?)\s+(?:vs?\.?|against)\s+(.+?)(?:\s+in\s+.+)?$", h, re.I)
    if m:
        return [m.group(1).strip(), m.group(2).strip()]
    m = re.match(r"^(.+?)\s+in\s+(?:the\s+)?(.+?)$", h)
    if m:
        host = re.split(r"\s+and\s+(?:the\s+)?", m.group(2))[0]   # co-hosted: first host
        return [m.group(1).strip(), host.strip()]
    return []


def parse_page(title: str, wikitext: str) -> List[Dict[str, Optional[str]]]:
    """Every ODI-numbered match row on the page, with its context. Rows without an ODI number
    ('Match 6' in a qualifier, T20Is, Tests, women's ODIs) are skipped."""
    rows: List[Dict[str, Optional[str]]] = []
    headings: Dict[int, str] = {}
    articles: Dict[int, str] = {}           # {{main|…}} under each heading level
    header: List[str] = []
    caption = ""
    lines = wikitext.split("\n")
    i = 0
    block: List[str] = []

    def flush(block_lines):
        nonlocal header, caption
        text = "\n".join(block_lines)
        heads = [ln for ln in block_lines if ln.startswith("!")]
        if heads:
            labels = _header_labels(heads)
            if any(lbl.lower() in ("no.", "no", "date") for lbl in labels):
                header = labels
            elif len(heads) == 1 and "colspan" in heads[0]:
                caption = _LINK.sub(lambda m: m.group(1), heads[0].split("|")[-1]).strip()
        m = _ODI_LINK.search(text)
        if not m:
            return
        no = _ODI_NO.match(m.group("label").strip())
        if not no:
            return
        url = m.group("url")
        mid = None if _SERIES_LINK.search(url) else _MATCH_ID.search(url)
        cells = [c for c in _split_cells(text)]
        while cells and not cells[0]:
            cells.pop(0)
        rec = _row(title, cells, header, headings, caption)
        rec.update(odi_no=no.group(1), match_id=mid.group(1) if mid else None,
                   source_title=title,
                   article=articles[max(articles)] if articles else None)
        rows.append(rec)

    while i < len(lines):
        line = lines[i]
        hm = _HEADING.match(line)
        if hm:
            level = len(hm.group(1))
            headings = {k: v for k, v in headings.items() if k < level}
            articles = {k: v for k, v in articles.items() if k < level}
            headings[level] = hm.group(2)
            header, caption = [], ""
        mm = _MAIN.match(line.strip())
        if mm and headings:
            articles[max(headings)] = mm.group(1).strip()
        if line.startswith("{|"):
            header, caption, block = [], "", []
        elif line.startswith("|-") or line.startswith("|}"):
            if block:
                flush(block)
            block = []
        else:
            block.append(line)
        i += 1
    if block:
        flush(block)
    return rows


def _row(title, cells, header, headings, caption) -> Dict[str, Optional[str]]:
    lab = [h.lower() for h in header]
    # Map label positions onto cells. Headers include "No." which matches cells[0].
    def col(pred) -> Optional[int]:
        for k, h in enumerate(lab):
            if pred(h):
                return k
        return None

    i_date = col(lambda h: h == "date")
    i_venue = col(lambda h: h.startswith("venue"))
    i_result = col(lambda h: h.startswith("result"))
    team_cols = [k for k, h in enumerate(lab)
                 if re.match(r"team\s*\d|home team|away team", h) and "captain" not in h]
    # "<Team> captain" names the team; "Home/Away/Team 1 captain" doesn't.
    cap_cols = [k for k, h in enumerate(lab) if h.endswith("captain")
                and not re.match(r"(home|away|team\s*\d|captain)", h)]

    def cell(k):
        return cells[k] if k is not None and k < len(cells) else ""

    if i_date is None and len(cells) >= 2:
        i_date = 1
    if i_result is None:
        i_result = len(cells) - 1
    if i_venue is None and len(cells) >= 3:
        i_venue = i_result - 1

    teams: List[str] = []
    how = ""
    if team_cols and all(team_tokens(cell(k)) for k in team_cols):
        teams = [team_tokens(cell(k))[0] for k in team_cols]
        how = "team columns"
    elif len(cap_cols) == 2:
        teams = [header[k][: -len("captain")].strip() for k in cap_cols]
        how = "captain columns"
    else:
        for level in sorted(headings, reverse=True):
            teams = _teams_from_heading(headings[level])
            if len(teams) == 2:
                how = "heading"
                break
        if len(teams) != 2 and caption:
            teams = _teams_from_heading(caption)
            how = "caption" if len(teams) == 2 else ""
    venue = _LINK.sub(lambda m: m.group(1), cell(i_venue)).strip()
    res = parse_result(cell(i_result))
    section = " / ".join(headings[k] for k in sorted(headings))
    return {"date": _date(cell(i_date), title), "team1": teams[0] if len(teams) > 0 else None,
            "team2": teams[1] if len(teams) > 1 else None, "teams_from": how, "venue": venue,
            "result_text": _LINK.sub(lambda m: m.group(1), cell(i_result)).strip(),
            "section": section, **res}
