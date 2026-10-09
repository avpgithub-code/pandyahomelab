"""Fetch one photo per 2027 World Cup venue from Wikimedia Commons, self-hosted with its credit.

    python3 cricstat/tools/fetch_venue_photos.py [--live]

Source of each file: venues.csv commons_file, chosen and looked at by a person (the venue table of
Wikipedia's "2027 Cricket World Cup" article, or the ground's own Commons photos). Same
rules as the player photos (P0.5): only public domain, CC0, CC BY and CC BY-SA are kept; only a
640 px thumbnail is downloaded; the host must be Wikimedia's and the bytes must really be a
JPEG/PNG/WebP. Licence, author and file page are written back into venues.csv (reviewed in git)
so the page and the licences page credit each photo. A venue without an allowed photo keeps none.
Writes into cricstat/tools/staging/web/venues/ (or cricstat/web/venues/ with --live).
"""
import csv
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

CRICSTAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENUES = os.path.join(CRICSTAT, "cricstat-models", "tournaments", "wc2027", "venues.csv")
WEB = os.path.join(CRICSTAT, "web") if "--live" in sys.argv else os.path.join(CRICSTAT, "tools", "staging", "web")
OUT = os.path.join(WEB, "venues")
UA = "cricstat/0.1 (https://pandyahomelab.com/cricket/; privacy@pandyahomelab.com) python-urllib"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_HOSTS = {"upload.wikimedia.org", "thumb.wikimedia.org"}
ALLOWED = re.compile(r"^(public domain.*|pd\b.*|pdm\b.*|cc0\b.*|cc[ -]by(-sa)?(\s+\d(\.\d)?(\s+[a-z]{2,3})?)?)$", re.I)
TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
PHOTO_COLS = ["photo", "photo_file", "photo_author", "photo_licence", "photo_licence_url", "photo_source"]


def get(url, accept="application/json"):
    time.sleep(1.0)                                  # one request a second (Wikimedia etiquette)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get_content_type()


def api(base, **q):
    q.update(format="json", formatversion="2")
    return json.loads(get(base + "?" + urllib.parse.urlencode(q))[0])


def plain(text, limit=200):
    if not text:
        return None
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()
    return t[:limit - 1] + "…" if len(t) > limit else t


def imageinfo(name):
    d = api(COMMONS_API, action="query", titles="File:" + name, prop="imageinfo",
            iiprop="url|extmetadata|mime", iiurlwidth=640,
            iiextmetadatafilter="LicenseShortName|LicenseUrl|Artist|Credit")
    page = d["query"]["pages"][0]
    info = (page.get("imageinfo") or [None])[0]
    if not info:
        return None
    meta = {k: (v or {}).get("value") for k, v in (info.get("extmetadata") or {}).items()}
    return {"licence": plain(meta.get("LicenseShortName"), 80), "licence_url": meta.get("LicenseUrl"),
            "author": plain(meta.get("Artist")) or plain(meta.get("Credit")),
            "page": info.get("descriptionurl"), "thumb": info.get("thumburl")}


def author(text):
    """Readable credit from Commons' Artist field: 'The original uploader was X at English
    Wikipedia.' → 'X (English Wikipedia)'; 'w:de:User:X' → 'X'."""
    if not text:
        return ""
    m = re.match(r"^The original uploader was (.+?) at (.+?)\.?\s*$", text)
    if m:
        return "%s (%s)" % (m.group(1).strip(), m.group(2).strip())
    return re.sub(r"^(?:w:[a-z]{2}:)?User:", "", text).strip()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main():
    rows = list(csv.DictReader(open(VENUES, encoding="utf-8", newline="")))
    fields = list(rows[0].keys()) + [c for c in PHOTO_COLS if c not in rows[0]]
    os.makedirs(OUT, exist_ok=True)
    for r in rows:
        for c in PHOTO_COLS:
            r.setdefault(c, "")
        # Only the file a person chose and looked at (venues.csv commons_file). No automatic
        # fallback: an article that redirects elsewhere once supplied another ground's photo.
        name = r["commons_file"]
        if not name:
            # A photo added by hand from elsewhere (e.g. Flickr, licence checked) is kept as is.
            print("%-14s %s" % (r["city"], "kept: " + r["photo"] if r.get("photo") else "no reviewed photo"))
            continue
        info = imageinfo(name)
        if not info:
            print("%-14s %s: not on Commons" % (r["city"], name))
            continue
        if not (info["licence"] and ALLOWED.match(info["licence"].strip())):
            print("%-14s %s: licence %r not allowed — skipped" % (r["city"], name, info["licence"]))
            continue
        url = urllib.parse.urlparse(info["thumb"] or "")
        if url.scheme != "https" or url.hostname not in THUMB_HOSTS:
            print("%-14s unexpected thumbnail host %r — skipped" % (r["city"], url.hostname))
            continue
        body, ctype = get(info["thumb"], "image/*")
        ext = TYPES.get(ctype)
        magic = {"jpg": body[:3] == b"\xff\xd8\xff", "png": body[:8] == b"\x89PNG\r\n\x1a\n",
                 "webp": body[:4] == b"RIFF" and body[8:12] == b"WEBP"}
        if not ext or not magic[ext]:
            print("%-14s not a JPEG/PNG/WebP (%s) — skipped" % (r["city"], ctype))
            continue
        out = "%s.%s" % (slug(r["stadium"]), ext)
        with open(os.path.join(OUT, out), "wb") as f:
            f.write(body)
        r.update(photo=out, photo_file=name, photo_author=author(info["author"]),
                 photo_licence=info["licence"], photo_licence_url=info["licence_url"] or "",
                 photo_source=info["page"] or "")
        print("%-14s %s  %s  %s  (%d KB)" % (r["city"], out, info["licence"], (info["author"] or "")[:40], len(body) // 1024))
    with open(VENUES, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
