"""Our own ODI World Cup 2027 marks for the predictor hero (the official logo is non-free and an ICC
trademark, so it is never used). Two options for the owner to compare:

  wc-seal.svg   a round seal: our gold trophy, "2027", "ODI WORLD CUP 2027 · FORECAST" and the hosts
  wc-hosts.svg  southern Africa with the three host countries and the 12 grounds as dots
                (shapes: assets/world-map.json, Natural Earth, public domain; ground positions are
                approximate city coordinates)

    python3 cricstat/tools/gen_wc_badges.py      # writes staging/web/assets/ + staging/web/badge-options/
"""
import csv
import html as H
import json
import os

from fetch_world_map import to_px

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "staging", "web")
VENUES = os.path.join(HERE, "..", "cricstat-models", "tournaments", "wc2027", "venues.csv")
# City coordinates (lat, lon), approximate: enough for a dot on a small map.
CITY = {"Johannesburg": (-26.13, 28.06), "Cape Town": (-33.97, 18.47), "Durban": (-29.85, 31.03),
        "Centurion": (-25.79, 28.25), "Bloemfontein": (-29.12, 26.21), "Gqeberha": (-33.96, 25.61),
        "KuGompo City": (-33.00, 27.90), "Paarl": (-33.73, 18.97), "Harare": (-17.81, 31.05),
        "Bulawayo": (-20.15, 28.58), "Victoria Falls": (-17.93, 25.83), "Windhoek": (-22.57, 17.08)}
HOSTS = {"ZAF", "ZWE", "NAM"}
NEIGHBOURS = {"BWA", "LSO", "SWZ", "MOZ", "ZMB", "AGO", "MWI"}
GOLD = '<linearGradient id="%s" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFE38A"/>' \
       '<stop offset=".5" stop-color="#F5B82E"/><stop offset="1" stop-color="#C98500"/></linearGradient>'


# Centre of the Players seal (pictograms, thick round strokes). Owner tried both on 2026-10-10;
# switch back by setting PLAYERS_FIGURE = "batter".
PLAYERS_FIGURE = "bowler"
PLAYER_FIGURES = {
    "batter": '<g fill="none" stroke="url(#pGold)" stroke-linecap="round" stroke-linejoin="round"><polyline points="101.4,69.0 112.4,95.2" stroke-width="15.2"/><polyline points="112.4,95.2 95.9,111.7 87.6,131.1" stroke-width="11.0"/><polyline points="112.4,95.2 126.2,113.1 137.3,129.7" stroke-width="11.0"/><polyline points="101.4,71.7 89.0,86.9" stroke-width="8.3"/><polyline points="104.1,74.5 93.1,89.7" stroke-width="8.3"/></g><circle cx="94.5" cy="55.2" r="10.3" fill="url(#pGold)"/><line x1="80.0" y1="56.5" x2="91.7" y2="56.5" stroke="url(#pGold)" stroke-width="4.1"/><line x1="91.7" y1="86.9" x2="89.0" y2="95.2" stroke="#e2e8f0" stroke-width="4.1" stroke-linecap="round"/><line x1="89.0" y1="95.2" x2="72.4" y2="125.5" stroke="#e8d3a0" stroke-width="11"/><circle cx="60.0" cy="131.1" r="6.2" fill="url(#pBall)"/>',   # a batter playing a drive
    "bowler": '<g fill="none" stroke="url(#pGold)" stroke-linecap="round" stroke-linejoin="round"><polyline points="92.8,85.0 102.4,107.8" stroke-width="13.2"/><polyline points="102.4,107.8 92.8,122.2 85.6,135.4" stroke-width="9.6"/><polyline points="102.4,107.8 116.8,117.4 128.8,121.0" stroke-width="9.6"/><polyline points="96.4,85.0 106.0,69.4 112.0,56.2" stroke-width="7.2"/><polyline points="91.6,87.4 80.8,93.4 72.4,101.8" stroke-width="7.2"/></g><circle cx="87.4" cy="74.8" r="9.0" fill="url(#pGold)"/><circle cx="114.4" cy="51.4" r="5.5" fill="url(#pBall)"/>',   # a bowler in delivery stride
}


def trophy(gid, x, y, s):
    """Our trophy (same shape family as the hub teaser's icon), drawn in a 64-unit box at (x, y), scale s."""
    return ('<g transform="translate(%.1f %.1f) scale(%.3f)" fill="url(#%s)">'
            '<path d="M18 8h28v14c0 9-6 16-14 16s-14-7-14-16z"/>'
            '<path d="M18 12H10c0 9 4 14 10 15M46 12h8c0 9-4 14-10 15" fill="none" stroke="url(#%s)" stroke-width="3.5"/>'
            '<rect x="29" y="37" width="6" height="9" rx="1"/><path d="M21 52c0-4 5-6 11-6s11 2 11 6v3H21z"/>'
            '<rect x="18" y="55" width="28" height="4" rx="1.5"/>'
            '<path d="M26 14c1 7 3 12 7 15" fill="none" stroke="#fff" stroke-opacity=".45" stroke-width="2" stroke-linecap="round"/>'
            '</g>') % (x, y, s, gid, gid)


def seal():
    return ('<svg class="wc-seal" viewBox="0 0 200 200" role="img" aria-label="ODI World Cup 2027 forecast by cricstat">'
            '<defs>' + GOLD % "sealGold" +
            '<path id="sealTop" d="M30 100a70 70 0 0 1 140 0"/><path id="sealBot" d="M24 100a76 76 0 0 0 152 0"/></defs>'
            '<circle cx="100" cy="100" r="96" fill="#13161e" stroke="url(#sealGold)" stroke-width="3"/>'
            '<circle cx="100" cy="100" r="86" fill="none" stroke="#F5B82E" stroke-opacity=".35" stroke-width="1"/>'
            '<circle cx="100" cy="100" r="58" fill="none" stroke="#F5B82E" stroke-opacity=".35" stroke-width="1"/>'
            '<text font-family="system-ui, sans-serif" font-weight="800" font-size="12.5" letter-spacing="2.2" fill="#F5B82E">'
            '<textPath href="#sealTop" startOffset="50%" text-anchor="middle">ODI WORLD CUP · FORECAST</textPath></text>'
            '<text font-family="system-ui, sans-serif" font-weight="700" font-size="9.5" letter-spacing="1.6" fill="#cbd5e1">'
            '<textPath href="#sealBot" startOffset="50%" text-anchor="middle">SOUTH AFRICA · ZIMBABWE · NAMIBIA</textPath></text>'
            '<circle cx="31" cy="100" r="2.4" fill="#FF9933"/><circle cx="169" cy="100" r="2.4" fill="#FF9933"/>'
            + trophy("sealGold", 74, 52, 0.82) +
            '<text x="100" y="133" text-anchor="middle" font-family="system-ui, sans-serif" font-weight="900" font-size="25" '
            'letter-spacing="1" fill="url(#sealGold)">2027</text>'
            '<text x="100" y="146" text-anchor="middle" font-family="system-ui, sans-serif" font-weight="700" font-size="7.5" '
            'letter-spacing="1.5" fill="#94a3b8">cric<tspan fill="#FF9933">stat</tspan></text>'
            '</svg>')


def method_seal():
    """Methodology hero: the same seal family, a balance scale (Elo weighs one team against another)."""
    return ('<svg class="wc-seal" viewBox="0 0 200 200" role="img" aria-label="Methodology of the cricstat predictor">'
            '<defs>' + GOLD % "mGold" +
            '<path id="mTop" d="M30 100a70 70 0 0 1 140 0"/><path id="mBot" d="M24 100a76 76 0 0 0 152 0"/></defs>'
            '<circle cx="100" cy="100" r="96" fill="#13161e" stroke="url(#mGold)" stroke-width="3"/>'
            '<circle cx="100" cy="100" r="86" fill="none" stroke="#F5B82E" stroke-opacity=".35" stroke-width="1"/>'
            '<circle cx="100" cy="100" r="58" fill="none" stroke="#F5B82E" stroke-opacity=".35" stroke-width="1"/>'
            '<text font-family="system-ui, sans-serif" font-weight="800" font-size="12.5" letter-spacing="2.2" fill="#F5B82E">'
            '<textPath href="#mTop" startOffset="50%" text-anchor="middle">HOW IT WORKS · METHODOLOGY</textPath></text>'
            '<text font-family="system-ui, sans-serif" font-weight="700" font-size="9" letter-spacing="1.4" fill="#cbd5e1">'
            '<textPath href="#mBot" startOffset="50%" text-anchor="middle">ELO · 50,000 SIMULATIONS · BACKTESTS</textPath></text>'
            '<circle cx="31" cy="100" r="2.4" fill="#FF9933"/><circle cx="169" cy="100" r="2.4" fill="#FF9933"/>'
            # balance scale: post, beam tilted slightly, two pans; a red ball on the lower pan
            '<g fill="none" stroke="url(#mGold)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M100 66v52M86 121h28"/><path d="M70 82l60-6"/>'
            '<path d="M70 82l-11 22M70 82l11 22M130 76l-11 22M130 76l11 22"/>'
            '<path d="M56 104q14 10 28 0M116 98q14 10 28 0"/></g>'
            '<circle cx="100" cy="64" r="3.6" fill="url(#mGold)"/>'
            '<circle cx="70" cy="99" r="5.2" fill="#b3201c"/><path d="M67.4 95.6c1.2 1.1 1.6 3.9.6 6.2M72.6 95.6c-1.2 1.1-1.6 3.9-.6 6.2" stroke="#f5efe6" stroke-width=".8" fill="none"/>'
            '<text x="100" y="140" text-anchor="middle" font-family="system-ui, sans-serif" font-weight="900" font-size="17" '
            'letter-spacing="1" fill="url(#mGold)">Elo</text>'
            '<text x="100" y="152" text-anchor="middle" font-family="system-ui, sans-serif" font-weight="700" font-size="7.5" '
            'letter-spacing="1.5" fill="#94a3b8">cric<tspan fill="#FF9933">stat</tspan></text>'
            '</svg>')


def players_seal(figure=None):
    """Players page: the same seal family; the centre is a batter or a bowler (PLAYERS_FIGURE)."""
    figure = figure or PLAYERS_FIGURE
    return ('<svg class="wc-seal" viewBox="0 0 200 200" role="img" aria-label="cricstat players">'
            '<defs>' + GOLD % "pGold" +
            '<radialGradient id="pBall" cx="35%" cy="32%" r="70%"><stop offset="0" stop-color="#e2544b"/>'
            '<stop offset=".65" stop-color="#b3201c"/><stop offset="1" stop-color="#6e1210"/></radialGradient>'
            '<path id="pTop" d="M30 100a70 70 0 0 1 140 0"/><path id="pBot" d="M24 100a76 76 0 0 0 152 0"/></defs>'
            '<circle cx="100" cy="100" r="96" fill="#13161e" stroke="url(#pGold)" stroke-width="3"/>'
            '<circle cx="100" cy="100" r="86" fill="none" stroke="#F5B82E" stroke-opacity=".35" stroke-width="1"/>'
            '<circle cx="100" cy="100" r="58" fill="none" stroke="#F5B82E" stroke-opacity=".35" stroke-width="1"/>'
            '<text font-family="system-ui, sans-serif" font-weight="800" font-size="12.5" letter-spacing="2.2" fill="#F5B82E">'
            '<textPath href="#pTop" startOffset="50%" text-anchor="middle">PLAYERS · CAREERS</textPath></text>'
            '<text font-family="system-ui, sans-serif" font-weight="700" font-size="9" letter-spacing="1.4" fill="#cbd5e1">'
            '<textPath href="#pBot" startOffset="50%" text-anchor="middle">MEN &amp; WOMEN · EVERY FORMAT</textPath></text>'
            '<circle cx="31" cy="100" r="2.4" fill="#FF9933"/><circle cx="169" cy="100" r="2.4" fill="#FF9933"/>'
            + PLAYER_FIGURES[figure] +
            '<text x="100" y="146" text-anchor="middle" font-family="system-ui, sans-serif" font-weight="700" font-size="7.5" '
            'letter-spacing="1.5" fill="#94a3b8">cric<tspan fill="#FF9933">stat</tspan></text>'
            '</svg>')


def countries_seal():
    """Countries landing: the same seal family, a globe with a cricket ball."""
    return ('<svg class="wc-seal" viewBox="0 0 200 200" role="img" aria-label="cricstat countries">'
            '<defs>' + GOLD % "cGold" +
            '<radialGradient id="cBall" cx="35%" cy="32%" r="70%"><stop offset="0" stop-color="#e2544b"/>'
            '<stop offset=".65" stop-color="#b3201c"/><stop offset="1" stop-color="#6e1210"/></radialGradient>'
            '<clipPath id="cClip"><circle cx="96" cy="94" r="30"/></clipPath>'
            '<path id="cTop" d="M30 100a70 70 0 0 1 140 0"/><path id="cBot" d="M24 100a76 76 0 0 0 152 0"/></defs>'
            '<circle cx="100" cy="100" r="96" fill="#13161e" stroke="url(#cGold)" stroke-width="3"/>'
            '<circle cx="100" cy="100" r="86" fill="none" stroke="#F5B82E" stroke-opacity=".35" stroke-width="1"/>'
            '<circle cx="100" cy="100" r="58" fill="none" stroke="#F5B82E" stroke-opacity=".35" stroke-width="1"/>'
            '<text font-family="system-ui, sans-serif" font-weight="800" font-size="12.5" letter-spacing="2.2" fill="#F5B82E">'
            '<textPath href="#cTop" startOffset="50%" text-anchor="middle">COUNTRIES · TEAMS</textPath></text>'
            '<text font-family="system-ui, sans-serif" font-weight="700" font-size="9" letter-spacing="1.4" fill="#cbd5e1">'
            '<textPath href="#cBot" startOffset="50%" text-anchor="middle">MEN &amp; WOMEN · EVERY FORMAT</textPath></text>'
            '<circle cx="31" cy="100" r="2.4" fill="#FF9933"/><circle cx="169" cy="100" r="2.4" fill="#FF9933"/>'
            # globe: sea, meridians and parallels in gold, ball resting at its lower right
            '<circle cx="96" cy="94" r="30" fill="#1a2440"/>'
            '<g clip-path="url(#cClip)" fill="none" stroke="url(#cGold)" stroke-width="1.6" opacity=".9">'
            '<ellipse cx="96" cy="94" rx="13" ry="30"/><path d="M96 64v60M66 84h60M66 104h60M70 74h52M70 114h52"/></g>'
            '<circle cx="96" cy="94" r="30" fill="none" stroke="url(#cGold)" stroke-width="3"/>'
            '<circle cx="124" cy="119" r="10" fill="url(#cBall)" stroke="#13161e" stroke-width="2"/>'
            '<path d="M119.2 112.6c2.2 2.1 3 7.3 1.1 11.7M128.8 112.6c-2.2 2.1-3 7.3-1.1 11.7" stroke="#f5efe6" stroke-width="1.2" fill="none" stroke-linecap="round"/>'
            '<text x="100" y="146" text-anchor="middle" font-family="system-ui, sans-serif" font-weight="700" font-size="7.5" '
            'letter-spacing="1.5" fill="#94a3b8">cric<tspan fill="#FF9933">stat</tspan></text>'
            '</svg>')


def hosts():
    with open(os.path.join(WEB, "assets", "world-map.json"), encoding="utf-8") as f:
        world = json.load(f)
    with open(VENUES, encoding="utf-8", newline="") as f:
        venues = list(csv.DictReader(f))
    x0, y0 = to_px(10.5, -15.0)                       # NW corner: west of Namibia, north of Zimbabwe
    x1, y1 = to_px(35.5, -35.5)                       # SE corner: south of the Cape, east of Durban
    w, hgt = x1 - x0, y1 - y0
    parts = ['<svg class="wc-hosts" viewBox="%.1f %.1f %.1f %.1f" role="img" '
             'aria-label="The 2027 hosts South Africa, Zimbabwe and Namibia, with the 12 World Cup grounds">' % (x0, y0, w, hgt)]
    for s in world["shapes"]:
        if s["code"] in HOSTS:
            parts.append('<path class="h-host" d="%s"><title>%s</title></path>' % (s["d"], H.escape(s["name"])))
        elif s["code"] in NEIGHBOURS:
            parts.append('<path class="h-near" d="%s"/>' % s["d"])
    for v in venues:
        lat, lon = CITY[v["city"]]
        x, y = to_px(lon, lat)
        parts.append('<circle class="h-ground" cx="%.2f" cy="%.2f" r=".75"><title>%s, %s</title></circle>'
                     % (x, y, H.escape(v["stadium"]), H.escape(v["city"])))
    parts.append("</svg>")
    return "".join(parts)


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Predictor hero: mark options (preview only)</title><meta name="robots" content="noindex">
<link rel="stylesheet" href="/cricket/assets/cricstat.css"><style>
body {{ padding: 1.5rem 1rem 3rem; }} .opt {{ max-width: 1100px; margin: 0 auto 1.4rem; }}
.opt > h2 {{ color: var(--saffron); font-size: 1rem; margin: 0 0 .5rem; }}
.mock {{ display: flex; gap: 1.6rem; align-items: center; background: radial-gradient(ellipse at top left, rgba(255,153,51,.08), transparent 60%), var(--surface);
        border: 1px solid var(--border); border-radius: 14px; padding: 1.4rem 1.6rem; }}
.mock h1 {{ font-size: clamp(1.6rem, 3.6vw, 2.6rem); margin: .3rem 0 .4rem; line-height: 1.15; }}
.mock p {{ color: var(--dim); margin: 0; max-width: 560px; }}
.wc-seal {{ width: 150px; height: 150px; flex: none; filter: drop-shadow(0 8px 22px rgba(245,184,46,.18)); }}
.wc-hosts {{ width: 210px; height: auto; flex: none; }}
.wc-hosts .h-host {{ fill: #2a3346; stroke: #F5B82E; stroke-width: .25; }}
.wc-hosts .h-near {{ fill: #1b202b; stroke: #10131a; stroke-width: .2; }}
.wc-hosts .h-ground {{ fill: #FF9933; stroke: #13161e; stroke-width: .25; }}
.hosts-cap {{ font-size: .75rem; color: var(--muted); margin-top: .3rem; text-align: center; }}
.icon-old {{ width: 64px; height: 64px; flex: none; }}
@media (max-width: 640px) {{ .mock {{ flex-direction: column; align-items: flex-start; }} }}
</style></head><body>
<div class="opt"><h2>Now — our trophy icon in the title</h2><div class="mock">{trophy_now}
  <div><div class="eyebrow"><span class="dot"></span>ODI World Cup 2027 · 2 Oct – 21 Nov 2027</div><h1>Who will lift the 2027 ODI World&nbsp;Cup?</h1>
  <p>Every team's chances, from Elo ratings and 50,000 simulated tournaments in the published format.</p></div></div></div>
<div class="opt"><h2>Option 2 — our own seal</h2><div class="mock">{seal}
  <div><div class="eyebrow"><span class="dot"></span>ODI World Cup 2027 · 2 Oct – 21 Nov 2027</div><h1>Who will lift the 2027 ODI World&nbsp;Cup?</h1>
  <p>Every team's chances, from Elo ratings and 50,000 simulated tournaments in the published format.</p></div></div></div>
<div class="opt"><h2>Option 3 — the hosts and their 12 grounds</h2><div class="mock"><figure style="margin:0">{hosts}<figcaption class="hosts-cap">12 grounds · 3 hosts</figcaption></figure>
  <div><div class="eyebrow"><span class="dot"></span>ODI World Cup 2027 · South Africa, Zimbabwe &amp; Namibia</div><h1>Who will lift the 2027 ODI World&nbsp;Cup?</h1>
  <p>Every team's chances, from Elo ratings and 50,000 simulated tournaments in the published format.</p></div></div></div>
<div class="opt"><h2>Option 2 + 3 together</h2><div class="mock">{seal2}<div><div class="eyebrow"><span class="dot"></span>ODI World Cup 2027 · 2 Oct – 21 Nov 2027</div>
  <h1>Who will lift the 2027 ODI World&nbsp;Cup?</h1><p>Every team's chances, from Elo ratings and 50,000 simulated tournaments in the published format.</p></div>
  <figure style="margin:0 0 0 auto">{hosts2}<figcaption class="hosts-cap">12 grounds · 3 hosts</figcaption></figure></div></div>
</body></html>"""


def main():
    s, m = seal(), hosts()
    os.makedirs(os.path.join(WEB, "badge-options"), exist_ok=True)
    for name, svg in (("wc-seal.svg", s), ("wc-hosts.svg", m)):
        with open(os.path.join(WEB, "assets", name), "w", encoding="utf-8") as f:
            f.write(svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1))
    now = ('<svg class="icon-old" viewBox="0 0 64 64" aria-hidden="true"><defs>' + GOLD % "nowGold" + "</defs>"
           + trophy("nowGold", 0, 0, 1) + "</svg>")
    with open(os.path.join(WEB, "badge-options", "index.html"), "w", encoding="utf-8") as f:
        f.write(PAGE.format(trophy_now=now, seal=s, hosts=m,
                            seal2=s.replace('id="seal', 'id="s2').replace("#seal", "#s2").replace("url(#s2Gold)", "url(#s2Gold)"),
                            hosts2=m))
    print("written: assets/wc-seal.svg, assets/wc-hosts.svg, badge-options/index.html")


if __name__ == "__main__":
    main()
