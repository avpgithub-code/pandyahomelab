"""Generate the cricstat page shells (cricstat/web/**/index.html) from one template, so the nav,
footer and head stay identical on every page. Edit here, then run:  python3 cricstat/tools/gen_pages.py
Bump V when CSS/JS change (cache busting).

cricstat/web is bind-mounted LIVE into nginx (since the P0.4 deploy). So by default this writes into the review
copy cricstat/tools/staging/web (created from cricstat/web on first use; edit CSS/JS there too, and preview with
web_preview.py). After approval:  rsync -a cricstat/tools/staging/web/ cricstat/web/  (or run with --live),
then remove the staging copy."""
import datetime
import html as H
import json
import os
import re
import shutil
import sys
CRICSTAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if "--live" in sys.argv:
    WEB = os.path.join(CRICSTAT, "web")
else:
    WEB = os.path.join(CRICSTAT, "tools", "staging", "web")
    if not os.path.isdir(WEB):
        shutil.copytree(os.path.join(CRICSTAT, "web"), WEB)
V = "64"
SITE = "https://pandyahomelab.com"
HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#0d0f14">
<link rel="canonical" href="https://pandyahomelab.com{path}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="pandyaHomeLab">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://pandyahomelab.com{path}">
<meta property="og:image" content="https://pandyahomelab.com/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/cricket/assets/cricstat.css?v={v}">
{extra_head}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<nav class="site-nav" aria-label="cricstat">
  <a class="brand" href="/">pandya<em>HomeLab</em><span class="sep">/</span><span class="cs">cric<b>stat</b></span></a>
  <ul class="nav-links">
    <li><a href="/cricket/"{c_hub}>Overview</a></li>
    <li><a href="/cricket/countries/"{c_countries}>Countries</a></li>
    <li><a href="/cricket/players/"{c_players}>Players</a></li>
    <li><span class="soon" title="Coming in the next phase">ODI WC 2027 <span class="soon-tag">soon</span></span></li>
    <li><span class="soon" title="Coming in a later phase">Ask <span class="soon-tag">soon</span></span></li>
    <li><span class="soon" title="Coming in a later phase">Methodology <span class="soon-tag">soon</span></span></li>
    <li><a href="/cricket/licences/"{c_licences}>Licences</a></li>
  </ul>
  <a class="about-trigger" href="/cricket/about/" data-about{c_about}><span aria-hidden="true">ⓘ</span> About cricstat</a>
</nav>
<main id="main" class="page-top">
'''
FOOT = '''</main>
<footer class="site-foot">
  <p>Match data from Cricsheet (cricsheet.org), used under the Open Data Commons Attribution License 1.0.</p>
  <p>Not affiliated with or endorsed by Cricsheet, the ICC or any cricket board. Statistics are derived from the source data and may differ from official records.</p>
  <p><a href="/cricket/licences/">Data &amp; licences</a> · <a href="/privacy/">Privacy</a> · <a href="/cricket/about/">How cricstat was built</a> · <a href="/">pandyaHomeLab</a> · Built by <a href="/">Archit Pandya</a></p>
</footer>
<script src="/cricket/assets/flags.js?v={v}"></script>
<script src="/cricket/assets/cricstat.js?v={v}"></script>
<script src="/cricket/assets/about.js?v={v}"></script>
{scripts}
<script src="/feedback-widget.js"></script>
</body>
</html>
'''
def page(rel, path, title, desc, cur, body, scripts, og_type="website", extra_head=""):
    c = {k: "" for k in ("c_hub", "c_countries", "c_players", "c_licences", "c_about")}
    c["c_" + cur] = ' aria-current="page"'
    html = HEAD.format(title=title, desc=desc, path=path, v=V, og_type=og_type, extra_head=extra_head, **c) + body + FOOT.format(
        v=V, scripts="\n".join('<script src="%s"></script>' % s for s in scripts))
    os.makedirs(os.path.dirname(os.path.join(WEB, rel)) or WEB, exist_ok=True)
    open(os.path.join(WEB, rel), "w").write(html)

HUB = '''<header class="hero">
  <div class="wrap">
    <div class="eyebrow"><span class="dot"></span><span id="h-asof">Live cricket data</span></div>
    <h1 class="cs-lockup"><span class="sr-only">cricstat</span><span class="cs" aria-hidden="true">cr<span class="i-ball">ı<svg class="i-dot" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><defs><radialGradient id="emBall" cx="35%" cy="32%" r="70%"><stop offset="0" stop-color="#e2544b"/><stop offset=".65" stop-color="#b3201c"/><stop offset="1" stop-color="#6e1210"/></radialGradient></defs><circle cx="10" cy="10" r="9" fill="url(#emBall)"/><path d="M5.5 3.2c2.6 2.4 3.4 8.4 1.3 13.6M14.5 3.2c-2.6 2.4-3.4 8.4-1.3 13.6" stroke="#f5efe6" stroke-width="1.3" fill="none" stroke-linecap="round"/></svg></span>c<b>stat</b></span></h1>
    <p class="subtitle">Cricket statistics, forecasts and an AI analyst — built from open ball-by-ball data for men's and women's cricket, with every number traceable to its source.</p>
    <p class="hero-hook">2011 gave us the six. 2023 gave us the heartbreak. 2027 is the question. <a class="link-btn" href="/cricket/about/" data-about>Read the story →</a></p>
    <form class="search-bar" action="/cricket/players/" method="get" role="search">
      <input name="q" type="search" placeholder="Search a player — Kohli, Mandhana, Bumrah…" aria-label="Search players" autocomplete="off" minlength="2" required>
      <button class="btn pri" type="submit">Search</button>
    </form>
  </div>
</header>

<section class="section panel" aria-label="The data behind cricstat"><div class="wrap volume scoreboard">
  <div class="sb-head" aria-hidden="true"><span class="bulb"></span>The data behind cricstat<span class="bulb"></span></div>
    <div class="counters" aria-live="polite">
      <div class="counter"><i class="c-icon saff" aria-hidden="true">🏟️</i><b id="k-matches" class="sb">—</b><span>Matches</span><small class="c-note">Men's and women's, 2001 to today. Every result feeds the team ratings.</small></div>
      <div class="counter"><i class="c-icon blue" aria-hidden="true"><svg viewBox="0 0 24 24" width="24" height="24"><defs><radialGradient id="ball" cx="35%" cy="32%" r="70%"><stop offset="0" stop-color="#e2544b"/><stop offset=".65" stop-color="#b3201c"/><stop offset="1" stop-color="#6e1210"/></radialGradient></defs><circle cx="12" cy="12" r="10" fill="url(#ball)"/><path d="M5.2 4.9c3.6 3.2 5 9.9 1.9 15.4M18.8 4.9c-3.6 3.2-5 9.9-1.9 15.4" fill="none" stroke="#f5efe6" stroke-width="1.1" stroke-linecap="round"/><path d="M6.6 7.4l1.1-.6M7.5 10l1.2-.3M7.8 12.7h1.2M7.4 15.4l1.2.3M18.6 7.4l-1.1-.6M17.6 10l-1.2-.3M17.3 12.7h-1.2M17.7 15.4l-1.2.3" stroke="#f5efe6" stroke-width=".8" stroke-linecap="round"/><ellipse cx="8.6" cy="7.6" rx="2.2" ry="1.2" fill="#fff" opacity=".18" transform="rotate(-30 8.6 7.6)"/></svg></i><b id="k-deliveries" class="sb">—</b><span>Balls bowled</span><small class="c-note">Each one recorded: who bowled, who faced, what happened. Enough to train a ball-by-ball model.</small></div>
      <div class="counter"><i class="c-icon saff" aria-hidden="true">🧢</i><b id="k-players" class="sb">—</b><span>Players</span><small class="c-note">Careers followed across Tests, ODIs, T20Is and leagues, the basis for player-strength ratings.</small></div>
      <div class="counter"><i class="c-icon blue" aria-hidden="true">🌍</i><b id="k-teams" class="sb">—</b><span>Teams</span><small class="c-note">National sides and franchises, all rated by the same model.</small></div>
    </div>
    <p class="why-volume"><b>Why the volume matters:</b> about 2,600 men's ODIs are too few to teach a model who wins a match. 11.6 million deliveries are plenty, so the <a class="wc-hl" href="#about" data-about="predictor">ODI World Cup 2027 predictor</a> will learn team and player strength from every ball, then simulate the tournament thousands of times.</p>
    <a class="wc-tease" href="#about" data-about="predictor">
      <span class="wc-q"><svg class="wc-icon" viewBox="0 0 64 64" width="44" height="44" aria-hidden="true" focusable="false"><defs><linearGradient id="wcGold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFE38A"/><stop offset=".5" stop-color="#F5B82E"/><stop offset="1" stop-color="#B9800F"/></linearGradient></defs><path d="M33 22 C 36 14, 44 13, 47 6 C 50 11, 47 16, 52 19 C 46 21, 41 19, 37 25 Z" fill="#FF9933"/><path d="M33.6 23.6 C 37 17, 44.6 16.4, 48.2 10.6 C 50.6 14.6, 48.4 18.6, 53.4 21.6 C 47.4 23.4, 42.4 21.6, 38.4 27 Z" fill="#FFFFFF"/><path d="M34.4 25.4 C 38 20, 45 19.6, 49 15 C 51 18.4, 49.6 22, 54.6 24.4 C 48.6 26, 43.4 24.4, 39.6 29 Z" fill="#138808"/><path d="M18 20 H46 V24 C46 34, 40 41, 32 41 C24 41, 18 34, 18 24 Z" fill="url(#wcGold)"/><path d="M18 23 C11 23, 10 32, 19 34" fill="none" stroke="url(#wcGold)" stroke-width="3" stroke-linecap="round"/><path d="M46 23 C53 23, 54 32, 45 34" fill="none" stroke="url(#wcGold)" stroke-width="3" stroke-linecap="round"/><rect x="29.5" y="40" width="5" height="8" fill="url(#wcGold)"/><path d="M23 48 H41 L43 54 H21 Z" fill="url(#wcGold)"/><rect x="19" y="54" width="26" height="4" rx="1.5" fill="#8A5A0B"/><path d="M23 22 C23 30, 26 36, 30 38" fill="none" stroke="#FFF6CF" stroke-width="1.6" stroke-linecap="round" opacity=".7"/></svg> What are the chances of India lifting the 2027 ODI World Cup?</span>
      <span class="wc-sub">Three models — Elo ratings (statistics), machine learning and deep learning — are about to compete to answer that <span aria-hidden="true">→</span></span>
    </a>
</div></section>

<section class="section panel" aria-label="Match centre: results, your team, leaders and leagues"><div class="wrap scoreboard match-centre">
  <div class="sb-head board-head" aria-hidden="true"><span class="bulb"></span>Match centre<span class="mc-asof" id="mc-asof"></span><span class="bulb"></span></div>
  <div class="sec-tabs" role="tablist" aria-label="Hub sections">
    <button class="sec-tab" type="button" role="tab" id="tab-latest" aria-controls="pane-latest" aria-selected="true">📋 Latest results</button>
    <button class="sec-tab" type="button" role="tab" id="tab-follow" aria-controls="pane-follow" aria-selected="false" tabindex="-1">⭐ Following</button>
    <button class="sec-tab" type="button" role="tab" id="tab-leaders" aria-controls="pane-leaders" aria-selected="false" tabindex="-1">🏅 Leaders</button>
    <button class="sec-tab" type="button" role="tab" id="tab-leagues" aria-controls="pane-leagues" aria-selected="false" tabindex="-1">🏆 Leagues</button>
  </div>
  <div class="sec-pane" role="tabpanel" id="pane-latest" aria-labelledby="tab-latest">
  <div class="section-head">
    <div><div class="section-label">Scorecards</div><h2 class="section-title">Latest results</h2></div>
    <div class="row" style="gap:.8rem">
      <div class="tabs" role="group" aria-label="Format">
        <button class="tab" type="button" data-lfmt="ALL" aria-pressed="false">All</button>
        <button class="tab" type="button" data-lfmt="TEST" aria-pressed="false">Test</button>
        <button class="tab" type="button" data-lfmt="ODI" aria-pressed="true">ODI</button>
        <button class="tab" type="button" data-lfmt="T20I" aria-pressed="false">T20I</button>
      </div>
      <div class="radio-pill" role="radiogroup" aria-label="Men's or women's cricket">
        <label><input type="radio" name="lgender" value="male" checked><span>Men</span></label>
        <label><input type="radio" name="lgender" value="female"><span>Women</span></label>
      </div>
    </div>
  </div>
  <div class="carousel">
    <button class="car-btn prev" type="button" aria-label="Previous results" data-car="-1">‹</button>
    <div class="strip" id="latest" aria-live="polite" tabindex="0"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>
    <button class="car-btn next" type="button" aria-label="More results" data-car="1">›</button>
  </div>
  <div class="row" style="justify-content:space-between;gap:.6rem">
    <p class="tiny muted" id="latest-note">Newest first.</p>
    <p class="tiny" id="latest-fresh" hidden></p>
  </div>
  </div>
  <div class="sec-pane" role="tabpanel" id="pane-follow" aria-labelledby="tab-follow" hidden>
  <div class="section-head">
    <div class="row"><span id="follow-badge"></span><div><div class="section-label">Following</div><h2 class="section-title" id="following-title" style="margin:0">India</h2></div></div>
    <div class="field"><label for="follow">Follow a team</label><select id="follow" autocomplete="off"><option value="india-men">India (men)</option></select>
      <span class="tiny muted">Remembered in this browser only — no cookies <a href="#" id="follow-reset" hidden>· Reset to India</a></span></div>
  </div>
  <div id="follow-period" style="margin-bottom:.9rem"></div>
  <div class="grid" id="follow-cards" aria-live="polite"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>
  <p class="tiny muted" style="margin-top:.8rem">Following a team changes what you see, never the numbers: every model treats all teams the same way.</p>
  </div>
  <div class="sec-pane" role="tabpanel" id="pane-leaders" aria-labelledby="tab-leaders" hidden>
  <div class="section-head">
    <div><div class="section-label">Leaders</div><h2 class="section-title" id="leaders-title">This year's leaders</h2></div>
    <div class="tabs" role="group" aria-label="Leaders by format">
      <button class="tab" type="button" data-leaders="ALL" aria-pressed="false">All</button>
      <button class="tab" type="button" data-leaders="TEST" aria-pressed="false">Test</button>
      <button class="tab" type="button" data-leaders="ODI" aria-pressed="true">ODI</button>
      <button class="tab" type="button" data-leaders="T20I" aria-pressed="false">T20I</button>
    </div>
  </div>
  <div class="grid" id="leaders"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>
  </div>
  <div class="sec-pane" role="tabpanel" id="pane-leagues" aria-labelledby="tab-leagues" hidden>
  <div class="section-label">Leagues</div><h2 class="section-title">Featured leagues</h2>
  <p class="section-desc">Ball-by-ball for every season in the data. League pages are coming; player pages already split stats by league.</p>
  <div class="grid-4" id="leagues"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>
  </div>
</div></section>

'''
ARCHIT = {"@type": "Person", "@id": SITE + "/#archit", "name": "Archit Pandya", "url": SITE + "/"}


def ld_json(obj):
    """A JSON-LD block (data only, never executed); '</' is escaped so it can't close the tag."""
    return ('<script type="application/ld+json">%s</script>\n'
            % json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/"))


HUB_DESC = ("Cricket statistics for men's and women's cricket across Tests, ODIs, T20Is and major leagues, built from "
            "open ball-by-ball data — and an ODI World Cup 2027 predictor that compares Elo, machine-learning and "
            "deep-learning models.")
page("index.html", "/cricket/", "cricstat — cricket stats, ODI World Cup 2027 predictor & AI analyst | pandyaHomeLab",
     HUB_DESC, "hub", HUB, ["/cricket/assets/hub.js?v=" + V],
     extra_head=ld_json({"@context": "https://schema.org", "@type": "WebApplication", "@id": SITE + "/cricket/#app",
                         "name": "cricstat", "url": SITE + "/cricket/", "description": HUB_DESC,
                         "applicationCategory": "SportsApplication", "operatingSystem": "Any",
                         "isAccessibleForFree": True, "inLanguage": "en", "author": ARCHIT,
                         "isPartOf": {"@id": SITE + "/#site"},
                         "about": ["Cricket statistics", "ODI World Cup 2027", "Machine learning", "Deep learning"]}))

PLAYERS = '''<header class="hero left">
  <div class="wrap">
    <div class="eyebrow"><span class="dot"></span>Players</div>
    <form class="search-bar" id="p-form" action="/cricket/players/" method="get" role="search">
      <input id="p-search" name="q" type="search" placeholder="Name, surname or initials — e.g. Kohli, S Mandhana" aria-label="Search players" autocomplete="off" minlength="2" required>
      <button class="btn pri" type="submit">Search</button>
    </form>
    <div id="p-results" aria-live="polite" style="margin-top:1rem"></div>
  </div>
</header>
<div id="p-profile" aria-live="polite"></div>
'''
page("players/index.html", "/cricket/players/", "Player statistics — cricstat | pandyaHomeLab",
     "Career, year-by-year, phase and opponent statistics for men's and women's cricketers: Tests, ODIs, T20Is and major leagues, from Cricsheet ball-by-ball data.",
     "players", PLAYERS, ["/vendor/chart.js-4.4.0/chart.umd.min.js", "/cricket/assets/players.js?v=" + V])

COUNTRIES = '''<header class="hero left" id="c-hero">
  <div class="wrap" style="display:flex;flex-wrap:wrap;gap:1.5rem;align-items:center;justify-content:space-between">
    <div class="row" style="gap:1.2rem"><span id="c-badge"></span>
      <div><div class="eyebrow" style="margin-bottom:.6rem"><span class="dot"></span>Country</div>
        <h1 id="c-name" style="font-size:clamp(2rem,5vw,3rem);margin:0">…</h1></div></div>
    <div class="row" style="align-items:flex-end;gap:1rem">
      <div class="tabs" role="group" aria-label="Men's or women's team" id="c-gender"></div>
      <div class="field"><label for="c-team">Switch team</label><select id="c-team" autocomplete="off"></select></div>
    </div>
  </div>
</header>
<div id="c-body" aria-live="polite"><div class="wrap"><div class="skeleton"></div></div></div>
'''
page("countries/index.html", "/cricket/countries/", "Team records — cricstat | pandyaHomeLab",
     "Team records by format, recent results, head to head, home and away, results by year and top run-scorers and wicket-takers for men's and women's international teams.",
     "countries", COUNTRIES, ["/vendor/chart.js-4.4.0/chart.umd.min.js", "/cricket/assets/countries.js?v=" + V])

LIC = '''<header class="hero left"><div class="wrap">
  <div class="eyebrow"><span class="dot"></span>Data &amp; licences</div>
  <h1 style="font-size:clamp(2rem,5vw,3rem)">Where the numbers come from</h1>
  <p class="subtitle">Open data, credited; what it covers and what it doesn't; and how your privacy is kept.</p>
</div></header>
<section class="section" style="padding-top:0"><div class="wrap stack" style="max-width:940px">
  <div class="card accent">
    <h2>Attribution</h2>
    <p class="dim">Match data from Cricsheet (<a href="https://cricsheet.org/">cricsheet.org</a>), used under the <a href="https://opendatacommons.org/licenses/by/1-0/">Open Data Commons Attribution License 1.0</a>.</p>
    <p class="dim" style="margin-top:.6rem"><span class="cs">cric<b>stat</b></span> is an independent, non-commercial project. It is not affiliated with or endorsed by Cricsheet, the ICC or any cricket board, and uses no board or team logos.</p>
  </div>
  <div class="card tablecard">
    <div class="card-head"><h2>Sources</h2></div>
    <div class="scroll"><table>
      <thead><tr><th scope="col" class="txt">Source</th><th scope="col" class="txt">Used for</th><th scope="col" class="txt">Licence</th></tr></thead>
      <tbody>
        <tr><td class="txt">Cricsheet match data</td><td class="txt">Ball-by-ball data for every match on these pages (men's and women's, 2001–present)</td><td class="txt">ODC-BY 1.0 · attribution required</td></tr>
        <tr><td class="txt">Cricsheet Register</td><td class="txt">Player identities and name variants used for search</td><td class="txt">ODC-BY 1.0 · attribution required</td></tr>
        <tr><td class="txt">Wikidata</td><td class="txt">Players' full names, dates and places of birth, matched only by their ESPNcricinfo id (never by name)</td><td class="txt">CC0 · no attribution required, credited anyway</td></tr>
        <tr><td class="txt">Wikimedia Commons</td><td class="txt">Player photos: a small copy of each image, served from this site, with its author, licence and file page shown next to it</td><td class="txt">Public domain, CC0, CC BY or CC BY-SA, per photo</td></tr>
        <tr><td class="txt">Wikimedia Commons</td><td class="txt">National flags, used unaltered at their official proportions and only to identify national teams (<a href="#flag-sources">source of each flag</a>)</td><td class="txt">Public domain (or CC0)</td></tr>
        <tr><td class="txt">Chart.js</td><td class="txt">Charts, served from this site (<a href="/vendor/chart.js-4.4.0/LICENSE">licence text</a>)</td><td class="txt">MIT</td></tr>
      </tbody>
    </table></div>
    <p class="tiny muted" style="padding:0 1.3rem 1.1rem">Photos are resized copies of the Commons originals and are not otherwise changed (the profile frame only crops what is shown). Players under 18 are shown without a photo or birth details. Published figures from public records, including Wikipedia, are used privately to cross-check our numbers and are not reproduced here.</p>
    <details class="flag-sources" id="flag-sources"><summary>Source of each flag (@@NFLAGS@@)</summary>
      <p class="tiny muted">Each flag is an unchanged copy of the Wikimedia Commons file linked here. Some countries also protect their flag by law (India, for example, by its Flag Code); flags here only identify the national team.</p>
      <ul>@@FLAGS@@</ul>
    </details>
  </div>
  <div class="card">
    <h2>What the data covers</h2>
    <ul class="plain">
      <li>Matches from late 2001 onwards. Earlier history — including the 1983 ODI World Cup — is not in the data.</li>
      <li>Coverage is thinner in the early years: men's Tests before about 2005 and women's international cricket before about 2016.</li>
      <li>Afghanistan men's matches are not included by the data source, so players' totals against Afghanistan are missing.</li>
      <li>Statistics are derived from ball-by-ball records and can differ from official figures. Averages and rates are shown cut to two decimals, as published records show them.</li>
    </ul>
  </div>
  <div class="grid">
    <div class="card"><h2>Privacy</h2><p class="dim">No cookies, and nothing is loaded from third parties. The team you follow is remembered in your browser only (local storage) and never sent to the server. Visits are counted the same way as on the rest of this site.</p><p style="margin-top:.6rem"><a href="/privacy/">Full privacy page →</a></p></div>
    <div class="card"><h2>Disclaimers</h2><p class="dim">Statistics are derived from the source data and may differ from official records. When forecasts and the AI analyst arrive, forecasts will be for education and entertainment, not betting advice, and every AI answer will show how it was computed.</p></div>
    <div class="card"><h2>Corrections</h2><p class="dim">Spotted an error, or want details about a player reviewed or a photo removed? Email <a href="mailto:privacy@pandyahomelab.com">privacy@pandyahomelab.com</a> with the page and what looks wrong.</p></div>
  </div>
</div></section>
'''
def flag_sources():
    """The licences page lists each flag's Commons page (from flags.js, written by fetch_flags.py)."""
    with open(os.path.join(WEB, "assets", "flags.js"), encoding="utf-8") as f:
        src = f.read()
    flags = json.loads(src[src.index("{"):src.rindex("}") + 1])
    items = "".join('<li><a href="%s">%s</a> · %s</li>' % (H.escape(f["source"]), H.escape(n), H.escape(f["licence"]))
                    for n, f in sorted(flags.items()))
    return LIC.replace("@@NFLAGS@@", str(len(flags))).replace("@@FLAGS@@", items)


page("licences/index.html", "/cricket/licences/", "Data & licences — cricstat | pandyaHomeLab",
     "Where cricstat's data comes from, its licences, what it covers, privacy and disclaimers.", "licences", flag_sources(), [])

# /cricket/about/ — the About drawer's story as a real page, rendered from the same about.json at build time,
# so search engines (which never open the drawer) can read it. Section ids are anchors (#predictor, #analyst…).
ABOUT_UPDATED = "2026-10-07"


def rich(text):
    """'**bold**' / '*italic*' → <strong>/<em>; everything else escaped (same rule as about.js)."""
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append("<strong>%s</strong>" % H.escape(part[2:-2]))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append("<em>%s</em>" % H.escape(part[1:-1]))
        else:
            out.append(H.escape(part))
    return "".join(out)


def about_page():
    with open(os.path.join(WEB, "about.json"), encoding="utf-8") as f:
        data = json.load(f)
    toc, secs = [], []
    for s in data["sections"]:
        toc.append('<a href="#%s">%s</a>' % (H.escape(s["id"]), H.escape(s["title"])))
        b = ['<section class="about-section card" id="%s">' % H.escape(s["id"]),
             '<h2><span class="icon" aria-hidden="true">%s</span>%s</h2>' % (H.escape(s.get("icon", "")), H.escape(s["title"]))]
        b += ["<p>%s</p>" % rich(p) for p in s.get("body", [])]
        if s.get("bullets"):
            b.append('<ul class="about-bullets">%s</ul>' % "".join(
                "<li><b>%s</b> — %s</li>" % (H.escape(x["label"]), rich(x["text"])) for x in s["bullets"]))
        b += ["<p>%s</p>" % rich(p) for p in s.get("after", [])]
        if s.get("diagram", {}).get("type") == "mermaid":
            b.append('<div class="about-diagram"><pre class="mermaid">%s</pre></div>' % H.escape(s["diagram"]["code"]))
        if s.get("facts"):
            b.append('<div class="about-facts">%s</div>' % "".join(
                '<div class="about-fact"><div class="about-fact-label">%s</div><div class="about-fact-value">%s</div></div>'
                % (H.escape(x["label"]), H.escape(x["value"])) for x in s["facts"]))
        links = [l for l in s.get("links", []) if l["href"] != "/cricket/about/"]
        if links:
            b.append('<div class="about-links">%s</div>' % "".join(
                '<a class="about-link" href="%s">%s →</a>' % (H.escape(l["href"]), H.escape(l["label"])) for l in links))
        secs.append("\n".join(b) + "\n</section>")
    when = datetime.date.fromisoformat(ABOUT_UPDATED)
    body = ('<header class="hero left"><div class="wrap">\n'
            '  <div class="eyebrow"><span class="dot"></span>About cricstat</div>\n'
            '  <h1 style="font-size:clamp(2rem,5vw,3rem)">How I built <span class="cs">cric<b>stat</b></span></h1>\n'
            '  <p class="subtitle">%s</p>\n'
            '  <p class="byline">By <a href="/">Archit Pandya</a> · Updated <time datetime="%s">%d %s</time></p>\n'
            '  <nav class="about-toc" aria-label="On this page">%s</nav>\n'
            '</div></header>\n'
            '<section class="section about-page" style="padding-top:0"><div class="wrap stack" style="max-width:860px">\n%s\n'
            '<p><a class="btn pri" href="/cricket/">Explore the stats →</a></p>\n</div></section>\n'
            % (H.escape(data["tagline"]), ABOUT_UPDATED, when.day, when.strftime("%B %Y"), " · ".join(toc), "\n".join(secs)))
    title = "How I built cricstat: cricket analytics & an ODI World Cup 2027 predictor | Archit Pandya"
    desc = ("Why and how Archit Pandya built cricstat: a cricket analytics project with an ODI World Cup 2027 predictor "
            "(Elo vs machine learning vs deep learning, backtested on 2019 and 2023), an AI analyst with published "
            "evals, and a daily data pipeline over 11.6 million deliveries.")
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": "How I built cricstat",
          "description": desc, "url": SITE + "/cricket/about/", "mainEntityOfPage": SITE + "/cricket/about/",
          "image": SITE + "/og-image.png", "datePublished": "2026-10-07", "dateModified": ABOUT_UPDATED,
          "inLanguage": "en", "author": ARCHIT, "publisher": ARCHIT, "isPartOf": {"@id": SITE + "/#site"},
          "about": [{"@id": SITE + "/cricket/#app"}, "ODI World Cup 2027", "Cricket analytics", "Machine learning"]}
    page("about/index.html", "/cricket/about/", title, desc, "about", body, [], og_type="article", extra_head=ld_json(ld))


about_page()
print("pages written to", WEB)
