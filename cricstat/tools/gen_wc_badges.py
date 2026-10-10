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
