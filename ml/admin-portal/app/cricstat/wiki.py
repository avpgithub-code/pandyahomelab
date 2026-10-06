"""Reference suggestions for the cricstat golden set, from Wikipedia (P0.3b).

Never ESPNcricinfo (its terms forbid automated use; cricstat sources policy). Pages are found
through Wikidata by Cricinfo id (property P2697) — no guessing by name — then each player's
article lead section is fetched once from the MediaWiki API and the "Infobox cricketer" career
columns are read. Polite: descriptive User-Agent, one request per second, fixed selection only.
Wikipedia is volunteer-edited and can lag: these are SUGGESTIONS the owner accepts or explains.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, Iterable, List, Optional

USER_AGENT = ("pandyaHomeLab-cricstat/0.1 (https://pandyahomelab.com/cricket/; golden-figure "
              "validation, a few dozen requests a week)")
SPARQL = "https://query.wikidata.org/sparql"
MEDIAWIKI = "https://en.wikipedia.org/w/api.php"

# Infobox column label → cricstat scope
COLUMN_SCOPE = {"test": "TEST", "wtest": "TEST", "odi": "ODI", "wodi": "ODI", "t20i": "T20I",
                "wt20i": "T20I", "ipl": "ipl", "wpl": "wpl"}
_FIELD = re.compile(r"^\|\s*([a-z0-9/ ]+?)\s*=\s*(.*)$", re.IGNORECASE)
_REF = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>|<!--.*?-->", re.DOTALL)
_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_DASHES = {"–", "—", "-", ""}


def _clean(value: str) -> str:
    value = _LINK.sub(r"\1", _REF.sub("", value))
    value = re.sub(r"\{\{[^}]*\}\}", "", value).replace("&nbsp;", " ").strip()
    return "-" if value in _DASHES else value.replace(",", "")


def _as_of(text: str, today: Optional[datetime] = None) -> Optional[str]:
    """The infobox 'date' as ISO. A day and month without a year (an editing slip seen in the
    wild, e.g. "22 September") is taken as the most recent such date."""
    text = _clean(text).replace(",", "")
    for fmt in ("%d %B %Y", "%B %d %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    today = today or datetime.utcnow()
    for fmt in ("%d %B", "%B %d"):
        try:
            d = datetime.strptime(text, fmt).replace(year=today.year)
        except ValueError:
            continue
        return (d if d <= today else d.replace(year=today.year - 1)).strftime("%Y-%m-%d")
    return None


def _dash(value: str) -> str:
    return "-" if value.strip() in _DASHES else value.strip()


def parse_infobox(wikitext: str) -> Dict[str, object]:
    """{'as_of': 'YYYY-MM-DD'|None, 'scopes': {scope: {metric: value}}} from Infobox cricketer.

    Metric names match the golden table: Mat, Runs, Ave, 100, HS, Wkts, Bowl Ave, 5w, BBI, Ct, St.
    """
    fields: Dict[str, str] = {}
    for line in wikitext.splitlines():
        m = _FIELD.match(line.strip())
        if m:
            fields[m.group(1).lower().strip()] = m.group(2)
    scopes: Dict[str, Dict[str, str]] = {}
    for n in range(1, 7):
        label = fields.get("column%d" % n)
        if not label:
            continue
        scope = COLUMN_SCOPE.get(_clean(label).lower().replace("'", ""))
        if not scope:
            continue

        def f(name, n=n):
            return _clean(fields.get("%s%d" % (name, n), ""))

        figures = {"Mat": f("matches"), "Runs": f("runs"), "Ave": f("bat avg"),
                   "HS": f("top score"), "Wkts": f("wickets"), "Bowl Ave": f("bowl avg"),
                   "5w": f("fivefor"), "BBI": f("best bowling")}
        hundreds = f("100s/50s").split("/")
        figures["100"] = _dash(hundreds[0])
        ct_st = f("catches/stumpings").split("/")
        figures["Ct"] = _dash(ct_st[0])
        figures["St"] = _dash(ct_st[1]) if len(ct_st) > 1 else "-"
        scopes[scope] = {k: v for k, v in figures.items() if v}
    return {"as_of": _as_of(fields.get("date", "")), "scopes": scopes}


def _get(url: str, timeout: float = 20) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def articles_for_cricinfo_ids(cricinfo_ids: Iterable[str]) -> Dict[str, str]:
    """{cricinfo_id: English Wikipedia title} via one Wikidata SPARQL query."""
    ids = sorted({i for i in cricinfo_ids if i and i.isdigit()})
    if not ids:
        return {}
    query = ("SELECT ?cid ?article WHERE { VALUES ?cid { %s } ?item wdt:P2697 ?cid ."
             " ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }"
             % " ".join('"%s"' % i for i in ids))
    data = _get("%s?%s" % (SPARQL, urllib.parse.urlencode({"query": query, "format": "json"})),
                timeout=60)
    out = {}
    for b in data["results"]["bindings"]:
        title = urllib.parse.unquote(b["article"]["value"].rsplit("/wiki/", 1)[-1])
        out[b["cid"]["value"]] = title.replace("_", " ")
    return out


def lead_wikitext(title: str) -> str:
    params = {"action": "parse", "page": title, "prop": "wikitext", "section": 0,
              "format": "json", "formatversion": 2, "redirects": 1}
    return _get("%s?%s" % (MEDIAWIKI, urllib.parse.urlencode(params)))["parse"]["wikitext"]


def fetch_suggestions(players: List[dict], pause: float = 1.0, log=None) -> Dict[str, dict]:
    """players: [{'id', 'name', 'cricinfo_ids': [...]}] → {player_id: {'title', 'url', 'as_of',
    'scopes'} or {'error'}}. One SPARQL query, then one page per player, `pause` s apart."""
    titles = articles_for_cricinfo_ids(i for p in players for i in p.get("cricinfo_ids", []))
    out: Dict[str, dict] = {}
    for p in players:
        title = next((titles[i] for i in p.get("cricinfo_ids", []) if i in titles), None)
        if not title:
            out[p["id"]] = {"error": "no English Wikipedia article linked to its Cricinfo id"}
            continue
        try:
            parsed = parse_infobox(lead_wikitext(title))
            out[p["id"]] = dict(parsed, title=title, url="https://en.wikipedia.org/wiki/%s"
                                % urllib.parse.quote(title.replace(" ", "_")))
        except Exception as exc:          # one bad page must not stop the run
            out[p["id"]] = {"error": "%s: %s" % (type(exc).__name__, exc), "title": title}
            if log:
                log.warning("wikipedia %s: %s", title, exc)
        time.sleep(pause)
    return out
