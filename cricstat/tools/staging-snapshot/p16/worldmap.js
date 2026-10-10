/* Cricket world map (sample, P1.6 review). Shapes: assets/world-map.json, built by tools/fetch_world_map.py
   from Natural Earth (public domain; India's point of view for borders). Data: /v1/teams, /v1/ratings,
   /v1/forecasts/wc-2027/latest, and per team on click /v1/teams/<slug>/record + /results.
   Colour = one blue hue, darker = less (sequential, 5 bands) on the dark surface; grey = no team or no
   value. A list view carries the same numbers as text. DOM via textContent only. */
(function () {
  const C = window.cricstat, h = C.h;
  const NS = "http://www.w3.org/2000/svg";
  // same ?v= as this script, so a new map file is fetched when the page version changes
  const MAP_URL = "/cricket/assets/world-map.json" + ((document.currentScript && document.currentScript.src.match(/\?v=\w+/)) || [""])[0];
  const BANDS = ["#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"];
  const NO_VALUE = "#2b3140", LAND = "#1c212c";
  // Natural Earth codes per cricket team (cricket splits the UK; Ireland is all-island; West Indies = the
  // Caribbean board's members incl. the Leeward Islands territories).
  const CODES = {
    "England": ["ENG", "WLS"], "Scotland": ["SCT"], "Ireland": ["IRL", "NIR"],
    "West Indies": ["JAM", "TTO", "GUY", "BRB", "ATG", "DMA", "GRD", "KNA", "LCA", "VCT", "AIA", "MSR", "VGB", "VIR", "SXM"],
    "Argentina": ["ARG"], "Australia": ["AUS"], "Austria": ["AUT"], "Bahamas": ["BHS"], "Bahrain": ["BHR"], "Bangladesh": ["BGD"],
    "Belgium": ["BEL"], "Belize": ["BLZ"], "Bermuda": ["BMU"], "Bhutan": ["BTN"], "Botswana": ["BWA"], "Brazil": ["BRA"],
    "Bulgaria": ["BGR"], "Cambodia": ["KHM"], "Cameroon": ["CMR"], "Canada": ["CAN"], "Cayman Islands": ["CYM"], "Chile": ["CHL"],
    "China": ["CHN"], "Cook Islands": ["COK"], "Costa Rica": ["CRI"], "Croatia": ["HRV"], "Cyprus": ["CYP"], "Czech Republic": ["CZE"],
    "Denmark": ["DNK"], "Estonia": ["EST"], "Eswatini": ["SWZ"], "Swaziland": ["SWZ"], "Fiji": ["FJI"], "Finland": ["FIN"],
    "France": ["FRA"], "Gambia": ["GMB"], "Germany": ["DEU"], "Ghana": ["GHA"], "Gibraltar": ["GIB"], "Greece": ["GRC"],
    "Guernsey": ["GGY"], "Hong Kong": ["HKG"], "Hungary": ["HUN"], "India": ["IND"], "Indonesia": ["IDN"], "Iran": ["IRN"],
    "Isle of Man": ["IMN"], "Israel": ["ISR"], "Italy": ["ITA"], "Ivory Coast": ["CIV"], "Japan": ["JPN"], "Jersey": ["JEY"],
    "Kenya": ["KEN"], "Kuwait": ["KWT"], "Lesotho": ["LSO"], "Luxembourg": ["LUX"], "Malawi": ["MWI"], "Malaysia": ["MYS"],
    "Maldives": ["MDV"], "Mali": ["MLI"], "Malta": ["MLT"], "Mexico": ["MEX"], "Mongolia": ["MNG"], "Mozambique": ["MOZ"],
    "Myanmar": ["MMR"], "Namibia": ["NAM"], "Nepal": ["NPL"], "Netherlands": ["NLD"], "New Zealand": ["NZL"], "Nigeria": ["NGA"],
    "Norway": ["NOR"], "Oman": ["OMN"], "Pakistan": ["PAK"], "Panama": ["PAN"], "Papua New Guinea": ["PNG"], "Peru": ["PER"],
    "Philippines": ["PHL"], "Portugal": ["PRT"], "Qatar": ["QAT"], "Romania": ["ROU"], "Rwanda": ["RWA"], "Samoa": ["WSM"],
    "Saudi Arabia": ["SAU"], "Serbia": ["SRB"], "Seychelles": ["SYC"], "Sierra Leone": ["SLE"], "Singapore": ["SGP"],
    "Slovenia": ["SVN"], "South Africa": ["ZAF"], "South Korea": ["KOR"], "Spain": ["ESP"], "Sri Lanka": ["LKA"],
    "St Helena": ["SHN"], "Suriname": ["SUR"], "Sweden": ["SWE"], "Switzerland": ["CHE"], "Tanzania": ["TZA"], "Thailand": ["THA"],
    "Timor-Leste": ["TLS"], "Turkey": ["TUR"], "Turks and Caicos Island": ["TCA"], "Uganda": ["UGA"],
    "United Arab Emirates": ["ARE"], "United States of America": ["USA"], "Uzbekistan": ["UZB"], "Vanuatu": ["VUT"],
    "Zambia": ["ZMB"], "Zimbabwe": ["ZWE"], "Afghanistan": ["AFG"],
  };
  const METRICS = {
    rating: { label: "cricstat Elo (ODI)", men: true, breaks: [1100, 1250, 1400, 1500], fmt: (v) => String(Math.round(v)),
              legend: ["< 1100", "1100–1249", "1250–1399", "1400–1499", "1500+"] },
    wc: { label: "ODI WC 2027 title chance", men: true, breaks: [0.001, 0.01, 0.05, 0.10], fmt: (v) => pct(v),
          legend: ["< 0.1%", "0.1–1%", "1–5%", "5–10%", "10%+"] },
    odiwin: { label: "ODI win % (2 yrs)", men: false, breaks: [20, 40, 55, 70], fmt: (v) => C.ratio(v) + "%",
              legend: ["< 20%", "20–39%", "40–54%", "55–69%", "70%+"] },
    t20win: { label: "T20I win % (2 yrs)", men: false, breaks: [20, 40, 55, 70], fmt: (v) => C.ratio(v) + "%",
              legend: ["< 20%", "20–39%", "40–54%", "55–69%", "70%+"] },
    matches: { label: "Matches in our data", men: false, breaks: [25, 75, 200, 500], fmt: (v) => C.num(v),
               legend: ["< 25", "25–74", "75–199", "200–499", "500+"] },
  };
  // Region zooms as [west, south, east, north] in degrees.
  const REGIONS = [["world", "🌍 World", null], ["asia", "South Asia & Gulf", [44, 0, 98, 38]],
    ["europe", "Europe", [-12, 35, 32, 62]], ["africa", "Africa", [-20, -36, 52, 18]],
    ["americas", "Americas & Caribbean", [-125, -10, -55, 50]], ["oceania", "Oceania", [110, -48, 180, 0]]];

  const MIN_MATCHES = 5;          // fewer and a win % says little (1–0 would be 100%)
  let FORM = { ODI: {}, T20I: {} }, SINCE = null;
  const H2H = {};                // followed team's slug → { ODI: {opponent slug: row}, T20I: {...} }
  let MAP = null, TEAMS = [], RATINGS = {}, WC = null, gender = "male", metric = "rating", view = "map", region = "world";
  let selected = null;
  const follow = C.getFollow();
  // data-model="off" (until the predictor page is public): no model numbers (ratings, WC 2027 chances) on the map.
  const landingEl = document.getElementById("c-landing");
  const MODEL = !landingEl || landingEl.dataset.model !== "off";
  if (!MODEL) { delete METRICS.rating; delete METRICS.wc; metric = "odiwin"; }

  const nth = (n) => n + ([, "st", "nd", "rd"][(n % 100 >> 3 ^ 1) && n % 10] || "th");
  function pct(p) {
    if (p === null || p === undefined) return "—";
    if (p === 0) return "0%";
    if (p < 0.001) return "<0.1%";
    return (100 * p).toFixed(1) + "%";
  }

  // Equal Earth, the same projection and scale as tools/fetch_world_map.py.
  const A1 = 1.340264, A2 = -0.081106, A3 = 0.000893, A4 = 0.003796, M = Math.sqrt(3) / 2;
  function proj(lon, lat) {
    const t = Math.asin(M * Math.sin(lat * Math.PI / 180)), t2 = t * t, t6 = t2 * t2 * t2;
    return [lon * Math.PI / 180 * Math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))),
            t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))];
  }
  const XMAX = proj(180, 0)[0], YMAX = proj(0, 90)[1];
  function px(lon, lat) { const [x, y] = proj(lon, lat), s = MAP.width / (2 * XMAX); return [(x + XMAX) * s, (YMAX - y) * s]; }
  function viewBox(r) {
    if (!r) return "0 0 " + MAP.width + " " + MAP.height;
    const pts = [px(r[0], r[1]), px(r[0], r[3]), px(r[2], r[1]), px(r[2], r[3])];
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    // keep the map's aspect so the box doesn't jump in height
    const w = Math.max(x1 - x0, (y1 - y0) * MAP.width / MAP.height), hgt = w * MAP.height / MAP.width;
    return [(x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - hgt / 2, w, hgt].map((v) => v.toFixed(1)).join(" ");
  }

  // ── data per team for the current gender ──
  function teamsNow() {
    const list = TEAMS.filter((t) => t.gender === gender && CODES[t.name]).map((t) => ({
      name: t.name, slug: t.slug, matches: t.matches, first: t.first_date, last: t.last_date,
      rating: gender === "male" && RATINGS[t.name] ? RATINGS[t.name] : null,
      wc: gender === "male" && WC ? WC.byName[t.name] || null : null,
      odi: FORM.ODI[t.slug] || null, t20: FORM.T20I[t.slug] || null }));
    // Afghanistan men: no Cricsheet matches (withheld), but rated from our reviewed results list.
    if (gender === "male" && RATINGS.Afghanistan && !list.some((t) => t.name === "Afghanistan"))
      list.push({ name: "Afghanistan", slug: null, matches: null, rating: RATINGS.Afghanistan,
                  wc: WC ? WC.byName.Afghanistan || null : null, withheld: true });
    return list;
  }
  function value(t) {
    if (metric === "rating") return t.rating ? t.rating.rating : null;
    if (metric === "wc") return t.wc ? t.wc.probabilities.champion || 0 : null;
    if (metric === "odiwin") return t.odi && t.odi.matches >= MIN_MATCHES ? t.odi.win_pct : null;
    if (metric === "t20win") return t.t20 && t.t20.matches >= MIN_MATCHES ? t.t20.win_pct : null;
    return t.matches;
  }
  function band(v) {
    if (v === null || v === undefined) return null;
    const b = METRICS[metric].breaks;
    let i = 0;
    while (i < b.length && v >= b[i]) i++;
    return i;
  }

  // ── map ──
  function svgEl(tag, attrs) { const el = document.createElementNS(NS, tag); Object.keys(attrs).forEach((k) => el.setAttribute(k, attrs[k])); return el; }
  let svg = null, tip = null;
  function drawMap() {
    const host = document.getElementById("wm-map");
    const list = teamsNow(), byCode = {};
    list.forEach((t) => CODES[t.name].forEach((c) => { byCode[c] = t; }));
    svg = svgEl("svg", { viewBox: viewBox((REGIONS.find((r) => r[0] === region) || [])[2]), class: "wm-svg",
                         role: "img", "aria-label": "World map of cricket teams coloured by " + METRICS[metric].label });
    const land = svgEl("g", { class: "wm-land" }), teams = svgEl("g", { class: "wm-teams" }), dots = svgEl("g", { class: "wm-dots" });
    const area = {};
    MAP.shapes.forEach((s) => { const t = byCode[s.code]; if (t) area[t.name] = (area[t.name] || 0) + s.area; });
    MAP.shapes.forEach((s) => {
      const t = byCode[s.code];
      if (!s.d && !t) return;
      if (!t) { land.appendChild(svgEl("path", { d: s.d, fill: LAND })); return; }
      const b = band(value(t)), fill = b === null ? NO_VALUE : BANDS[b];
      if (s.d) {
        const p = svgEl("path", { d: s.d, fill, class: "wm-team" + (t.slug === follow ? " me" : "") + (selected === t.name ? " sel" : "") });
        p.dataset.team = t.name;
        teams.appendChild(p);
      }
      // tiny members (Bermuda, Jersey, Singapore…): one dot per team at its main island so it stays visible and clickable
      if (area[t.name] < 4 && CODES[t.name][0] === s.code) {
        const c = svgEl("circle", { cx: s.x, cy: s.y, r: 3.2, fill, class: "wm-dot" + (selected === t.name ? " sel" : "") });
        c.dataset.team = t.name;
        dots.appendChild(c);
      }
    });
    svg.appendChild(land); svg.appendChild(teams); svg.appendChild(dots);
    if (metric === "wc" && WC) {                       // ★ on the 10 teams already in the World Cup
      const marks = svgEl("g", { class: "wm-stars", "aria-hidden": "true" });
      list.filter((t) => t.wc && t.wc.direct_qualifier).forEach((t) => {
        const s = MAP.shapes.filter((x) => CODES[t.name].includes(x.code)).sort((a, b) => b.area - a.area)[0];
        const txt = svgEl("text", { x: s.x, y: s.y, class: "wm-star", "text-anchor": "middle", "dominant-baseline": "central" });
        txt.textContent = "★";
        marks.appendChild(txt);
      });
      svg.appendChild(marks);
    }
    svg.addEventListener("pointermove", (ev) => {
      const name = ev.target.dataset && ev.target.dataset.team;
      if (!name) { tip.hidden = true; return; }
      const t = list.find((x) => x.name === name), r = host.getBoundingClientRect();
      C.fill(tip, tipBody(t));
      tip.hidden = false;
      const tw = tip.offsetWidth || 260, th = tip.offsetHeight || 150;      // keep the card inside the map
      tip.style.left = Math.max(4, Math.min(ev.clientX - r.left + 14, r.width - tw - 4)) + "px";
      tip.style.top = Math.max(4, (ev.clientY - r.top + th + 18 > r.height ? ev.clientY - r.top - th - 10 : ev.clientY - r.top + 14)) + "px";
    });
    svg.addEventListener("pointerleave", () => { tip.hidden = true; });
    svg.addEventListener("click", (ev) => { const name = ev.target.dataset && ev.target.dataset.team; if (name) { select(name); askOnce(); } });
    tip = h("div", { class: "wm-tip", hidden: true, "aria-hidden": "true" });
    C.fill(host, [svg, tip]);
  }

  // Head to head against the team you follow (same country, in the gender on show): two calls per
  // followed team (ODI, T20I), cached, so hovering never waits on the API.
  function followedNow() {
    const f = TEAMS.find((t) => t.slug === follow);
    if (!f) return null;
    return TEAMS.find((t) => t.name === f.name && t.gender === gender && t.team_type === "international") || null;
  }
  async function loadH2H() {
    const me = followedNow();
    if (!me || H2H[me.slug]) return;
    H2H[me.slug] = { ODI: {}, T20I: {} };
    await Promise.all(["ODI", "T20I"].map((f) => C.api("/v1/teams/" + me.slug + "/head-to-head?scope=" + f)
      .then(({ data }) => data.forEach((r) => { if (r.opponent.slug) H2H[me.slug][f][r.opponent.slug] = r; })).catch(() => {})));
  }
  function h2hLine(t) {
    const me = followedNow();
    if (!me || !t.slug || t.slug === me.slug || !H2H[me.slug]) return null;
    const parts = [["ODIs", H2H[me.slug].ODI[t.slug]], ["T20Is", H2H[me.slug].T20I[t.slug]]].filter((x) => x[1])
      .map(([n, r]) => n + " " + r.won + "–" + r.lost + (r.tied ? " (" + r.tied + " tied)" : ""));
    return ["v " + me.name, parts.length ? me.name + " won–lost: " + parts.join(" · ") : "never met in our data"];
  }

  // Hover card: only what the page already holds (no request per hover); record + form are in the panel.
  function wcLine(t) {
    if (gender !== "male" || !WC) return null;
    const w = t.wc;
    if (!w) return ["ODI WC 2027", "not in the 2027 race"];
    const p = w.probabilities;
    const where = (w.direct_qualifier ? "qualified · group " + w.group : pct(p.qualified) + " to get through the Qualifier")
      + (WC.hosts.includes(t.name) && WC.home ? " · 🏠 host: +" + WC.home + " home advantage" : "");
    return ["ODI WC 2027", pct(p.champion) + " title (" + nth(WC.rank[t.name]) + " favourite) · " + pct(p.final) + " final · " + pct(p.semi) + " semi", where];
  }
  const ROW = { rating: "cricstat Elo", wc: "ODI WC 2027", matches: "In our data", odiwin: "ODIs · 2 yrs", t20win: "T20Is · 2 yrs" };
  function formLine(r) {
    if (!r) return "none";
    return r.won + "–" + r.lost + (r.tied ? "–" + r.tied + "T" : "") + " in " + r.matches +
      (r.matches >= MIN_MATCHES ? " · " + C.ratio(r.win_pct) + "% won" : " (too few for a win %)");
  }
  function tipBody(t) {
    const rows = [];
    if (gender === "male" && MODEL) rows.push(["cricstat Elo", t.rating ? Math.round(t.rating.rating) + (t.rating.rank ? " · #" + t.rating.rank : " · unranked (no recent ODIs)") : "not rated"]);
    const wc = wcLine(t);
    if (wc) rows.push(wc);
    if (!t.withheld) { rows.push(["ODIs · 2 yrs", formLine(t.odi)]); rows.push(["T20Is · 2 yrs", formLine(t.t20)]); }
    const hh = h2hLine(t);
    if (hh) rows.push(hh);
    rows.push(["In our data", t.matches ? C.num(t.matches) + " matches · last " + C.date(t.last) : "withheld by Cricsheet"]);
    return [
      h("div", { class: "wm-tip-head" }, [C.teamBadge(t.name, "sm"), h("b", {}, t.name), h("span", { class: "tiny muted" }, gender === "male" ? "men" : "women")]),
      h("dl", { class: "wm-tip-rows" }, rows.map((r) => {
        const on = r[0] === ROW[metric] ? "on" : null;              // the row the map is coloured by
        return [h("dt", { class: on }, r[0]), h("dd", { class: on }, [r[1], r[2] ? h("small", {}, r[2]) : null])];
      }).flat()),
      h("p", { class: "tiny muted wm-tip-hint" }, "Click for record and recent form")];
  }

  // ── list view (the same numbers as text; also the keyboard route) ──
  function drawList() {
    const list = teamsNow().filter((t) => value(t) !== null).sort((a, b) => value(b) - value(a));
    C.fill("wm-map", h("div", { class: "scroll wm-list" }, h("table", { class: "wc-table" }, [
      h("thead", {}, h("tr", {}, ["#", "Team", METRICS[metric].label].map((x, i) => h("th", { scope: "col", class: i === 1 ? "txt" : null }, x)))),
      h("tbody", {}, list.map((t, i) => {
        const b = h("button", { type: "button", class: "link-btn wm-pick" }, t.name);
        b.addEventListener("click", () => { select(t.name); askOnce(); });
        return h("tr", { class: t.slug === follow ? "me" : null }, [h("td", { class: "num" }, String(i + 1)),
          h("td", { class: "txt" }, h("span", { class: "wc-team" }, [C.teamBadge(t.name, "sm"), b])),
          h("td", {}, METRICS[metric].fmt(value(t)))]);
      }))])));
  }

  function legend() {
    const m = METRICS[metric];
    C.fill("wm-legend", [h("span", { class: "tiny muted" }, m.label + ":"),
      ...m.legend.map((l, i) => h("span", { class: "wm-key" }, [h("i", { style: "background:" + BANDS[i] }), l])),
      h("span", { class: "wm-key" }, [h("i", { style: "background:" + NO_VALUE }), metric === "wc" ? "not in the World Cup race" : /win/.test(metric) ? "fewer than " + MIN_MATCHES + " matches" : "no " + m.label.charAt(0).toLowerCase() + m.label.slice(1)]),
      metric === "wc" ? h("span", { class: "wm-key" }, [h("b", { class: "wm-star-key" }, "★"), "already qualified"]) : null,
      /win/.test(metric) && SINCE ? h("span", { class: "tiny muted" }, "Matches since " + C.date(SINCE) + " · win % = won ÷ matches with a result (ties count as not won; no results are left out).") : null]);
  }

  // ── controls ──
  function controls() {
    const pills = h("div", { class: "radio-pill", role: "radiogroup", "aria-label": "Men's or women's teams" },
      [["male", "Men"], ["female", "Women"]].map(([k, n]) => {
        const i = h("input", { type: "radio", name: "wm-gender", value: k });
        i.checked = k === gender;
        i.addEventListener("change", () => {
          gender = k;
          if (!METRICS[metric] || (gender === "female" && METRICS[metric].men)) metric = "odiwin";
          if (!teamsNow().some((t) => t.name === selected)) selected = "India";   // same country if it has a side, else India
          render();
        });
        return h("label", {}, [i, h("span", {}, n)]);
      }));
    const metrics = h("div", { class: "tabs", role: "group", "aria-label": "Colour by" },
      Object.keys(METRICS).filter((k) => gender === "male" || !METRICS[k].men).map((k) => {
        const b = h("button", { type: "button", class: "tab sm", "aria-pressed": String(k === metric) }, METRICS[k].label);
        b.addEventListener("click", () => { metric = k; render(); });
        return b;
      }));
    const views = h("div", { class: "tabs", role: "group", "aria-label": "Show as" }, [["map", "🗺️ Map"], ["list", "📋 List"]].map(([k, n]) => {
      const b = h("button", { type: "button", class: "tab sm", "aria-pressed": String(k === view) }, n);
      b.addEventListener("click", () => { view = k; render(); });
      return b;
    }));
    const regions = h("div", { class: "tabs wm-regions", role: "group", "aria-label": "Zoom to" }, REGIONS.map(([k, n]) => {
      const b = h("button", { type: "button", class: "tab sm", "aria-pressed": String(k === region) }, n);
      b.addEventListener("click", () => { region = k; render(); });
      return b;
    }));
    C.fill("wm-controls", [h("div", { class: "row wm-row" }, [pills, metrics, views]), view === "map" ? regions : null]);
  }

  // ── detail panel ──
  // After the visitor's own first pick, the site feedback pill asks about the map (feedback-widget.js).
  let asked = false;
  function askOnce() {
    if (asked) return;
    asked = true;
    try { if (window.phl && window.phl.nudge) window.phl.nudge("Like the world map?", "map"); } catch (e) { /* optional */ }
  }

  async function select(name) {
    selected = name;
    if (view === "map") document.querySelectorAll(".wm-team, .wm-dot").forEach((el) => el.classList.toggle("sel", el.dataset.team === name));
    const t = teamsNow().find((x) => x.name === name);
    const panel = document.getElementById("wm-panel");
    if (!t) { C.fill(panel, h("p", { class: "muted" }, "Pick a team on the map.")); return; }
    const facts = [];
    if (t.rating) facts.push(["cricstat Elo", Math.round(t.rating.rating) + (t.rating.rank ? " · #" + t.rating.rank : " · unranked (no recent ODIs)")]);
    if (t.wc) facts.push(["ODI WC 2027", pct(t.wc.probabilities.champion) + " title chance · " + nth(WC.rank[t.name]) + " favourite" + (t.wc.direct_qualifier ? " · qualified (group " + t.wc.group + ")" : " · via the Qualifier")
      + (WC.hosts.includes(t.name) && WC.home ? " · 🏠 host (+" + WC.home + " home advantage)" : "")]);
    if (!t.withheld) { facts.push(["ODIs · 2 yrs", formLine(t.odi)]); facts.push(["T20Is · 2 yrs", formLine(t.t20)]); }
    const hh = h2hLine(t);
    if (hh) facts.push(hh);
    if (t.matches) facts.push(["In our data", C.num(t.matches) + " international matches since " + t.first.slice(0, 4)]);
    C.fill(panel, [
      h("div", { class: "wm-head" }, [C.teamBadge(t.name, "lg"), h("div", {}, [h("div", { class: "section-label" }, gender === "male" ? "Men" : "Women"), h("h2", { class: "section-title", style: "margin:0" }, t.name)])]),
      h("dl", { class: "wm-facts" }, facts.map(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]).flat()),
      t.withheld ? h("p", { class: "tiny wm-note" }, "Cricsheet withholds Afghanistan men's matches (a protest over Afghan women's cricket), so there is no team page. The rating and forecast use our reviewed results list.") : null,
      h("div", { id: "wm-record" }, t.slug ? h("div", { class: "skeleton", style: "height:90px" }) : null),
      t.slug ? h("a", { class: "btn pri wm-open", href: "/cricket/countries/" + t.slug + "/" }, "Open the " + t.name + " page →") : null]);
    if (!t.slug) return;
    try {
      const [{ data: rec }, { data: res }] = await Promise.all([C.api("/v1/teams/" + t.slug + "/record"), C.api("/v1/teams/" + t.slug + "/results?limit=5")]);
      if (selected !== name) return;
      C.fill("wm-record", [
        C.table(["Format", "Mat", "Won", "Lost", "Win %"], rec.filter((r) => r.matches && ["TEST", "ODI", "T20I"].includes(r.format)).map((r) => [C.fmtName(r.format), r.matches, r.won, r.lost, C.ratio(r.win_pct)]), { textCols: [0] }),
        res.length ? h("div", { class: "row wm-form" }, [h("span", { class: "tiny muted" }, "Last " + res.length + ":"), C.formDots(res.map((r) => r.outcome)),
          h("span", { class: "tiny muted" }, "latest " + C.date(res[0].date) + " v " + res[0].opponent.name)]) : null]);
    } catch (e) { C.showError("wm-record", e, "this team's record"); }
  }

  function render() {
    const me = followedNow();
    if (me && !H2H[me.slug]) loadH2H().then(() => { if (selected) select(selected); });
    controls(); legend();
    if (view === "map") drawMap(); else drawList();
    if (selected) select(selected);
  }

  async function init() {
    try {
      const [map, teams, ratings, wc] = await Promise.all([
        fetch(MAP_URL).then((r) => { if (!r.ok) throw new Error("map " + r.status); return r.json(); }),
        C.api("/v1/teams?type=international"), MODEL ? C.api("/v1/ratings?scope=ODI&gender=male").catch(() => ({ data: [] })) : { data: [] },
        MODEL ? C.api("/v1/forecasts/wc-2027/latest").catch(() => null) : null]);
      MAP = map; TEAMS = teams.data;
      // Hero tile: countries on the map (distinct names with a men's or women's international side)
      const tile = document.getElementById("c-count");
      if (tile) {
        const names = new Set(TEAMS.filter((t) => CODES[t.name]).map((t) => t.name));
        C.countUp(tile, names.size);
      }
      // last two years up to the newest match we hold
      const newest = TEAMS.reduce((m, t) => (t.last_date > m ? t.last_date : m), "");
      SINCE = (Number(newest.slice(0, 4)) - 2) + newest.slice(4);
      const recs = await Promise.all(["ODI", "T20I"].map((f) => C.api("/v1/records/teams?type=international&scope=" + f + "&from=" + SINCE).catch(() => ({ data: [] }))));
      ["ODI", "T20I"].forEach((f, i) => recs[i].data.forEach((r) => { FORM[f][r.slug] = r; }));
      ratings.data.forEach((r) => { RATINGS[r.team] = r; });
      if (wc) {
        // title-chance rank ("2nd favourite") and the hosts' home advantage, both from the forecast itself
        WC = { byName: {}, rank: {}, hosts: wc.data.tournament.hosts || [], home: ((wc.data.model || {}).elo || {}).home };
        wc.data.teams.forEach((t) => { WC.byName[t.team] = t; });
        wc.data.teams.slice().sort((a, b) => (b.probabilities.champion || 0) - (a.probabilities.champion || 0))
          .forEach((t, i) => { WC.rank[t.team] = i + 1; });
      }
      const me = TEAMS.find((t) => t.slug === follow);
      gender = me ? me.gender : "male";
      if (!METRICS[metric] || (gender === "female" && METRICS[metric].men)) metric = "odiwin";
      selected = me && CODES[me.name] ? me.name : "India";
      render();
    } catch (e) { C.showError("wm-map", e, "the map"); }
  }
  // countries.js starts it on the Countries landing (/cricket/countries/), not on team pages.
  window.cricstatMap = { init };
})();
