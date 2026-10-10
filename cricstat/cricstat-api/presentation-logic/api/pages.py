"""Server-rendered heads: player and team pages, the WC 2027 predictor, the cricstat sitemap.

Nginx sends /cricket/players/<slug>/ and /cricket/countries/<slug>/ here (/pages/...), and falls
back to the plain static shell if the API is down. The shell is the same file Nginx would serve
(cricstat/web, mounted read-only): this module only swaps the head tags, adds robots + JSON-LD and
puts a short summary inside the box the page's JavaScript fills, so visitors see the same page and
search engines see real content. Every value is HTML-escaped.
"""
import html
import json
import os
import re
import threading
from typing import Dict, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from application_logic.services import forecast_service, pages_service
from application_logic.services.golden import trunc2
from db_logic.repository import meta_repo
from shared.config import ATTRIBUTION, Config
from shared.exceptions import ApiError
from shared.logger import get_logger

log = get_logger("pages")
GENDER_LD = {"male": "Male", "female": "Female"}
GODL_NOTE = "No endorsement by the Government of India is implied."   # GODL-India condition


class Shells:
    """The static page shells, re-read when the file changes (a gen_pages.py run)."""

    def __init__(self, web_dir: str):
        self.web_dir = web_dir
        self._cache: Dict[str, Tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, section: str) -> Tuple[str, float]:
        path = os.path.join(self.web_dir, section, "index.html")
        mtime = os.stat(path).st_mtime          # FileNotFoundError → 503 (Nginx serves the shell)
        with self._lock:
            hit = self._cache.get(path)
            if hit and hit[0] == mtime:
                return hit[1], mtime
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with self._lock:
            self._cache[path] = (mtime, text)
        return text, mtime


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def ld_json(obj: dict) -> str:
    """JSON-LD is data, never executed; '<' is escaped so nothing can close the script tag."""
    return ('<script type="application/ld+json">%s</script>\n'
            % json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c"))


def set_head(shell: str, title: str, desc: str, url: Optional[str], robots: str,
             extra: str = "", og_type: Optional[str] = None, image: Optional[str] = None) -> str:
    def attr(pattern: str, value: str, text: str) -> str:
        return re.sub(pattern, lambda m: m.group(1) + esc(value) + m.group(2), text, count=1)
    out = re.sub(r"<title>.*?</title>", lambda m: "<title>%s</title>" % esc(title), shell,
                 count=1, flags=re.S)
    out = attr(r'(<meta name="description" content=")[^"]*(")', desc, out)
    out = attr(r'(<meta property="og:title" content=")[^"]*(")', title, out)
    out = attr(r'(<meta property="og:description" content=")[^"]*(")', desc, out)
    if og_type:
        out = attr(r'(<meta property="og:type" content=")[^"]*(")', og_type, out)
    if image:                                  # a player's photo: a small portrait card
        out = attr(r'(<meta property="og:image" content=")[^"]*(")', image, out)
        out = attr(r'(<meta name="twitter:card" content=")[^"]*(")', "summary", out)
    if url:
        out = attr(r'(<link rel="canonical" href=")[^"]*(")', url, out)
        out = attr(r'(<meta property="og:url" content=")[^"]*(")', url, out)
    else:                                      # a 404 has no canonical page
        out = re.sub(r'<link rel="canonical" href="[^"]*">\n?', "", out, count=1)
        out = re.sub(r'<meta property="og:url" content="[^"]*">\n?', "", out, count=1)
    robots_tag = '<meta name="robots" content="%s">\n' % robots
    return out.replace("</head>", robots_tag + extra + "</head>", 1)


def fill(shell: str, marker: str, inner: str) -> str:
    """Replace the contents of the element whose opening tag is exactly `marker` (nested elements
    of the same tag are matched, so the whole placeholder goes)."""
    i = shell.find(marker)
    if i < 0:
        log.warning("page shell has no %s; serving it without a summary", marker)
        return shell
    tag = re.match(r"<(\w+)", marker).group(1)
    j = pos = i + len(marker)
    depth = 1
    for m in re.compile(r"<(/?)%s\b[^>]*>" % tag).finditer(shell, pos):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return shell[:j] + inner + shell[m.start():]
    log.warning("page shell: %s is not closed; serving it without a summary", marker)
    return shell


def _r(v) -> str:
    return "-" if v is None else trunc2(v)


def _n(v) -> str:
    return "-" if v is None else f"{v:,}"


def player_summary(p: dict, data_as_of: Optional[str]) -> str:
    team = p["team"]
    team_html = ""
    if team:
        name = esc(team["name"] + (" women" if p["gender"] == "female" else ""))
        team_html = ('<a href="/cricket/countries/%s/">%s</a>' % (esc(team["slug"]), name)
                     if team["slug"] and team["team_type"] == "international" else name)
    facts = " · ".join(x for x in (team_html, esc(p["role"]) if p["role"] else "",
                                   esc(p["span"])) if x)
    born = '<p class="dim">%s</p>' % esc(p["born"]) if p.get("born") else ""
    ph = p.get("photo")
    figure = "" if not ph else (
        '<figure class="ssr-photo"><img src="%s" width="%s" height="%s" alt="%s">'
        '<figcaption class="tiny muted">Photo: %s, <a href="%s">%s</a>, via '
        '<a href="%s">Wikimedia Commons</a>%s</figcaption></figure>'
        % (esc(ph["url"]), esc(ph["width"]), esc(ph["height"]), esc(p["name"]),
           esc(ph["author"] or "unknown author"), esc(ph["licence_url"] or ph["source_url"]),
           esc(ph["licence"]), esc(ph["source_url"]),
           ". " + GODL_NOTE if (ph["licence"] or "").lower() == "godl-india" else ""))
    aka = (' <span class="muted">(%s on scorecards)</span>' % esc(p["scorecard_name"])
           if p["scorecard_name"] != p["name"] else "")
    rows = "".join(
        "<tr><th scope=\"row\" class=\"txt\">%s</th><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
        "<td>%s/%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (esc(r["label"]), _n(r["matches"]), _n(r["runs"]), _r(r["bat_avg"]),
           _r(r["strike_rate"]), _n(r["hundreds"]), _n(r["fifties"]), _n(r["wickets"]),
           _r(r["bowl_avg"]), _r(r["economy"])) for r in p["rows"])
    table = ("" if not rows else
             '<div class="card tablecard"><div class="scroll"><table>'
             '<caption class="sr-only">Career summary by format</caption><thead><tr>'
             '<th scope="col" class="txt">Format</th><th scope="col">Mat</th>'
             '<th scope="col">Runs</th><th scope="col">Ave</th><th scope="col">SR</th>'
             '<th scope="col">100/50</th><th scope="col">Wkts</th><th scope="col">Bowl ave</th>'
             '<th scope="col">Econ</th></tr></thead><tbody>%s</tbody></table></div></div>' % rows)
    return ('<section class="section ssr-summary" aria-label="Career summary">'
            '<div class="wrap stack">'
            '<div class="card accent">%s<h1>%s%s</h1><p class="dim">%s</p>%s</div>%s'
            '<p class="tiny muted">%s%s Averages and rates are cut to two decimals.</p>'
            '</div></section>'
            % (figure, esc(p["name"]), aka, facts, born, table, esc(ATTRIBUTION),
               " Data as of %s." % esc(data_as_of) if data_as_of else ""))


def team_summary(t: dict, data_as_of: Optional[str]) -> str:
    rows = "".join(
        "<tr><th scope=\"row\" class=\"txt\">%s</th><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
        "<td>%s</td><td>%s</td><td>%s</td></tr>"
        % (esc(r["label"]), _n(r["matches"]), _n(r["won"]), _n(r["lost"]), _n(r["tied"]),
           _n(r["drawn"]), _n(r["no_result"]), _r(r["win_pct"])) for r in t["rows"])
    table = ("" if not rows else
             '<div class="card tablecard"><div class="scroll"><table>'
             '<caption class="sr-only">Record by format</caption><thead><tr>'
             '<th scope="col" class="txt">Format</th><th scope="col">Mat</th><th scope="col">W</th>'
             '<th scope="col">L</th><th scope="col">T</th><th scope="col">D</th>'
             '<th scope="col">NR</th><th scope="col">Win %%</th></tr></thead><tbody>%s</tbody>'
             '</table></div></div>' % rows)
    return ('<div class="wrap stack ssr-summary">%s<p class="tiny muted">%s%s</p></div>'
            % (table, esc(ATTRIBUTION),
               " Data as of %s." % esc(data_as_of) if data_as_of else ""))


def _pct(p) -> str:
    p = p or 0
    return "0%" if p == 0 else "<0.1%" if p < 0.001 else "%.1f%%" % (100 * p)


def _nth(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, suffix)


def _day(iso: Optional[str]) -> str:
    """'2026-10-07' → '7 Oct 2026' (no locale dependence)."""
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    month = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()[int(m) - 1]
    return "%d %s %s" % (int(d), month, y)


def predictor_text(data: dict) -> Tuple[str, str, list]:
    """The forecast in plain words (for search engines and anyone reading the page without scripts):
    returns the meta description, the HTML section and the FAQ entries for JSON-LD."""
    teams = data["teams"]
    as_of = _day(data["forecast"]["data_as_of"])
    sims = "{:,}".format(data["forecast"]["n_simulations"])
    hosts = data["tournament"].get("hosts") or []
    home = ((data.get("model") or {}).get("elo") or {}).get("home") or 75

    def p(t: dict, stage: str = "champion") -> str:
        return _pct(t["probabilities"].get(stage))

    a, b, c = teams[:3]
    lead = "%s %s, %s %s and %s %s" % (a["team"], p(a), b["team"], p(b), c["team"], p(c))
    desc = ("Who will win the 2027 Cricket World Cup? cricstat's model: %s (updated %s). "
            "Chances for all %d teams from %s simulated tournaments, with the backtests behind "
            "them." % (lead, as_of, len(teams), sims))
    host_chances = ", ".join("%s %s (%s favourite)" % (t["team"], p(t), _nth(i + 1))
                             for i, t in enumerate(teams) if t["team"] in hosts)
    faq = [
        ("Who is the favourite to win the 2027 Cricket World Cup?",
         "On %s, cricstat's model makes %s the favourite with a %s chance of winning the title, "
         "ahead of %s (%s) and %s (%s). The numbers come from %s simulated tournaments in the "
         "published format and change as teams play."
         % (as_of, a["team"], p(a), b["team"], p(b), c["team"], p(c), sims)),
        ("Can the hosts win?",
         "South Africa, Zimbabwe and Namibia host the tournament. Home teams get a %s-point boost "
         "in cricstat Elo, measured from every ODI since 2002. Their title chances: %s."
         % (home, host_chances)),
        ("How are the chances calculated?",
         "Every team gets a cricstat Elo rating (cricstat's own rating, not the ICC ranking) from "
         "every men's ODI since 2002. The 2027 tournament, Qualifier included, is then played %s "
         "times with those ratings, home advantage, rain-offs at each host's usual rate and a "
         "year's worth of uncertainty; a team's chance is the share of runs it wins. The model was "
         "tested on 900 ODIs since 2019, each predicted before it was played." % sims),
        ("How often is the forecast updated?",
         "Daily, after the latest results arrive; it only moves when a team plays an ODI. "
         "Last update: %s." % as_of),
    ]
    rows = "".join(
        "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (i + 1, esc(t["team"]),
           esc(t.get("group") or ("" if t.get("direct_qualifier") else "Qualifier")),
           esc(p(t, "semi")), esc(p(t, "final")), esc(p(t)))
        for i, t in enumerate(teams))
    table = ('<details class="wc-seo-table"><summary>Every team\'s chances as text (%d teams, '
             '%s)</summary><table><thead><tr><th>#</th><th>Team</th><th>Group</th>'
             '<th>Semi-final</th><th>Final</th><th>Title</th></tr></thead><tbody>%s</tbody>'
             '</table></details>' % (len(teams), esc(as_of), rows))
    section = ('<div class="section-label">The forecast in words</div>'
               '<h2 class="section-title">Who will win the 2027 Cricket World Cup?</h2>'
               + "".join("<h3>%s</h3><p>%s</p>" % (esc(q), esc(ans)) for q, ans in faq)
               + table
               + '<p class="tiny muted">A statistical estimate for fun and learning, not betting '
                 'advice. <a href="/cricket/methodology/">How it works</a>.</p>')
    return desc, section, faq


def register(app: FastAPI, cfg: Config) -> None:
    db = app.state.db
    shells = Shells(cfg.WEB_DIR)
    site, prefix = cfg.SITE_URL.rstrip("/"), cfg.PUBLIC_PREFIX.rstrip("/")
    cache = "public, max-age=%d, stale-while-revalidate=%d" % (cfg.CACHE_MAX_AGE, cfg.CACHE_SWR)
    author = {"@type": "Person", "@id": site + "/#archit", "name": "Archit Pandya"}

    def build() -> dict:
        return db.cached("build", lambda: meta_repo.latest_build(db) or {})

    def respond(request: Request, section: str, page: dict, render) -> Response:
        b = build()
        try:
            shell, mtime = shells.get(section)
        except OSError as exc:            # no shell mounted: Nginx falls back to the static file
            log.warning("page shell unavailable: %s", exc)
            return Response("page shell unavailable", status_code=503, media_type="text/plain")
        etag = '"p%s-%d-%d"' % (b.get("build_id"), int(mtime), page["status"])
        headers = {"ETag": etag, "Cache-Control": cache}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return HTMLResponse(render(shell, b.get("data_as_of")), status_code=page["status"],
                            headers=headers)

    def not_found(shell: str, what: str) -> str:
        return set_head(shell, "%s not found | cricstat" % what,
                        "There's no %s at this address on cricstat." % what.lower(), None,
                        "noindex")

    @app.get("/pages/players/{slug}/", include_in_schema=False)
    def player_page(request: Request, slug: str):
        page = pages_service.player_page(db, slug, cfg.INDEX_MIN_INTL, cfg.INDEX_MIN_LEAGUE)
        if page["status"] == 301:
            return RedirectResponse("%s/players/%s/" % (prefix, page["slug"]), status_code=301,
                                    headers={"Cache-Control": cache})
        if page["status"] == 404:
            return respond(request, "players", page, lambda s, _: not_found(s, "Player"))
        url = "%s%s/players/%s/" % (site, prefix, page["slug"])

        def render(shell: str, as_of: Optional[str]) -> str:
            ld = {"@context": "https://schema.org", "@type": "ProfilePage", "url": url,
                  "name": page["title"], "isPartOf": {"@id": site + "/#site"}, "author": author,
                  "mainEntity": dict(
                      {"@type": "Person", "name": page["name"], "description": page["description"]},
                      **({"alternateName": page["scorecard_name"]}
                         if page["scorecard_name"] != page["name"] else {}),
                      **({"gender": GENDER_LD[page["gender"]]} if page["gender"] in GENDER_LD
                         else {}),
                      **({"memberOf": {"@type": "SportsTeam", "name": page["team"]["name"],
                                       "sport": "Cricket"}} if page["team"] else {}),
                      **({"sameAs": ["https://www.wikidata.org/wiki/" + page["wikidata_qid"]]}
                         if page["wikidata_qid"] else {}),
                      **({"birthDate": page["date_of_birth"]}
                         if len(page["date_of_birth"] or "") == 10 else {}),
                      **({"birthPlace": {"@type": "Place", "name": page["birthplace"]}}
                         if page["birthplace"] else {}),
                      **({"image": site + page["photo"]["url"]} if page["photo"] else {}))}
            out = set_head(shell, page["title"], page["description"], url,
                           "index,follow" if page["indexable"] else "noindex,follow",
                           ld_json(ld), og_type="profile",
                           image=site + page["photo"]["url"] if page["photo"] else None)
            # The intro (heading, seal, player count) is for the plain Players page only.
            out = out.replace('<div class="wc-head p-intro" id="p-intro">',
                              '<div class="wc-head p-intro" id="p-intro" hidden>', 1)
            return fill(out, '<div id="p-profile" aria-live="polite">',
                        player_summary(page, as_of))
        return respond(request, "players", page, render)

    @app.get("/pages/countries/{slug}/", include_in_schema=False)
    def team_page(request: Request, slug: str):
        page = pages_service.team_page(db, slug, cfg.INDEX_MIN_INTL)
        if page["status"] == 404:
            return respond(request, "countries", page, lambda s, _: not_found(s, "Team"))
        url = "%s%s/countries/%s/" % (site, prefix, page["slug"])

        def render(shell: str, as_of: Optional[str]) -> str:
            ld = {"@context": "https://schema.org", "@type": "SportsTeam", "name": page["name"],
                  "sport": "Cricket", "url": url, "description": page["description"]}
            if page["gender"] in GENDER_LD:
                ld["gender"] = GENDER_LD[page["gender"]]
            out = set_head(shell, page["title"], page["description"], url,
                           "index,follow" if page["indexable"] else "noindex,follow",
                           ld_json(ld))
            out = fill(out, '<h1 id="c-name" style="font-size:clamp(2rem,5vw,3rem);margin:0">',
                       esc(page["name"]))
            # The shell is the Countries landing (world map); a team page shows its own header.
            out = out.replace('<div id="c-landing"', '<div id="c-landing" hidden', 1)
            out = out.replace('<header class="hero left" id="c-hero" hidden>',
                              '<header class="hero left" id="c-hero">', 1)
            return fill(out, '<div id="c-body" aria-live="polite">', team_summary(page, as_of))
        return respond(request, "countries", page, render)

    @app.get("/pages/predictor/", include_in_schema=False)
    def predictor_page(request: Request):
        """The predictor with the live forecast written into the page (title, description, the
        forecast in words, FAQ JSON-LD, dateModified); 503 → Nginx serves the static page."""
        fdb = app.state.fdb
        try:
            data, _ = forecast_service.latest(db, fdb, "wc-2027")
            shell, mtime = shells.get("predictor")
        except (ApiError, OSError) as exc:
            log.warning("predictor page not rendered: %s", exc)
            return Response("predictor unavailable", status_code=503, media_type="text/plain")
        etag = '"w%s-%d"' % (data["forecast"]["forecast_id"], int(mtime))
        headers = {"ETag": etag, "Cache-Control": cache}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        url = "%s%s/predictor/" % (site, prefix)
        desc, section, faq = predictor_text(data)
        title = ("Cricket World Cup 2027 prediction: who will win? Every team's chances "
                 "| cricstat")
        ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": url,
               "description": desc, "dateModified": data["forecast"]["data_as_of"],
               "isPartOf": {"@id": site + "/#site"}, "author": author,
               "about": ["ICC Men's Cricket World Cup 2027", "Elo rating",
                         "Monte Carlo simulation"]},
              {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                  {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                  for q, a in faq]}]
        out = re.sub(r'<script type="application/ld\+json">.*?</script>\n?', "", shell,
                     count=1, flags=re.S)
        out = set_head(out, title, desc, url, "index,follow", "".join(ld_json(x) for x in ld))
        out = fill(out, '<div class="wrap wc-seo" id="wc-seo">', section)
        return HTMLResponse(out, headers=headers)

    @app.get("/pages/sitemap.xml", include_in_schema=False)
    def sitemap(request: Request):
        b = build()
        try:                                       # the predictor's date = its latest forecast
            fc = forecast_service.latest(db, app.state.fdb, "wc-2027")[0]["forecast"]
        except ApiError:
            fc = {}
        etag = '"s%s-f%s"' % (b.get("build_id"), fc.get("forecast_id"))
        headers = {"ETag": etag, "Cache-Control": cache}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        key = "sitemap-%d-%d" % (cfg.INDEX_MIN_INTL, cfg.INDEX_MIN_LEAGUE)
        entries = db.cached(key, lambda: pages_service.sitemap_entries(
            db, cfg.INDEX_MIN_INTL, cfg.INDEX_MIN_LEAGUE))
        if fc:
            entries = [{"path": "predictor/", "lastmod": fc.get("data_as_of")},
                       {"path": "methodology/", "lastmod": fc.get("data_as_of")}] + list(entries)
        urls = "".join("<url><loc>%s%s/%s</loc>%s</url>\n" % (
            site, prefix, esc(e["path"]),
            "<lastmod>%s</lastmod>" % esc(e["lastmod"]) if e["lastmod"] else "") for e in entries)
        body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s</urlset>\n'
                % urls)
        return Response(body, media_type="application/xml", headers=headers)
