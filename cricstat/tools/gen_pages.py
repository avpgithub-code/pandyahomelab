"""Generate the cricstat page shells (cricstat/web/**/index.html) from one template, so the nav,
footer and head stay identical on every page. Edit here, then run:  python3 cricstat/tools/gen_pages.py
Bump V when CSS/JS change (cache busting).

cricstat/web is bind-mounted LIVE into nginx (since the P0.4 deploy). So by default this writes into the review
copy cricstat/tools/staging/web (created from cricstat/web on first use; edit CSS/JS there too, and preview with
web_preview.py). After approval:  rsync -a cricstat/tools/staging/web/ cricstat/web/  (or run with --live),
then remove the staging copy."""
import datetime
import html as H
import csv
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
V = "120"
# P1.6 ships in two parts: False = the approved non-predictor pages only (nav "ODI WC 2027 soon", no predictor page,
# no model numbers on the map, no predictor rows on the licences page). True at the full P1.6 deploy.
PREDICTOR_LIVE = os.environ.get("CRICSTAT_PREDICTOR_LIVE", "1") == "1"   # live since the P1.6 launch; CRICSTAT_PREDICTOR_LIVE=0 builds the old partial set
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
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/cricket/assets/cricstat.css?v={v}">
{extra_head}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<nav class="site-nav" aria-label="cricstat">
  <a class="brand" href="/">pandya<em>HomeLab</em><span class="sep">/</span><span class="cs"><i class="cs-sr">cricstat</i><i class="cs-w" aria-hidden="true">cr<i class="cs-i">ı</i>c<b>stat</b></i></span></a>
  <ul class="nav-links">
    <li><a href="/cricket/"{c_hub}>Overview</a></li>
    <li><a href="/cricket/countries/"{c_countries}>Countries</a></li>
    <li><a href="/cricket/players/"{c_players}>Players</a></li>
    {nav_predictor}
    <li><span class="soon" title="Coming in a later phase">Ask <span class="soon-tag">soon</span></span></li>
    {nav_method}
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
def page(rel, path, title, desc, cur, body, scripts, og_type="website", extra_head="", og_image=SITE + "/og-image.png"):
    c = {k: "" for k in ("c_hub", "c_countries", "c_players", "c_licences", "c_about", "c_predictor", "c_method")}
    c["c_" + cur] = ' aria-current="page"'
    c["nav_method"] = ('<li><a href="/cricket/methodology/"%s>Methodology</a></li>' % c["c_method"] if PREDICTOR_LIVE else
                       '<li><span class="soon" title="Coming in a later phase">Methodology <span class="soon-tag">soon</span></span></li>')
    c["nav_predictor"] = ('<li><a href="/cricket/predictor/"%s>ODI WC 2027</a></li>' % c["c_predictor"] if PREDICTOR_LIVE else
                          '<li><span class="soon" title="Coming in a later phase">ODI WC 2027 <span class="soon-tag">soon</span></span></li>')
    html = HEAD.format(title=title, desc=desc, path=path, v=V, og_type=og_type, extra_head=extra_head, og_image=og_image, **c) + body + FOOT.format(
        v=V, scripts="\n".join('<script src="%s"></script>' % s for s in scripts))
    os.makedirs(os.path.dirname(os.path.join(WEB, rel)) or WEB, exist_ok=True)
    open(os.path.join(WEB, rel), "w").write(html)

# "stat" on the pitch: a Manhattan (runs per over) of India's chase in the 2011 World Cup final, match 433606
# in Cricsheet (serving DB: SUM(runs_total) per over_no, innings 2; wickets fell in overs 1, 7, 22, 42; target 275).
# Real data, so it is captioned; the last bar holds Dhoni's six (48.2).
WC2011_CHASE = [4, 6, 5, 11, 1, 4, 1, 1, 2, 6, 9, 11, 7, 4, 9, 5, 5, 5, 3, 6, 4, 6, 2, 5, 2, 4, 6, 8, 4, 5,
                6, 8, 5, 5, 8, 8, 5, 8, 6, 11, 2, 4, 5, 8, 5, 3, 11, 11, 7]
WC2011_WICKETS = {1, 7, 22, 42}


def manhattan_svg():
    x0, x1, base, per_run, worm = 404.0, 776.0, 154.0, 4.2, 0.43
    w = (x1 - x0) / len(WC2011_CHASE)
    out = ['<g class="manhattan">']
    for i, r in enumerate(WC2011_CHASE):
        x, hgt = x0 + i * w, r * per_run
        last = i == len(WC2011_CHASE) - 1
        out.append('<rect class="mh-bar%s" style="--i:%d" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1"/>'
                   % (" mh-six" if last else "", i, x + .8, base - hgt, w - 1.6, hgt))
        if i + 1 in WC2011_WICKETS:
            out.append('<circle class="mh-wkt" style="--i:%d" cx="%.1f" cy="%.1f" r="1.7"/>' % (i, x + w / 2, base - hgt - 3.5))
    total, pts = 0, ["%.1f,%.1f" % (x0, base)]
    for i, r in enumerate(WC2011_CHASE):
        total += r
        pts.append("%.1f,%.1f" % (x0 + (i + 1) * w, base - total * worm))
    ty = base - 275 * worm
    out.append('<line class="mh-target" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (x0, ty, x1, ty))
    out.append('<text class="mh-label" x="%.1f" y="%.1f">target 275</text>' % (x0 + 2, ty - 3))
    out.append('<polyline class="mh-worm" pathLength="1" points="%s"/>' % " ".join(pts))
    lx = x0 + (len(WC2011_CHASE) - .5) * w
    out.append('<text class="mh-six-label" x="%.1f" y="%.1f" text-anchor="middle">6</text>'
               % (lx, base - WC2011_CHASE[-1] * per_run - 4))
    out.append('</g>')
    return "".join(out)


HUB = '''<header class="hero">
  <div class="wrap">
    <div class="eyebrow"><span class="dot"></span><span id="h-asof">Live cricket data</span></div>
    <div class="pitch"><svg class="pitch-svg" viewBox="0 0 800 170" aria-hidden="true" focusable="false">  <defs><radialGradient id="sq" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#2f8f4e" stop-opacity=".32"/><stop offset="1" stop-color="#2f8f4e" stop-opacity="0"/></radialGradient></defs><ellipse cx="400" cy="85" rx="420" ry="95" fill="url(#sq)"/>  <defs><linearGradient id="mow" x1="0" x2="1" y1="0" y2="0"><stop offset="0.0" stop-color="#fff" stop-opacity="0"/><stop offset="0.1" stop-color="#fff" stop-opacity="0"/><stop offset="0.1" stop-color="#fff" stop-opacity="0.05"/><stop offset="0.2" stop-color="#fff" stop-opacity="0.05"/><stop offset="0.2" stop-color="#fff" stop-opacity="0"/><stop offset="0.3" stop-color="#fff" stop-opacity="0"/><stop offset="0.3" stop-color="#fff" stop-opacity="0.05"/><stop offset="0.4" stop-color="#fff" stop-opacity="0.05"/><stop offset="0.4" stop-color="#fff" stop-opacity="0"/><stop offset="0.5" stop-color="#fff" stop-opacity="0"/><stop offset="0.5" stop-color="#fff" stop-opacity="0.05"/><stop offset="0.6" stop-color="#fff" stop-opacity="0.05"/><stop offset="0.6" stop-color="#fff" stop-opacity="0"/><stop offset="0.7" stop-color="#fff" stop-opacity="0"/><stop offset="0.7" stop-color="#fff" stop-opacity="0.05"/><stop offset="0.8" stop-color="#fff" stop-opacity="0.05"/><stop offset="0.8" stop-color="#fff" stop-opacity="0"/><stop offset="0.9" stop-color="#fff" stop-opacity="0"/><stop offset="0.9" stop-color="#fff" stop-opacity="0.05"/><stop offset="1.0" stop-color="#fff" stop-opacity="0.05"/></linearGradient></defs>  <rect x="20" y="15" width="760" height="140" rx="6" fill="#b89a68" opacity="0.2"/><rect x="20" y="15" width="760" height="140" rx="6" fill="url(#mow)"/>  <line x1="110" y1="15" x2="110" y2="155" stroke="rgba(255,255,255,0.42)" stroke-width="2.2"/><line x1="690" y1="15" x2="690" y2="155" stroke="rgba(255,255,255,0.42)" stroke-width="2.2"/>  <line x1="70" y1="45" x2="70" y2="125" stroke="rgba(255,255,255,0.42)" stroke-width="2.2"/><line x1="730" y1="45" x2="730" y2="125" stroke="rgba(255,255,255,0.42)" stroke-width="2.2"/>  <line x1="40" y1="50" x2="110" y2="50" stroke="rgba(255,255,255,0.42)" stroke-width="2.2"/><line x1="40" y1="120" x2="110" y2="120" stroke="rgba(255,255,255,0.42)" stroke-width="2.2"/>  <line x1="690" y1="50" x2="760" y2="50" stroke="rgba(255,255,255,0.42)" stroke-width="2.2"/><line x1="690" y1="120" x2="760" y2="120" stroke="rgba(255,255,255,0.42)" stroke-width="2.2"/>  <circle cx="70" cy="75" r="3.2" fill="#f5efe6" opacity="0.85"/><circle cx="70" cy="85" r="3.2" fill="#f5efe6" opacity="0.85"/><circle cx="70" cy="95" r="3.2" fill="#f5efe6" opacity="0.85"/><circle cx="730" cy="75" r="3.2" fill="#f5efe6" opacity="0.85"/><circle cx="730" cy="85" r="3.2" fill="#f5efe6" opacity="0.85"/><circle cx="730" cy="95" r="3.2" fill="#f5efe6" opacity="0.85"/>@@MANHATTAN@@</svg><h1 class="cs-lockup"><span class="sr-only">cricstat</span><span class="cs" aria-hidden="true">cr<span class="i-ball">ı<svg class="i-dot" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><defs><radialGradient id="emBall" cx="35%" cy="32%" r="70%"><stop offset="0" stop-color="#e2544b"/><stop offset=".65" stop-color="#b3201c"/><stop offset="1" stop-color="#6e1210"/></radialGradient></defs><circle cx="10" cy="10" r="9" fill="url(#emBall)"/><path d="M5.5 3.2c2.6 2.4 3.4 8.4 1.3 13.6M14.5 3.2c-2.6 2.4-3.4 8.4-1.3 13.6" stroke="#f5efe6" stroke-width="1.3" fill="none" stroke-linecap="round"/></svg></span>c<b>stat</b></span></h1></div>
    <p class="pitch-cap tiny">Behind <b>stat</b>: runs per over in India's chase of 275 in the 2011 World Cup final (Cricsheet). The last bar holds the six.</p>
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
    <div class="field"><label for="follow">Follow a team</label>
      <div class="row follow-pick"><div class="radio-pill" role="radiogroup" aria-label="Men's or women's team">
        <label><input type="radio" name="fgender" value="male" checked><span>Men</span></label>
        <label><input type="radio" name="fgender" value="female"><span>Women</span></label>
      </div><select id="follow" autocomplete="off"><option value="india-men">India</option></select></div>
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
HUB = HUB.replace("@@MANHATTAN@@", manhattan_svg())
if PREDICTOR_LIVE:   # the teaser answers its own question (hub.js fills #wc-answer from the live forecast)
    HUB = (HUB.replace('<a class="wc-tease" href="#about" data-about="predictor">', '<a class="wc-tease" href="/cricket/predictor/" id="wc-tease">', 1)
           .replace("</svg> What are the chances of India lifting the 2027 ODI World Cup?</span>",
                    '</svg> <span id="wc-qtext">What are the chances of India lifting the 2027 ODI World Cup?</span></span>\n'
                    '      <span class="wc-a" id="wc-answer" aria-live="polite"></span>', 1)
           .replace("Three models — Elo ratings (statistics), machine learning and deep learning — are about to compete to answer that",
                    "Today: cricstat Elo and 50,000 simulated tournaments. Machine-learning and deep-learning challengers are coming", 1))
    assert 'id="wc-answer"' in HUB and 'id="wc-tease"' in HUB, "hub teaser markers moved"
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
    <div class="wc-head p-intro" id="p-intro">@@PSEAL@@
     <div class="wc-head-text"><h1 class="wc-title" style="font-size:clamp(2rem,4.4vw,3rem);margin:0">Every player, every ball</h1>
      <p class="subtitle" style="margin-top:.6rem">Careers built ball by ball for men and women in Tests, ODIs, T20Is and the big leagues: batting, bowling and fielding by format, year, phase and opponent. Search any name, surname or initials.</p></div>
     <figure class="wc-hosts-fig p-countfig"><div class="p-count"><b id="p-count" class="sb">—</b><span>players</span><small id="p-count-sub">men &amp; women · since 2001</small></div><figcaption>in our data, updated daily</figcaption></figure>
    </div>
    <form class="search-bar" id="p-form" action="/cricket/players/" method="get" role="search">
      <input id="p-search" name="q" type="search" placeholder="Name, surname or initials — e.g. Kohli, S Mandhana" aria-label="Search players" autocomplete="off" minlength="2" required>
      <button class="btn pri" type="submit">Search</button>
    </form>
    <div id="p-results" aria-live="polite" style="margin-top:1rem"></div>
  </div>
</header>
<div id="p-profile" aria-live="polite"></div>
'''
from gen_wc_badges import players_seal  # noqa: E402
PLAYERS = PLAYERS.replace("@@PSEAL@@", players_seal())
page("players/index.html", "/cricket/players/", "Player statistics — cricstat | pandyaHomeLab",
     "Career, year-by-year, phase and opponent statistics for men's and women's cricketers: Tests, ODIs, T20Is and major leagues, from Cricsheet ball-by-ball data.",
     "players", PLAYERS, ["/vendor/chart.js-4.4.0/chart.umd.min.js", "/cricket/assets/players.js?v=" + V])

# The Countries landing (/cricket/countries/): the cricket world map. Team pages (/cricket/countries/<slug>/) use
# the same shell: static = landing (map visible, team header hidden); the API's /pages/countries/<slug>/ swaps
# them (pages.py) and countries.js does the same in the browser.
MAP_BOARD = '''<div id="c-landing" data-model="@@MODEL@@">
<header class="hero left"><div class="wrap">
  <div class="eyebrow"><span class="dot"></span>Countries</div>
  <div class="wc-head">@@CSEAL@@
   <div class="wc-head-text"><h1 class="wc-title" style="font-size:clamp(2rem,4.4vw,3rem);margin:0">Cricket around the world</h1>
    <p class="subtitle" style="margin-top:.6rem">@@CSUB@@</p></div>
   <figure class="wc-hosts-fig"><div class="p-count"><b id="c-count" class="sb">—</b><span>cricket nations</span><small id="c-count-sub">men &amp; women · internationals</small></div><figcaption>on the map, updated daily</figcaption></figure>
  </div>
</div></header>
<section class="section panel" aria-label="Cricket world map"><div class="wrap scoreboard wm-board">
  <div class="sb-head board-head" aria-hidden="true"><span class="bulb"></span>Cricket world map<span class="bulb"></span></div>
  <div id="wm-controls" class="wm-controls"></div>
  <div class="wm-grid">
    <div><div id="wm-map" class="wm-map"><p class="muted" style="padding:1rem;margin:0">Loading the map…</p></div><div id="wm-legend" class="wm-legend"></div></div>
    <aside id="wm-panel" class="card wm-panel" aria-live="polite"><p class="muted">Pick a team on the map.</p></aside>
  </div>
  <p class="tiny muted" style="margin-top:.8rem">Borders: Natural Earth (public domain), drawn as India officially shows them. Cricket splits the UK (England with Wales, Scotland), Ireland is one all-island team and the West Indies cover the Caribbean board's members. Tiny members (Bermuda, Jersey, Singapore…) are dots. @@AFG_MAP@@</p>
</div></section>
</div>
'''
from gen_wc_badges import countries_seal  # noqa: E402
MAP_BOARD = MAP_BOARD.replace("@@CSEAL@@", countries_seal()).replace("@@CSUB@@",
    "Every international team in our data on one map. Colour it by " + ("cricstat Elo (our own ODI rating), ODI World Cup 2027 chances, " if PREDICTOR_LIVE else "")
    + "recent win % or matches played, then pick a team for its record and latest form.")
MAP_BOARD = (MAP_BOARD.replace("@@MODEL@@", "on" if PREDICTOR_LIVE else "off")
             .replace("@@AFG_MAP@@", "Afghanistan men's matches are withheld by Cricsheet; their rating comes from our reviewed results list."
                      if PREDICTOR_LIVE else "Afghanistan men's matches are withheld by Cricsheet, so they are not on the men's map."))
COUNTRIES = '''<header class="hero left" id="c-hero" hidden>
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
page("countries/index.html", "/cricket/countries/", "Cricket world map and team records — cricstat | pandyaHomeLab",
     "A world map of international cricket — every men's and women's team coloured by ODI rating, ODI World Cup 2027 chances, recent win % or matches — and each team's records, results, head to head and top players.",
     "countries", MAP_BOARD + COUNTRIES, ["/vendor/chart.js-4.4.0/chart.umd.min.js", "/cricket/assets/worldmap.js?v=" + V,
                                          "/cricket/assets/countries.js?v=" + V])

PREDICTOR = '''<header class="hero left wc-hero">
  <div class="wrap wc-hero-grid">
   <div class="wc-hero-main">
    <div class="wc-head">@@SEAL@@
     <div class="wc-head-text"><div class="eyebrow"><span class="dot"></span>ODI World Cup 2027 · South Africa, Zimbabwe &amp; Namibia · 2 Oct – 21 Nov 2027</div>
    <h1 class="wc-title" style="font-size:clamp(2rem,4.4vw,3rem)">Who will lift the 2027 ODI World&nbsp;Cup?</h1></div>
     <figure class="wc-hosts-fig">@@HOSTS@@<figcaption>12 grounds · 3 hosts</figcaption></figure>
    </div>
    <p class="subtitle">Every team's chances, from Elo ratings and 50,000 simulated tournaments in the published format. One model for every team: following a team changes what you see first, never the numbers.</p>
    <p class="wc-answer" id="wc-answer"></p>
    <p class="wc-stamp tiny muted" id="wc-stamp">Loading the latest forecast…</p>
    <div id="wc-follow" class="wc-follow" aria-live="polite"></div>
    <p class="wc-caveats tiny">Our model, not a tip · it doesn't know squads, injuries or pitches yet · Afghanistan's results come from a reviewed list · <a href="#wc-limits">Strengths &amp; limits ↓</a></p>
   </div>
   <figure class="wc-donut" id="wc-donut" aria-label="Share of simulated tournaments won, by team"></figure>
  </div>
</header>
<section class="section panel" aria-label="ODI World Cup 2027 forecast"><div class="wrap scoreboard wc-board" id="wc-board">
  <!-- Top-level tabs on the board's title bar: the forecast board, Strengths & limits, The forecast in words.
       #wc-seo keeps its exact opening tag: the API fills it wherever it sits (pages.predictor_page). -->
  <div class="board-head wc-top-tabs" role="tablist" aria-label="Predictor">
    <button class="top-tab" type="button" role="tab" id="top-board" aria-controls="top-pane-board" aria-selected="true"><span class="bulb" aria-hidden="true"></span>ODI World Cup 2027<span class="mc-asof" id="wc-asof"></span></button>
    <button class="top-tab" type="button" role="tab" id="top-limits" aria-controls="top-pane-limits" aria-selected="false" tabindex="-1">⚖️ Strengths &amp; limits</button>
    <button class="top-tab" type="button" role="tab" id="top-words" aria-controls="top-pane-words" aria-selected="false" tabindex="-1">📝 The forecast in words</button>
  </div>
  <div role="tabpanel" id="top-pane-board" aria-labelledby="top-board">
  <div class="sec-tabs" role="tablist" aria-label="Forecast sections">
    <button class="sec-tab" type="button" role="tab" id="tab-odds" aria-controls="pane-odds" aria-selected="true">🏆 Title odds</button>
    <button class="sec-tab" type="button" role="tab" id="tab-time" aria-controls="pane-time" aria-selected="false" tabindex="-1">📈 Odds over time</button>
    <button class="sec-tab" type="button" role="tab" id="tab-fixtures" aria-controls="pane-fixtures" aria-selected="false" tabindex="-1">📅 Fixtures</button>
    <button class="sec-tab" type="button" role="tab" id="tab-venues" aria-controls="pane-venues" aria-selected="false" tabindex="-1">🏟️ Venues</button>
    <button class="sec-tab" type="button" role="tab" id="tab-ratings" aria-controls="pane-ratings" aria-selected="false" tabindex="-1">⚖️ Ratings</button>
    <button class="sec-tab" type="button" role="tab" id="tab-format" aria-controls="pane-format" aria-selected="false" tabindex="-1">🗺️ Format</button>
    <button class="sec-tab" type="button" role="tab" id="tab-good" aria-controls="pane-good" aria-selected="false" tabindex="-1">✅ How good is it?</button>
  </div>
  <div class="sec-pane" role="tabpanel" id="pane-odds" aria-labelledby="tab-odds"><div class="skeleton"></div></div>
  <div class="sec-pane" role="tabpanel" id="pane-time" aria-labelledby="tab-time" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-fixtures" aria-labelledby="tab-fixtures" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-venues" aria-labelledby="tab-venues" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-ratings" aria-labelledby="tab-ratings" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-format" aria-labelledby="tab-format" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-good" aria-labelledby="tab-good" hidden></div>
  </div>
  <div role="tabpanel" id="top-pane-limits" aria-labelledby="top-limits" hidden><div class="wrap wc-limits" id="wc-limits"></div></div>
  <div role="tabpanel" id="top-pane-words" aria-labelledby="top-words" hidden><div class="wrap wc-seo" id="wc-seo">
  <div class="section-label">The forecast in words</div>
  <h2 class="section-title">Who will win the 2027 Cricket World Cup?</h2>
  <p>cricstat's model rates every team with cricstat Elo, its own rating built from every men's ODI since 2002 (not the ICC ranking), then plays the 2027 tournament in South Africa, Zimbabwe and Namibia 50,000 times. Each team's title chance is the share of those runs it wins; the forecast updates daily as teams play. <a href="/cricket/methodology/">How it works</a>.</p>
</div></div>
</div></section>
'''
# Our own marks (tools/gen_wc_badges.py): a seal and the hosts' map; the official logo is non-free (ICC trademark).
from gen_wc_badges import hosts as wc_hosts, seal as wc_seal  # noqa: E402
PREDICTOR = PREDICTOR.replace("@@SEAL@@", wc_seal()).replace("@@HOSTS@@", wc_hosts())
PRED_DESC = ("Who will win the 2027 Cricket World Cup? Every team's chances from cricstat Elo and 50,000 simulated "
             "tournaments, updated daily, with backtests on the 2019 and 2023 World Cups.")
if PREDICTOR_LIVE:
  page("predictor/index.html", "/cricket/predictor/",
       "Cricket World Cup 2027 Prediction: Who Will Win? | cricstat", PRED_DESC, "predictor", PREDICTOR,
       ["/vendor/chart.js-4.4.0/chart.umd.min.js", "/cricket/assets/predictor.js?v=" + V],
       og_image=SITE + "/cricket/og/predictor.png",
       extra_head=ld_json({"@context": "https://schema.org", "@type": "WebPage", "name": "ODI World Cup 2027 predictor",
                           "description": PRED_DESC, "url": SITE + "/cricket/predictor/", "isPartOf": {"@id": SITE + "/#site"},
                           "about": ["ODI World Cup 2027", "Elo rating", "Monte Carlo simulation"], "author": ARCHIT}))

METHOD = '''<header class="hero left"><div class="wrap">
  <div class="eyebrow"><span class="dot"></span>Methodology · ODI World Cup 2027 predictor</div>
  <div class="wc-head">@@MSEAL@@
   <div class="wc-head-text"><h1 class="wc-title" style="font-size:clamp(2rem,4.4vw,3rem);margin:0">How the predictor works — and how well</h1>
  <p class="subtitle" style="margin-top:.6rem">The model in plain words and in formulas, every setting and how it was chosen, and the tests it had to pass
  on matches it had never seen. One model for every team; every number below comes from the same files the forecast uses.</p></div>
   <figure class="wc-hosts-fig m-calfig"><svg class="m-calmini" id="m-calmini" viewBox="0 0 120 120" role="img" aria-label="Calibration: predicted against observed win rate (loading)"></svg><figcaption id="m-calcap">said vs happened</figcaption></figure>
  </div>
  <p class="tiny muted" id="m-stamp">Loading…</p>
</div></header>
<section class="section panel" aria-label="Methodology"><div class="wrap scoreboard m-board">
  <div class="sb-head board-head" aria-hidden="true"><span class="bulb"></span>Methodology<span class="mc-asof" id="m-asof"></span><span class="bulb"></span></div>
  <div class="sec-tabs" role="tablist" aria-label="Methodology sections">
    <button class="sec-tab" type="button" role="tab" id="tab-m-plain" aria-controls="pane-m-plain" aria-selected="true">🧭 In plain words</button>
    <button class="sec-tab" type="button" role="tab" id="tab-m-elo" aria-controls="pane-m-elo" aria-selected="false" tabindex="-1">📐 Ratings</button>
    <button class="sec-tab" type="button" role="tab" id="tab-m-sim" aria-controls="pane-m-sim" aria-selected="false" tabindex="-1">🎲 Simulation</button>
    <button class="sec-tab" type="button" role="tab" id="tab-m-tests" aria-controls="pane-m-tests" aria-selected="false" tabindex="-1">✅ Backtests</button>
    <button class="sec-tab" type="button" role="tab" id="tab-m-cal" aria-controls="pane-m-cal" aria-selected="false" tabindex="-1">🎯 Calibration</button>
    <button class="sec-tab" type="button" role="tab" id="tab-m-models" aria-controls="pane-m-models" aria-selected="false" tabindex="-1">🏁 Models &amp; versions</button>
    <button class="sec-tab" type="button" role="tab" id="tab-m-limits" aria-controls="pane-m-limits" aria-selected="false" tabindex="-1">⚠️ Limits</button>
  </div>
  <div class="sec-pane" role="tabpanel" id="pane-m-plain" aria-labelledby="tab-m-plain"><div class="skeleton"></div></div>
  <div class="sec-pane" role="tabpanel" id="pane-m-elo" aria-labelledby="tab-m-elo" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-m-sim" aria-labelledby="tab-m-sim" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-m-tests" aria-labelledby="tab-m-tests" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-m-cal" aria-labelledby="tab-m-cal" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-m-models" aria-labelledby="tab-m-models" hidden></div>
  <div class="sec-pane" role="tabpanel" id="pane-m-limits" aria-labelledby="tab-m-limits" hidden></div>
</div></section>
'''
from gen_wc_badges import method_seal  # noqa: E402
METHOD = METHOD.replace("@@MSEAL@@", method_seal())
METHOD_DESC = ("How cricstat's ODI World Cup 2027 predictor works: Elo ratings from every men's ODI, 50,000 simulated "
               "tournaments, and backtests on the 2019 and 2023 World Cups with calibration, baselines and model versions.")
if PREDICTOR_LIVE:
    page("methodology/index.html", "/cricket/methodology/",
         "Methodology: how the ODI World Cup 2027 predictor works and how well — cricstat | pandyaHomeLab", METHOD_DESC,
         "method", METHOD, ["/vendor/chart.js-4.4.0/chart.umd.min.js", "/cricket/assets/methodology.js?v=" + V],
         extra_head=ld_json({"@context": "https://schema.org", "@type": "TechArticle", "headline": "How the ODI World Cup 2027 predictor works",
                             "description": METHOD_DESC, "url": SITE + "/cricket/methodology/", "isPartOf": {"@id": SITE + "/#site"},
                             "about": ["Elo rating", "Monte Carlo simulation", "Calibration", "Backtesting"], "author": ARCHIT}))

LIC = '''<header class="hero left"><div class="wrap">
  <div class="eyebrow"><span class="dot"></span>Data &amp; licences</div>
  <h1 style="font-size:clamp(2rem,5vw,3rem)">Where the numbers come from</h1>
  <p class="subtitle">Open data, credited; what it covers and what it doesn't; and how your privacy is kept.</p>
</div></header>
<section class="section" style="padding-top:0"><div class="wrap stack" style="max-width:940px">
  <div class="card accent">
    <h2>Attribution</h2>
    <p class="dim">Match data from Cricsheet (<a href="https://cricsheet.org/">cricsheet.org</a>), used under the <a href="https://opendatacommons.org/licenses/by/1-0/">Open Data Commons Attribution License 1.0</a>.</p>
    <p class="dim" style="margin-top:.6rem"><span class="cs"><i class="cs-sr">cricstat</i><i class="cs-w" aria-hidden="true">cr<i class="cs-i">ı</i>c<b>stat</b></i></span> is an independent, non-commercial project. It is not affiliated with or endorsed by Cricsheet, the ICC or any cricket board, and uses no board or team logos.</p>
  </div>
  <div class="card tablecard">
    <div class="card-head"><h2>Sources</h2></div>
    <div class="scroll"><table>
      <thead><tr><th scope="col" class="txt">Source</th><th scope="col" class="txt">Used for</th><th scope="col" class="txt">Licence</th></tr></thead>
      <tbody>
        <tr><td class="txt">Cricsheet match data</td><td class="txt">Ball-by-ball data for every match on these pages (men's and women's, 2001–present)</td><td class="txt">ODC-BY 1.0 · attribution required</td></tr>
        <tr><td class="txt">Cricsheet Register</td><td class="txt">Player identities and name variants used for search</td><td class="txt">ODC-BY 1.0 · attribution required</td></tr>
        <tr><td class="txt">Wikidata</td><td class="txt">Players' full names, dates and places of birth, matched only by their ESPNcricinfo id (never by name)</td><td class="txt">CC0 · no attribution required, credited anyway</td></tr>
        <tr><td class="txt">Wikimedia Commons</td><td class="txt">Player photos: a small copy of each image, served from this site, with its author, licence and file page shown next to it</td><td class="txt">Public domain, CC0, CC BY, CC BY-SA or GODL-India, per photo</td></tr>
        <tr><td class="txt">Wikimedia Commons</td><td class="txt">National flags, used unaltered at their official proportions and only to identify national teams (<a href="#flag-sources">source of each flag</a>)</td><td class="txt">Public domain (or CC0)</td></tr>
        <tr><td class="txt">Wikipedia</td><td class="txt">For the ODI World Cup 2027 predictor: Afghanistan men's ODI results (results only, each checked against a second Wikipedia source and reviewed; Cricsheet withholds these matches), and the 2027 World Cup's format, schedule, start times and venue capacities. Facts only; no Wikipedia text is reproduced</td><td class="txt">CC BY-SA 4.0 · <a href="https://en.wikipedia.org/wiki/2027_Cricket_World_Cup">2027 Cricket World Cup</a>, <a href="https://en.wikipedia.org/wiki/Afghanistan_national_cricket_team">Afghanistan national cricket team</a>, and the yearly "International cricket in …" pages</td></tr>
        <tr><td class="txt">Wikimedia Commons</td><td class="txt">Photos of the 2027 World Cup grounds (and one from Flickr), served from this site, each credited on the predictor page (<a href="#venue-photos">source of each photo</a>)</td><td class="txt">Public domain (incl. the Public Domain Mark), CC BY or CC BY-SA, per photo</td></tr>
        <tr><td class="txt">Natural Earth</td><td class="txt">Country shapes for the cricket world map (1:10m, with borders as India officially shows them), simplified and served from this site</td><td class="txt">Public domain · <a href="https://www.naturalearthdata.com/about/terms-of-use/">terms of use</a></td></tr>
        <tr><td class="txt">Chart.js</td><td class="txt">Charts, served from this site (<a href="/vendor/chart.js-4.4.0/LICENSE">licence text</a>)</td><td class="txt">MIT</td></tr>
      </tbody>
    </table></div>
    <p class="tiny muted" style="padding:0 1.3rem 1.1rem">Photos are resized copies of the Commons originals and are not otherwise changed (the profile frame only crops what is shown). Photos under the Government Open Data License – India (GODL-India, mostly from the Press Information Bureau) are credited as it requires and imply no endorsement by the Government of India. Players under 18 are shown without a photo or birth details. Published figures from public records, including Wikipedia, are used privately to cross-check our numbers and are not reproduced here.</p>
    <details class="flag-sources" id="venue-photos"><summary>Source of each venue photo (@@NVENUES@@)</summary>
      <p class="tiny muted">Resized copies of the Wikimedia Commons or Flickr files linked here, not otherwise changed. Chosen and checked by hand; grounds without a freely licensed photo show none.</p>
      <ul>@@VENUES@@</ul>
    </details>
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
      <li>Afghanistan men's matches are not included by the data source (Cricsheet withholds them as a protest over Afghan women's cricket), so players' totals against Afghanistan are missing. For the ODI World Cup 2027 predictor only, Afghanistan's results come from a reviewed list (see Wikipedia above), so the forecast stays fair to every team.</li>
      <li>Statistics are derived from ball-by-ball records and can differ from official figures. Averages and rates are shown cut to two decimals, as published records show them.</li>
    </ul>
  </div>
  <div class="grid">
    <div class="card"><h2>Privacy</h2><p class="dim">No cookies, and nothing is loaded from third parties. The team you follow is remembered in your browser only (local storage) and never sent to the server. Visits are counted the same way as on the rest of this site.</p><p style="margin-top:.6rem"><a href="/privacy/">Full privacy page →</a></p></div>
    <div class="card"><h2>Disclaimers</h2><p class="dim">Statistics are derived from the source data and may differ from official records. Forecasts (the ODI World Cup 2027 predictor) are statistical estimates for education and entertainment, not tips and not betting advice. When the AI analyst arrives, every answer will show how it was computed.</p></div>
    <div class="card"><h2>Corrections</h2><p class="dim">Spotted an error, or want details about a player reviewed or a photo removed? Email <a href="mailto:privacy@pandyahomelab.com">privacy@pandyahomelab.com</a> with the page and what looks wrong.</p></div>
  </div>
</div></section>
'''
PRED_LIC_ROWS = [l for l in LIC.split("\n") if "For the ODI World Cup 2027 predictor:" in l or "Photos of the 2027 World Cup grounds" in l]
if not PREDICTOR_LIVE:            # until the predictor page is public, the licences page doesn't describe it
    for l in PRED_LIC_ROWS:
        LIC = LIC.replace(l + "\n", "")
    LIC = LIC[:LIC.index('    <details class="flag-sources" id="venue-photos">')] + LIC[LIC.index("    </details>\n", LIC.index('id="venue-photos"')) + len("    </details>\n"):]
    LIC = LIC.replace(" For the ODI World Cup 2027 predictor only, Afghanistan's results come from a reviewed list (see Wikipedia above), so the forecast stays fair to every team.", "")
    LIC = LIC.replace("Forecasts (the ODI World Cup 2027 predictor) are statistical estimates for education and entertainment, not tips and not betting advice. When the AI analyst arrives, every answer will show how it was computed.",
                      "When forecasts and the AI analyst arrive, forecasts will be for education and entertainment, not betting advice, and every AI answer will show how it was computed.")


def flag_sources():
    """The licences page lists each flag's Commons page (from flags.js, written by fetch_flags.py)."""
    with open(os.path.join(WEB, "assets", "flags.js"), encoding="utf-8") as f:
        src = f.read()
    flags = json.loads(src[src.index("{"):src.rindex("}") + 1])
    items = "".join('<li><a href="%s">%s</a> · %s</li>' % (H.escape(f["source"]), H.escape(n), H.escape(f["licence"]))
                    for n, f in sorted(flags.items()))
    vpath = os.path.join(CRICSTAT, "cricstat-models", "tournaments", "wc2027", "venues.csv")
    with open(vpath, encoding="utf-8", newline="") as f:
        venues = [r for r in csv.DictReader(f) if r.get("photo")]
    vitems = "".join('<li><a href="%s">%s</a> · %s · %s</li>' % (
        H.escape(v["photo_source"]), H.escape(v["stadium"]), H.escape(v["photo_author"] or "unknown author"),
        H.escape(v["photo_licence"])) for v in venues)
    return (LIC.replace("@@NFLAGS@@", str(len(flags))).replace("@@FLAGS@@", items)
            .replace("@@NVENUES@@", str(len(venues))).replace("@@VENUES@@", vitems))


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
            '  <h1 style="font-size:clamp(2rem,5vw,3rem)">How I built <span class="cs"><i class="cs-sr">cricstat</i><i class="cs-w" aria-hidden="true">cr<i class="cs-i">ı</i>c<b>stat</b></i></span></h1>\n'
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
