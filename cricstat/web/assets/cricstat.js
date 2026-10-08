/* cricstat shared helpers (P0.4): API access, number formatting (F4 R23), safe DOM building.
   No cookies; the only browser storage is "cricstat:follow" (the team you follow), kept in
   localStorage and listed on the privacy page. Every number comes from /cricket/api (F5). */
(function () {
  "use strict";
  const API = "/cricket/api";

  async function api(path) {
    const res = await fetch(API + path, { headers: { Accept: "application/json" } });
    let body = null;
    try { body = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok) {
      const err = new Error((body && (body.detail || body.title)) || ("HTTP " + res.status));
      err.status = res.status;
      throw err;
    }
    return body;                       // {data, meta}
  }

  // F4 R23: ratios are cut to 2 decimals, not rounded, as published records show them.
  function ratio(v) {
    if (v === null || v === undefined) return "—";
    const s = Number(v).toFixed(6);
    return s.slice(0, s.indexOf(".") + 3);
  }
  function num(v) {
    if (v === null || v === undefined) return "—";
    return Number(v).toLocaleString("en-US");
  }
  function hs(runs, notOut) { return runs === null || runs === undefined ? "—" : runs + (notOut ? "*" : ""); }
  function bbi(best) { return best && best.wickets !== null && best.wickets !== undefined ? best.wickets + "/" + best.runs : "—"; }
  function overs(balls) { return balls ? Math.floor(balls / 6) + "." + (balls % 6) : "0.0"; }
  function date(iso) {
    if (!iso) return "—";
    const d = new Date(iso + "T00:00:00Z");
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  }
  const LETTER = { won: "W", lost: "L", tied: "T", drawn: "D", no_result: "N" };
  function letter(outcome) { return LETTER[outcome] || "?"; }

  // h("td", {class: "x"}, "text" | Node | [children]) — text is always set as text, never HTML.
  function h(tag, attrs, children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const c of [].concat(children === undefined ? [] : children)) {
      if (c === null || c === undefined || c === false) continue;
      el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  function fill(target, children) {
    const el = typeof target === "string" ? document.getElementById(target) : target;
    if (!el) return null;
    el.replaceChildren(...[].concat(children).filter((c) => c !== null && c !== undefined));
    return el;
  }
  function table(headers, rows, opts) {
    opts = opts || {};
    return h("div", { class: "scroll" }, h("table", { style: opts.minWidth ? "min-width:" + opts.minWidth : null }, [
      h("thead", {}, h("tr", {}, headers.map((t, i) =>
        h("th", { scope: "col", class: (opts.textCols || []).includes(i) ? "txt" : null }, t)))),
      h("tbody", {}, rows.map((r) => h("tr", {}, r.map((c, i) =>
        h("td", { class: (opts.textCols || []).includes(i) ? "txt" : null }, c))))),
    ]));
  }
  function showError(target, err, what) {
    fill(target, h("div", { class: "error", role: "alert" },
      "Couldn't load " + what + ": " + (err && err.message ? err.message : err) + ". Please try again later."));
  }

  // Remembered team (no cookies). Storage may be blocked: then it simply isn't remembered.
  const FOLLOW_KEY = "cricstat:follow";
  function getFollow() { try { return localStorage.getItem(FOLLOW_KEY) || "india-men"; } catch (e) { return "india-men"; } }
  function setFollow(slug) { try { localStorage.setItem(FOLLOW_KEY, slug); } catch (e) { /* ignore */ } }

  // /cricket/players/virat-kohli-ba607b88/ → "ba607b88"; /cricket/countries/india-men/ → "india-men"
  function pathTail(section) {
    const m = location.pathname.match(new RegExp("^/cricket/" + section + "/([a-z0-9-]+)/?$"));
    return m ? m[1] : null;
  }
  function playerIdFromPath() {
    const t = pathTail("players");
    const m = t && t.match(/([0-9a-f]{8})$/);
    return m ? m[1] : null;
  }

  function dataNote(meta) {
    const el = document.getElementById("data-note");
    if (el && meta && meta.data_as_of) el.textContent = date(meta.data_as_of);
  }

  // ── Visual identity without flags or logos (planning decision: no national flags, no board or
  //    franchise marks): a 3-letter code on the team's sporting colours. Clubs get a neutral colour
  //    derived from their name, so nothing imitates their branding.
  const TEAM = {
    "India": ["IND", "#1347A3", "#FF9933"], "Australia": ["AUS", "#00843D", "#FFCD00"],
    "England": ["ENG", "#1D2E5B", "#CF142B"], "Pakistan": ["PAK", "#01411C", "#9AD39A"],
    "South Africa": ["RSA", "#007A4D", "#FFB612"], "New Zealand": ["NZ", "#111111", "#9AA0A6"],
    "Sri Lanka": ["SL", "#0B2F6B", "#FFBE29"], "West Indies": ["WI", "#7B0041", "#F2C94C"],
    "Bangladesh": ["BAN", "#006A4E", "#F42A41"], "Afghanistan": ["AFG", "#0B3D91", "#D32011"],
    "Zimbabwe": ["ZIM", "#C8102E", "#FCE300"], "Ireland": ["IRE", "#169B62", "#7CD39B"],
    "Scotland": ["SCO", "#1D3F8F", "#9DB7F0"], "Netherlands": ["NED", "#E2591B", "#FFD5B5"],
    "United Arab Emirates": ["UAE", "#00732F", "#C8102E"], "United States of America": ["USA", "#0A3161", "#B31942"],
    "Nepal": ["NEP", "#C1121F", "#1D3F8F"], "Oman": ["OMA", "#C8102E", "#00843D"],
    "Namibia": ["NAM", "#003580", "#D21034"], "Canada": ["CAN", "#D80621", "#F5B7B1"],
    "Hong Kong": ["HK", "#BA0C2F", "#F3B6C0"], "Thailand": ["THA", "#2D2A4A", "#A51931"],
    "Kenya": ["KEN", "#0E5E2F", "#BB0000"], "Uganda": ["UGA", "#111111", "#FCDC04"],
    "Papua New Guinea": ["PNG", "#111111", "#CE1126"], "Malaysia": ["MAS", "#010066", "#FFCC00"],
  };
  function hashHue(str) { let x = 0; for (const c of str) x = (x * 31 + c.charCodeAt(0)) >>> 0; return x % 360; }
  function teamStyle(name) {
    if (TEAM[name]) return TEAM[name];
    const words = name.replace(/[^A-Za-z ]/g, "").split(/\s+/).filter(Boolean);
    const code = (words.length > 1 ? words.map((w) => w[0]).join("") : name).slice(0, 3).toUpperCase();
    const hue = hashHue(name);
    return [code, "hsl(" + hue + ",35%,32%)", "hsl(" + hue + ",35%,55%)"];
  }
  // National flags (public domain, self-hosted; see assets/flags.js) at their own proportions:
  // never stretched or cropped. Teams without one keep the colour badge.
  const FLAGS = window.CRICSTAT_FLAGS || {};
  const FLAG_H = { xs: 12, sm: 20, "": 26, lg: 52 };
  function teamBadge(name, size) {
    const f = FLAGS[name];
    if (f) {
      const hgt = FLAG_H[size || ""];
      return h("span", { class: "tflag" + (size ? " " + size : ""), title: name }, h("img", {
        src: "/cricket/flags/" + f.file, alt: "", width: Math.round(hgt * f.w / f.h), height: hgt,
        loading: "lazy", decoding: "async" }));
    }
    const [code, c1, c2] = teamStyle(name || "?");
    return h("span", { class: "tbadge" + (size ? " " + size : ""), title: name, "aria-hidden": "true",
                       style: "background:" + c1 + ";--b2:" + c2 }, code);
  }
  // Say plainly when the newest data is old: Cricsheet publishes completed matches with a delay.
  // Prefers the source's own last update (recorded by the daily check), else the newest match.
  function freshness(el, source, asOf) {
    if (!el || !asOf) return;
    const when = source && source.last_updated ? source.last_updated.slice(0, 10) : asOf;
    const days = Math.floor((Date.now() - Date.parse(when + "T12:00:00Z")) / 86400000);
    el.hidden = days < 7;
    el.textContent = source && source.last_updated
      ? "⏱ Cricsheet's last update was " + date(when) + " (" + ago(when) + "); we check for new matches every day and add them as soon as they're published."
      : "⏱ Newest match in the data is " + ago(asOf) + " (" + date(asOf) + "); we check for new matches every day and add them as soon as they're published.";
  }
  // Section tabs (WAI-ARIA tabs pattern): [role=tablist] > [role=tab][aria-controls] → [role=tabpanel].
  function sectionTabs(list) {
    if (!list) return;
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    const select = (t, focus) => {
      tabs.forEach((x) => { const on = x === t; x.setAttribute("aria-selected", String(on)); x.tabIndex = on ? 0 : -1;
        const pane = document.getElementById(x.getAttribute("aria-controls")); if (pane) pane.hidden = !on; });
      if (focus) t.focus();
      window.dispatchEvent(new Event("resize"));   // strips/carousels re-measure once visible
    };
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => select(t));
      t.addEventListener("keydown", (e) => {
        const k = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
        if (k) { e.preventDefault(); select(tabs[(i + k + tabs.length) % tabs.length], true); }
        else if (e.key === "Home") { e.preventDefault(); select(tabs[0], true); }
        else if (e.key === "End") { e.preventDefault(); select(tabs[tabs.length - 1], true); }
      });
    });
  }
  // Horizontal score-card strip with ‹ › buttons (same look as the hub's Latest results).
  function carousel(strip, what) {
    const btn = (dir, cls, label, sym) => h("button", { class: "car-btn " + cls, type: "button", "aria-label": label }, sym);
    const prev = btn(-1, "prev", "Previous " + what, "‹"), next = btn(1, "next", "More " + what, "›");
    const update = () => {
      prev.disabled = strip.scrollLeft <= 4;
      next.disabled = strip.scrollLeft + strip.clientWidth >= strip.scrollWidth - 4;
    };
    [[prev, -1], [next, 1]].forEach(([b, dir]) => b.addEventListener("click", () =>
      strip.scrollBy({ left: dir * Math.max(280, strip.clientWidth - 60), behavior: "smooth" })));
    strip.setAttribute("tabindex", "0");
    strip.addEventListener("scroll", () => window.requestAnimationFrame(update), { passive: true });
    window.addEventListener("resize", update);
    new MutationObserver(() => window.requestAnimationFrame(update)).observe(strip, { childList: true });
    window.requestAnimationFrame(update);
    return h("div", { class: "carousel" }, [prev, strip, next]);
  }
  // "India · Batter" line with a small flag in front (only teams with a public-domain flag, see flags.js).
  function teamLine(team, text) {
    return FLAGS[team] ? h("span", { class: "team-line" }, [teamBadge(team, "xs"), text]) : text;
  }
  function initials(name) {
    const parts = (name || "?").replace(/[^A-Za-z ]/g, " ").split(/\s+/).filter(Boolean);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    const first = parts[0].length <= 3 && parts[0] === parts[0].toUpperCase() ? parts[0][0] : parts[0][0];
    return (first + parts[parts.length - 1][0]).toUpperCase();
  }
  function avatar(name, teamName, size, photoUrl) {
    // A player's self-hosted Commons photo (P0.5) when there is one, else coloured initials.
    if (photoUrl) return h("img", { class: "avatar photo" + (size ? " " + size : ""), src: photoUrl, alt: "", loading: "lazy" });
    const [, c1, c2] = teamStyle(teamName || name || "?");
    return h("span", { class: "avatar" + (size ? " " + size : ""), "aria-hidden": "true",
                       style: "background:linear-gradient(135deg," + c1 + "," + c2 + ")" }, initials(name));
  }
  function who(name, sub, teamName, href, extra, photoUrl) {
    let label = href ? h("a", { href: href, class: "name" }, name) : h("span", { class: "name" }, name);
    if (extra) label = h("span", { class: "name-line" }, [label, extra]);
    return h("div", { class: "who" }, [avatar(name, teamName, null, photoUrl), h("div", { style: "min-width:0" },
      [label, sub ? h("div", { class: "sub" }, sub) : null])]);
  }
  // Role icons (API role: batter | bowler | all-rounder | wicketkeeper), drawn as inline SVG.
  const ROLE = { batter: "Batter", bowler: "Bowler", "all-rounder": "All-rounder", wicketkeeper: "Wicketkeeper" };
  const BAT = [["g", { transform: "rotate(40 12 12)" }, [
    ["rect", { x: 11, y: 1.5, width: 2, height: 7, rx: 1, fill: "#4F7FD6" }],
    ["rect", { x: 8.6, y: 8, width: 6.8, height: 14.5, rx: 2.2, fill: "#E9C98B", stroke: "#B8915A", "stroke-width": .9 }],
    ["path", { d: "M12 10v10.5", stroke: "#B8915A", "stroke-width": .8, "stroke-linecap": "round" }]]]];
  const BALL = (cx, cy, r) => [["circle", { cx: cx, cy: cy, r: r, fill: "#C0261F" }],
    ["path", { d: "M" + (cx - r * .45) + " " + (cy - r * .82) + "q" + (r * .5) + " " + (r * .82) + " 0 " + (r * 1.64) +
      "M" + (cx + r * .45) + " " + (cy - r * .82) + "q" + (-r * .5) + " " + (r * .82) + " 0 " + (r * 1.64),
      fill: "none", stroke: "#F5EFE6", "stroke-width": .9, "stroke-linecap": "round" }]];
  const ROLE_SVG = {
    batter: BAT,
    bowler: BALL(12, 12, 9),
    "all-rounder": BAT.concat(BALL(18, 18, 5)),
    wicketkeeper: [
      ["path", { d: "M6.5 19V10.5C6.5 6.8 8.6 3.5 12 3.5s5.5 3 5.5 6.5v3l2.2-1.4c1.2-.7 2.4.6 1.6 1.7L17.5 19z",
                 fill: "#F1F5F9", stroke: "#94A3B8", "stroke-width": .9, "stroke-linejoin": "round" }],
      ["path", { d: "M10 5v6M12.6 4.2V11M15.1 5.2V11", stroke: "#94A3B8", "stroke-width": .8, "stroke-linecap": "round" }],
      ["rect", { x: 6, y: 18.2, width: 12, height: 3.6, rx: 1, fill: "#FF9933" }]],
  };
  function svgNode(spec) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", spec[0]);
    for (const [k, v] of Object.entries(spec[1])) el.setAttribute(k, v);
    for (const c of spec[2] || []) el.appendChild(svgNode(c));
    return el;
  }
  function roleLabel(role) { return ROLE[role] || null; }
  function roleIcon(role) {
    if (!ROLE_SVG[role]) return null;
    const svg = svgNode(["svg", { viewBox: "0 0 24 24", width: 18, height: 18, "aria-hidden": "true", focusable: "false" }, ROLE_SVG[role]]);
    return h("span", { class: "role-ic", title: ROLE[role], role: "img", "aria-label": ROLE[role] }, svg);
  }
  function formDots(outcomes) {
    return h("span", { class: "form", "aria-label": "Last results: " + outcomes.map(letter).join(" ") },
      outcomes.map((o) => h("i", { class: letter(o) }, letter(o))));
  }
  const FMT = { TEST: "Test", ODI: "ODI", T20I: "T20I", T20_LEAGUE: "T20", HUNDRED: "Hundred",
                LIST_A: "List A", FIRST_CLASS: "First-class", T20I_OTHER: "T20I", OD_INTL_OTHER: "ODI",
                MD_INTL_OTHER: "Multi-day" };
  function fmtName(k) { return FMT[k] || k; }
  function resultText(m) {
    if (m.result === "win") return m.winner + " won by " + m.margin + (m.method ? " (" + m.method + ")" : "");
    if (m.result === "tie") return "Match tied" + (m.decided_by === "super_over" && m.winner ? " · " + m.winner + " won the super over" : "");
    if (m.result === "draw") return "Match drawn";
    return "No result";
  }
  // "3 days ago" against today's date (pages are viewed after the data date, so this shows
  // how recent a result really is, not just its position in the list).
  function ago(iso) {
    if (!iso) return "";
    const days = Math.floor((Date.now() - Date.parse(iso + "T12:00:00Z")) / 86400000);
    if (days <= 0) return "today";
    if (days === 1) return "yesterday";
    if (days < 14) return days + " days ago";
    if (days < 60) return Math.round(days / 7) + " weeks ago";
    if (days < 730) return Math.round(days / 30.4) + " months ago";
    return Math.round(days / 365) + " years ago";
  }
  // The 12 grounds of the 2027 ODI World Cup (ICC schedule, 1 Oct 2026). Matched on name and city so a
  // ground's older names count too (Goodyear Park, Chevrolet Park, OUTsurance Oval = Mangaung Oval;
  // New Wanderers = Wanderers) and Windhoek's other "Wanderers" ground doesn't.
  const WC2027_VENUES = [
    [/Newlands/, /Cape Town/], [/SuperSport Park|Centurion Park/, /Centurion/], [/Wanderers/, /Johannesburg/],
    [/Kingsmead/, /Durban/], [/St George's Park/, /Port Elizabeth|Gqeberha/], [/Buffalo Park/, /East London|KuGompo/],
    [/Boland/, /Paarl/], [/Mangaung|Goodyear Park|Chevrolet Park|OUTsurance Oval|Springbok Park/, /Bloemfontein/],
    [/Harare Sports Club/, /.*/], [/Queens Sports Club/, /.*/], [/Namibia Cricket Ground/, /.*/],
    [/Mosi-oa-Tunya/, /.*/]];
  function isWc2027Venue(venue, city) {
    const text = (venue || "") + ", " + (city || "");
    return WC2027_VENUES.some(([v, c]) => v.test(venue || "") && c.test(text));
  }
  function wc2027Mark(short) {
    const label = "2027 ODI World Cup venue";
    return h("span", { class: "wc27", title: label, "aria-label": label, role: "img" }, short ? "★" : "★ WC 2027");
  }
  function matchCard(m) {
    return h("article", { class: "mcard" }, [
      h("div", { class: "top" }, [h("span", { class: "comp" }, m.competition || ""),
        h("span", { class: "badge fmt" }, fmtName(m.format) + (m.gender === "female" ? " · W" : ""))]),
      ...m.teams.map((t) => h("div", { class: "team " + (m.result === "win" ? (t.won ? "won" : "lost") : "") }, [
        teamBadge(t.name, "sm"),
        t.slug ? h("a", { class: "tname", href: "/cricket/countries/" + t.slug + "/", style: "color:inherit" }, t.name)
               : h("span", { class: "tname" }, t.name),
        h("span", { class: "score" }, t.innings.length ? t.innings.map((x, i) => i === 0 ? x.replace(/ \(.*\)$/, "")
          : " & " + x.replace(/ \(.*\)$/, "")).join("") : "—"),
      ])),
      h("div", { class: "res" }, resultText(m)),
      h("div", { class: "where" }, [h("span", { class: "age" }, ago(m.end_date || m.date)), " "]),
      h("div", { class: "where" }, [date(m.date) + " · " + [m.venue, m.city].filter(Boolean).join(", ").replace(/, ([^,]+), \1$/, ", $1"),
        isWc2027Venue(m.venue, m.city) ? wc2027Mark() : null]),
    ]);
  }
  // Results donut (inline SVG, no chart library): won / lost / drawn+tied / no result, win % in
  // the middle. Segments are drawn with stroke-dasharray on one circle per slice.
  const SLICES = [["won", "Won", "#22c55e"], ["lost", "Lost", "#ef4444"], ["dt", "Drawn / tied", "#4F7FD6"],
                  ["no_result", "No result", "#475569"]];
  function donut(r, size) {
    size = size || 100;
    const vals = { won: r.won || 0, lost: r.lost || 0, dt: (r.drawn || 0) + (r.tied || 0), no_result: r.no_result || 0 };
    const total = Object.values(vals).reduce((a, b) => a + b, 0) || 1;
    const NS = "http://www.w3.org/2000/svg", R = 15.915, C = 100;       // circumference 100 → % units
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 42 42"); svg.setAttribute("width", size); svg.setAttribute("height", size);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", SLICES.filter(([k]) => vals[k]).map(([k, label]) => label + " " + vals[k]).join(", "));
    const ring = (stroke, dash, offset) => {
      const c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", 21); c.setAttribute("cy", 21); c.setAttribute("r", R); c.setAttribute("fill", "none");
      c.setAttribute("stroke", stroke); c.setAttribute("stroke-width", 5.2);
      c.setAttribute("stroke-dasharray", dash); c.setAttribute("stroke-dashoffset", offset);
      svg.appendChild(c);
    };
    ring("#212636", "100 0", 0);
    let start = 25;                                                     // begin at 12 o'clock
    for (const [k, , color] of SLICES) {
      const pct = vals[k] * C / total;
      if (pct > 0) ring(color, pct + " " + (C - pct), start);
      start = (start - pct + 100) % 100;
    }
    const txt = (y, size2, weight, fill, text) => {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", 21); t.setAttribute("y", y); t.setAttribute("text-anchor", "middle");
      t.setAttribute("font-size", size2); t.setAttribute("font-weight", weight); t.setAttribute("fill", fill);
      t.textContent = text; svg.appendChild(t);
    };
    txt(21.5, 6.6, 800, "#e2e8f0", r.win_pct === null || r.win_pct === undefined ? "—" : ratio(r.win_pct).replace(/\.\d+$/, "") + "%");
    txt(27.5, 3.4, 600, "#94a3b8", "WIN RATE");
    return svg;
  }
  function donutLegend(r) {
    const vals = { won: r.won || 0, lost: r.lost || 0, dt: (r.drawn || 0) + (r.tied || 0), no_result: r.no_result || 0 };
    // Every row always shown (zeros dimmed), so all cards share one layout.
    return h("ul", { class: "legend" }, SLICES.map(([k, label, color]) =>
      h("li", { class: vals[k] ? null : "zero" }, [h("i", { style: "background:" + color }), label, h("b", {}, num(vals[k]))])));
  }
  // ── Period for team format cards: Last 10 matches · YTD · 1 year · 5 years · All ──
  const PERIODS = [["last10", "Last 10"], ["ytd", "YTD"], ["1y", "1 year"], ["5y", "5 years"], ["all", "All"]];
  function periodRange(key, asOf) {
    const end = new Date(asOf + "T00:00:00Z");
    const iso = (d) => d.toISOString().slice(0, 10);
    if (key === "ytd") return { from: asOf.slice(0, 4) + "-01-01", to: asOf, label: "YTD " + asOf.slice(0, 4) };
    if (key === "1y" || key === "5y") {
      const d = new Date(end); d.setUTCFullYear(d.getUTCFullYear() - (key === "1y" ? 1 : 5)); d.setUTCDate(d.getUTCDate() + 1);
      return { from: iso(d), to: asOf, label: key === "1y" ? "1 year" : "5 years" };
    }
    if (key === "last10") return { last: 10, label: "last 10 matches" };
    return { label: "all" };
  }
  function periodControl(current, onPick) {
    return h("div", { class: "row", style: "gap:.5rem" }, [h("span", { class: "tiny dim", style: "letter-spacing:.1em;text-transform:uppercase" }, "Period"),
      h("div", { class: "tabs", role: "group", "aria-label": "Period" }, PERIODS.map(([k, n]) =>
        h("button", { type: "button", class: "tab sm", "data-period": k, "aria-pressed": String(k === current),
          onclick: (ev) => { ev.currentTarget.parentNode.querySelectorAll("[data-period]").forEach((b) =>
            b.setAttribute("aria-pressed", String(b === ev.currentTarget))); onPick(k); } }, n)))]);
  }
  const NONE = { TEST: "Tests", ODI: "ODIs", T20I: "T20Is" };
  const LAST_TEXT = { won: "beat ", lost: "lost to ", tied: "tied with ", drawn: "drew with ", no_result: "no result v " };
  // One format card (used by the hub and the team pages): donut, legend, form dots, last result.
  async function formatCard(team, scope, period, asOf, href) {
    const p = periodRange(period, asOf);
    const win = p.from ? "&from=" + p.from + "&to=" + p.to : "";
    let r, recent;
    if (p.last) {
      recent = (await api("/v1/teams/" + team.slug + "/results?scope=" + scope + "&limit=" + p.last)).data;
      const c = { won: 0, lost: 0, tied: 0, drawn: 0, no_result: 0 };
      recent.forEach((x) => { c[x.outcome] = (c[x.outcome] || 0) + 1; });
      const played = recent.length - c.no_result;
      r = Object.assign({ matches: recent.length, win_pct: played > 0 ? c.won * 100 / played : null }, c);
    } else {
      const [rec, res] = await Promise.all([
        api("/v1/teams/" + team.slug + "/record?scope=" + scope + win),
        api("/v1/teams/" + team.slug + "/results?scope=" + scope + "&limit=5" + win)]);
      r = rec.data[0]; recent = res.data;
    }
    const label = p.last ? "Last " + recent.length : p.label === "all" ? "All · since " + (team.first_date || "").slice(0, 4) : p.label;
    const head = h("div", { class: "card-head" }, [h("span", { class: "badge fmt" }, fmtName(scope) + " · " + label),
      recent && recent.length ? formDots(recent.slice(0, 5).map((x) => x.outcome)) : null]);
    const tag = href ? "a" : "div";
    if (!r || !r.matches) {
      return h(tag, { class: "card accent fcard", href: href || null }, [head,
        h("div", { class: "donut-row empty" }, h("p", { class: "dim small" }, "No " + (NONE[scope] || "matches") + " in this period.")),
        h("p", { class: "tiny dim last" }, " ")]);
    }
    return h(tag, { class: "card accent fcard", href: href || null }, [head,
      h("div", { class: "donut-row" }, [donut(r), h("div", { class: "stack", style: "gap:.6rem;min-width:0" }, [
        h("div", { class: "kpi" }, [h("b", {}, num(r.matches)), h("span", {}, "Matches"), h("small", {}, "Win " + ratio(r.win_pct) + "%")]),
        donutLegend(r)])]),
      recent[0] ? h("p", { class: "tiny dim last" }, "Last: " + LAST_TEXT[recent[0].outcome] + recent[0].opponent.name + " · " + date(recent[0].date))
                : h("p", { class: "tiny dim last" }, " ")]);
  }

  // Scoreboard digits: an element with class "sb" shows each character on its own tile.
  function scoreText(el, text) {
    if (!el) return;
    if (!el.classList.contains("sb")) { el.textContent = text; return; }
    el.setAttribute("aria-label", text);
    el.replaceChildren(...String(text).split("").map((ch) =>
      h("span", { class: /[0-9]/.test(ch) ? "sb-d" : "sb-s", "aria-hidden": "true" }, ch)));
  }
  function countUp(el, value, ms) {
    if (!el) return;
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !value) { scoreText(el, num(value)); return; }
    const t0 = performance.now(); ms = ms || 900;
    const step = (t) => { const k = Math.min(1, (t - t0) / ms); scoreText(el, num(Math.round(value * (1 - Math.pow(1 - k, 3)))));
                          if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  function compact(v) {
    if (v >= 1e6) return (v / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
    return num(v);
  }

  // Player and team pages get their head (title, description, canonical, robots) from the server
  // since P0.6; scripts then leave document.title alone. Static shells have no robots meta.
  const serverHead = !!document.querySelector('meta[name="robots"]');
  window.cricstat = { serverHead, sectionTabs, scoreText, freshness, carousel, teamLine, roleIcon, roleLabel, api, ratio, num, hs, bbi, overs, date, letter, h, fill, table, showError,
                      getFollow, setFollow, pathTail, playerIdFromPath, dataNote, teamBadge, teamStyle,
                      avatar, who, formDots, fmtName, resultText, matchCard, countUp, compact, ago, isWc2027Venue, wc2027Mark,
                      donut, donutLegend, periodControl, formatCard, periodRange };
})();
