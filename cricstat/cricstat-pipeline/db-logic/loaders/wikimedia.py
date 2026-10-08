"""Wikidata (SPARQL) and Wikimedia Commons (API, thumbnails) for player enrichment (P0.5).

Polite by design: a descriptive User-Agent with contact details, one request at a time with a
pause between them, retries with backoff on 429/5xx. People are matched only by ESPNcricinfo id
(Wikidata P2697). Only freely licensed images are accepted, and only a 330 px thumbnail is kept.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, Iterable, List, Optional

from shared.exceptions import DownloadError
from shared.logger import get_logger

log = get_logger("wikimedia")
SPARQL_URL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_WIDTH = 320              # Commons rounds up to its standard sizes (330 px today)
THUMB_HOSTS = {"upload.wikimedia.org", "thumb.wikimedia.org"}
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
# Public domain (incl. the owner's Public Domain Mark), CC0, CC BY and CC BY-SA (any version/port),
# and GODL-India (Government Open Data License – India: attribution, no implied endorsement; most
# Press Information Bureau photos of Indian players). Anything else is rejected.
# "CC BY-SA 3.0 de" and "CC BY 2.0" pass; "CC BY-NC…", "CC BY-ND…" and GFDL-only do not.
ALLOWED_LICENCE = re.compile(r"^(public domain.*|pd\b.*|pdm\b.*|cc0\b.*|godl-india"
                             r"|cc[ -]by(-sa)?(\s+\d(\.\d)?(\s+[a-z]{2,3})?)?)$", re.I)
GODL_URL = "https://data.gov.in/government-open-data-license-india"
_QID = re.compile(r"/entity/(Q\d+)$")
_CID = re.compile(r"^\d{1,9}$")


class Client:
    def __init__(self, user_agent: str, timeout: float = 60, retries: int = 4, backoff: float = 5,
                 pause: float = 1.0, opener: Callable = urllib.request.urlopen,
                 sleep: Callable[[float], None] = time.sleep):
        self.ua, self.timeout, self.retries, self.backoff = user_agent, timeout, retries, backoff
        self.pause, self.opener, self.sleep = pause, opener, sleep
        self.requests = 0

    def fetch(self, url: str, data: Optional[bytes] = None, accept: str = "application/json"):
        """GET (or POST when data is given) → (body bytes, content type). Retries 408/429/5xx
        and network errors; other 4xx fail at once."""
        last = None
        for attempt in range(self.retries + 1):
            if self.requests:
                self.sleep(self.pause)
            self.requests += 1
            req = urllib.request.Request(url, data=data, headers={
                "User-Agent": self.ua, "Accept": accept,
                **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})})
            try:
                with self.opener(req, timeout=self.timeout) as resp:
                    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
                    return resp.read(), ctype
            except urllib.error.HTTPError as exc:
                last = exc
                if 400 <= exc.code < 500 and exc.code not in (408, 429):
                    raise DownloadError("%s: HTTP %d" % (url.split("?")[0], exc.code)) from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                wait = float(retry_after) if retry_after and retry_after.isdigit() else None
            except (urllib.error.URLError, OSError) as exc:
                last, wait = exc, None
            if attempt < self.retries:
                wait = wait if wait is not None else self.backoff * (2 ** attempt)
                log.warning("%s failed (%s); retry %d/%d in %.0fs", url.split("?")[0], last,
                            attempt + 1, self.retries, wait)
                self.sleep(wait)
        raise DownloadError("%s: failed after %d attempts: %s"
                            % (url.split("?")[0], self.retries + 1, last))

    def json(self, url: str, data: Optional[bytes] = None, accept: str = "application/json"):
        body, _ = self.fetch(url, data, accept)
        try:
            return json.loads(body.decode("utf-8"))
        except ValueError as exc:
            raise DownloadError("%s: not JSON" % url.split("?")[0]) from exc


# ── Wikidata ─────────────────────────────────────────────────────────────────────────────
def sparql_people(cricinfo_ids: Iterable[str]) -> str:
    ids = [c for c in cricinfo_ids if _CID.match(c)]           # digits only: safe to inline
    return """SELECT ?cid ?item ?label ?dob ?prec ?bpLabel ?cfsLabel ?img WHERE {
  VALUES ?cid { %s }
  ?item wdt:P2697 ?cid .
  OPTIONAL { ?item rdfs:label ?label FILTER(LANG(?label) = "en") }
  OPTIONAL { ?item p:P569/psv:P569 [ wikibase:timeValue ?dob; wikibase:timePrecision ?prec ] }
  OPTIONAL { ?item wdt:P19 ?bp . ?bp rdfs:label ?bpLabel FILTER(LANG(?bpLabel) = "en") }
  OPTIONAL { ?item wdt:P1532 ?cfs . ?cfs rdfs:label ?cfsLabel FILTER(LANG(?cfsLabel) = "en") }
  OPTIONAL { ?item wdt:P18 ?img }
}""" % " ".join('"%s"' % c for c in ids)


def wikidata_date(value: Optional[str], precision: Optional[str]) -> Optional[str]:
    """'+1988-11-05T00:00:00Z' at precision 11/10/9 → '1988-11-05' / '1988-11' / '1988'.
    Coarser than a year, or BCE, → None."""
    m = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})T", value or "")
    if not m:
        return None
    p = int(precision) if precision and str(precision).isdigit() else 11
    if p >= 11:
        return "-".join(m.groups())
    if p == 10:
        return "%s-%s" % m.group(1, 2)
    return m.group(1) if p == 9 else None


def commons_file(url: Optional[str]) -> Optional[str]:
    """P18 value (http://commons.wikimedia.org/wiki/Special:FilePath/Virat%20Kohli.jpg) → name."""
    if not url or "Special:FilePath/" not in url:
        return None
    return urllib.parse.unquote(url.split("Special:FilePath/", 1)[1]).replace("_", " ") or None


def parse_people(bindings: List[dict]) -> Dict[str, dict]:
    """SPARQL rows (one per combination of optional values) → one record per cricinfo id. When an
    id has several items or values, the lowest QID and the smallest value win (deterministic)."""
    rows: Dict[str, Dict[str, set]] = {}
    for b in bindings:
        v = {k: x.get("value") for k, x in b.items()}
        cid, item = v.get("cid"), _QID.search(v.get("item") or "")
        if not cid or not item:
            continue
        r = rows.setdefault(cid, {k: set() for k in ("qid", "label", "dob", "bp", "cfs", "img")})
        r["qid"].add(item.group(1))
        for key, src in (("label", "label"), ("bp", "bpLabel"), ("cfs", "cfsLabel")):
            if v.get(src):
                r[key].add(v[src].strip())
        if v.get("dob"):
            d = wikidata_date(v["dob"], v.get("prec"))
            if d:
                r["dob"].add(d)
        f = commons_file(v.get("img"))
        if f:
            r["img"].add(f)

    def first(values):
        return min(values) if values else None
    return {cid: {"qid": min(r["qid"], key=lambda q: int(q[1:])), "label_en": first(r["label"]),
                  "date_of_birth": first(r["dob"]), "birthplace": first(r["bp"]),
                  "country_for_sport": first(r["cfs"]), "image_file": first(r["img"])}
            for cid, r in rows.items()}


def fetch_people(client: Client, cricinfo_ids: List[str]) -> Dict[str, dict]:
    data = urllib.parse.urlencode({"query": sparql_people(cricinfo_ids), "format": "json"})
    doc = client.json(SPARQL_URL, data.encode(), "application/sparql-results+json")
    return parse_people(doc.get("results", {}).get("bindings", []))


# ── Commons ──────────────────────────────────────────────────────────────────────────────
def plain(text: Optional[str], limit: int = 200) -> Optional[str]:
    """Commons metadata is HTML: keep the text only."""
    if not text:
        return None
    t = html.unescape(re.sub(r"<[^>]+>", " ", text))
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:limit - 1] + "…" if len(t) > limit else t) or None


def licence_allowed(short_name: Optional[str]) -> bool:
    return bool(short_name and ALLOWED_LICENCE.match(short_name.strip()))


def parse_imageinfo(doc: dict) -> Dict[str, dict]:
    """action=query&prop=imageinfo response → {file name: info}. Files Commons doesn't have come
    back with status 'error'; a licence outside the allowed set with status 'rejected'."""
    pages = (doc.get("query") or {}).get("pages") or {}
    norm = {n["to"]: n["from"] for n in (doc.get("query") or {}).get("normalized", [])}
    out = {}
    for page in (pages.values() if isinstance(pages, dict) else pages):
        title = page.get("title", "")
        name = norm.get(title, title)
        name = name[5:] if name.startswith("File:") else name
        info = (page.get("imageinfo") or [None])[0]
        if not info:
            out[name] = {"status": "error", "note": "not on Commons"}
            continue
        meta = {k: (v or {}).get("value") for k, v in (info.get("extmetadata") or {}).items()}
        licence = plain(meta.get("LicenseShortName"), 80)
        licence_url = meta.get("LicenseUrl")
        if not licence_url and (licence or "").lower() == "godl-india":
            licence_url = GODL_URL
        rec = {"licence": licence, "licence_url": licence_url,
               "author": plain(meta.get("Artist")) or plain(meta.get("Credit")),
               "description_url": info.get("descriptionurl"), "thumb_url": info.get("thumburl"),
               "width": info.get("thumbwidth"), "height": info.get("thumbheight")}
        if not licence_allowed(licence):
            rec.update(status="rejected", note="licence not allowed: %s" % (licence or "none"))
        elif not rec["thumb_url"]:
            rec.update(status="error", note="no thumbnail")
        else:
            rec.update(status="ok", note=None)
        out[name] = rec
    return out


def fetch_imageinfo(client: Client, files: List[str]) -> Dict[str, dict]:
    """Up to 50 files per call (the API's limit)."""
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size", "iiurlwidth": THUMB_WIDTH,
        "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|Credit",
        "titles": "|".join("File:" + f for f in files)})
    return parse_imageinfo(client.json(COMMONS_API + "?" + q))


def fetch_thumbnail(client: Client, url: str) -> (bytes, str):
    """→ (bytes, extension). Only JPEG/PNG/WebP, checked by both Content-Type and magic bytes."""
    parts = urllib.parse.urlparse(url)
    if parts.scheme != "https" or parts.hostname not in THUMB_HOSTS:
        raise DownloadError("unexpected thumbnail host: %s" % parts.hostname)
    body, ctype = client.fetch(url, accept="image/*")
    ext = IMAGE_TYPES.get(ctype)
    magic = {"jpg": body[:3] == b"\xff\xd8\xff", "png": body[:8] == b"\x89PNG\r\n\x1a\n",
             "webp": body[:4] == b"RIFF" and body[8:12] == b"WEBP"}
    if not ext or not magic[ext]:
        raise DownloadError("not a JPEG/PNG/WebP image (%s)" % (ctype or "no type"))
    return body, ext
