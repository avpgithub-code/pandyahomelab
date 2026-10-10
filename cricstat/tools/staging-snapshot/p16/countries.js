/* cricstat countries page (P0.4): format records, recent results, results by year, head to head,
   home/away and top performers. Team pages live at /cricket/countries/<team-slug>/ (e.g. india-women). */
(function () {
  "use strict";
  const C = window.cricstat, h = C.h;
  const GENDER = { male: "Men", female: "Women" };
  const FORMATS = [["TEST", "Test"], ["ODI", "ODI"], ["T20I", "T20I"]];
  let chart = null, team = null, teams = [];
  if (window.Chart) { window.Chart.defaults.color = "#94a3b8"; window.Chart.defaults.borderColor = "#252a38"; }

  function slugFor(name, gender) { const t = teams.find((x) => x.name === name && x.gender === gender); return t ? t.slug : null; }

  function header() {
    const label = team.name + " " + GENDER[team.gender].toLowerCase();
    document.getElementById("c-name").textContent = label;
    if (!C.serverHead) document.title = label + " — team records | cricstat";
    C.fill("c-badge", C.teamBadge(team.name, "lg"));
    const select = document.getElementById("c-team");
    const india = (t) => t.name === "India" ? 0 : 1;   // India first, as in the hub's "Follow a team"
    const same = teams.filter((t) => t.gender === team.gender && t.matches >= 20)
      .sort((a, b) => india(a) - india(b) || a.name.localeCompare(b.name));
    C.fill(select, same.map((t) => h("option", { value: t.slug }, t.name)));
    select.value = team.slug;
    select.onchange = () => { location.href = "/cricket/countries/" + select.value + "/"; };
    const back = document.getElementById("c-maplink");
    if (!back && document.getElementById("c-landing")) {
      document.getElementById("c-gender").before(h("a", { id: "c-maplink", class: "tab", href: "/cricket/countries/" }, "🌍 World map"));
    }
    C.fill("c-gender", ["male", "female"].map((g) => {
      const slug = slugFor(team.name, g);
      return slug ? h("a", { class: "tab", href: "/cricket/countries/" + slug + "/", "aria-pressed": String(g === team.gender) }, GENDER[g])
                  : h("span", { class: "tab", "aria-disabled": "true", style: "opacity:.4" }, GENDER[g]);
    }));
  }

  let period = "ytd", asOf = null;
  async function formCards() {
    const out = C.fill("c-formats", [h("div", { class: "skeleton" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton" })]);
    C.fill("c-period", C.periodControl(period, (k) => { period = k; formCards(); }));
    try {
      C.fill(out, await Promise.all(["ODI", "T20I", "TEST"].map((k) => C.formatCard(team, k, period, asOf))));   // same order as the hub
    } catch (e) { C.showError(out, e, "records"); }
  }

  // Recent results, one format at a time like the hub's Latest results (ODI first).
  let recentFmt = "ODI", source = null;
  async function recent() {
    document.querySelectorAll("[data-rfmt]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.rfmt === recentFmt)));
    const out = C.fill("c-recent", [h("div", { class: "skeleton" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton" })]);
    try {
      const { data } = await C.api("/v1/matches?team=" + team.slug + "&scope=" + recentFmt + "&limit=16");
      C.fill(out, data.length ? data.map(C.matchCard) : h("p", { class: "muted" }, "No " + (recentFmt === "ALL" ? "" : C.fmtName(recentFmt) + " ") + "matches."));
      out.scrollLeft = 0;
      const span = data.length ? " · " + C.date(data[data.length - 1].date) + " – " + C.date(data[0].end_date || data[0].date) : "";
      document.getElementById("c-recent-note").textContent = data.length + " " + (recentFmt === "ALL" ? "" : C.fmtName(recentFmt) + " ") +
        (data.length === 1 ? "match" : "matches") + span + ", newest first.";
      C.freshness(document.getElementById("c-recent-fresh"), source, asOf);
    } catch (e) { C.showError(out, e, "recent results"); }
  }

  async function yearsChart(scope) {
    document.querySelectorAll("[data-yfmt]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.yfmt === scope)));
    const target = document.getElementById("years-chart");
    try {
      const { data } = await C.api("/v1/teams/" + team.slug + "/years" + (scope ? "?scope=" + scope : ""));
      if (chart) { chart.destroy(); chart = null; }
      if (!data.length || !window.Chart) { C.fill(target, h("p", { class: "muted" }, "No matches.")); return; }
      C.fill(target, h("canvas", { id: "years-canvas", role: "img", "aria-label": "Results by year" }));
      chart = new window.Chart(document.getElementById("years-canvas"), { type: "bar",
        data: { labels: data.map((y) => y.year), datasets: [
          { label: "Won", data: data.map((y) => y.won), backgroundColor: "#22c55e", borderRadius: 4 },
          { label: "Lost", data: data.map((y) => y.lost), backgroundColor: "#ef4444", borderRadius: 4 },
          { label: "Tied / drawn / no result", data: data.map((y) => y.tied + y.drawn + y.no_result), backgroundColor: "#475569", borderRadius: 4 }] },
        options: { responsive: true, maintainAspectRatio: false,
          scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, grid: { color: "#1c2130" } } } } });
    } catch (e) { C.showError(target, e, "results by year"); }
  }

  // What's planned for this format and gender. Only the men's ODI World Cup 2027 predictor is
  // committed (P1); everything else is said to come later, without promising a date.
  // Men's ODI: the live Elo rating and ODI World Cup 2027 chances (P1.6), once the predictor is public
  // (the shell's data-model="off" keeps the "Next" placeholder until then). Fetched once per page.
  const MODEL_ON = (() => { const l = document.getElementById("c-landing"); return !!l && l.dataset.model !== "off"; })();
  let model = null;
  function loadModel() {
    if (!model) {
      model = Promise.all([C.api("/v1/ratings?scope=ODI&gender=male"), C.api("/v1/ratings/" + team.slug + "/history").catch(() => null),
        C.api("/v1/forecasts/wc-2027/latest").catch(() => null)])
        .then(([r, hist, wc]) => ({ rating: r.data.find((x) => x.slug === team.slug) || null, ranked: r.data.filter((x) => x.rank).length,
          points: hist ? hist.data.points : [], wc: wc ? wc.data.teams.find((t) => t.slug === team.slug) || null : null,
          asOf: wc ? wc.data.forecast.data_as_of : null }));
    }
    return model;
  }
  function spark(points) {
    const NS = "http://www.w3.org/2000/svg", W = 260, H = 54;
    if (points.length < 2) return null;
    const ys = points.map((p) => p.rating), lo = Math.min.apply(null, ys) - 5, hi = Math.max.apply(null, ys) + 5;
    const t0 = Date.parse(points[0].date), t1 = Date.parse(points[points.length - 1].date) || t0 + 1;
    const xy = points.map((p) => [(Date.parse(p.date) - t0) / (t1 - t0 || 1) * (W - 8) + 4, H - 4 - (p.rating - lo) / (hi - lo) * (H - 8)]);
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("class", "r-spark"); svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Rating over the last two years: from " + Math.round(ys[0]) + " to " + Math.round(ys[ys.length - 1]));
    const line = document.createElementNS(NS, "polyline");
    line.setAttribute("points", xy.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" "));
    line.setAttribute("fill", "none"); line.setAttribute("stroke", "#3987e5"); line.setAttribute("stroke-width", "2"); line.setAttribute("stroke-linejoin", "round");
    const dot = document.createElementNS(NS, "circle"), last = xy[xy.length - 1];
    dot.setAttribute("cx", last[0]); dot.setAttribute("cy", last[1]); dot.setAttribute("r", "3.5"); dot.setAttribute("fill", "#FF9933");
    svg.appendChild(line); svg.appendChild(dot);
    return svg;
  }
  const pctTxt = (p) => (p === null || p === undefined ? "—" : p === 0 ? "0%" : p < 0.001 ? "<0.1%" : (100 * p).toFixed(1) + "%");
  async function liveRatings() {
    const target = C.fill("f-ratings", [h("div", { class: "card-head" }, [h("h2", {}, "Ratings & ODI World Cup 2027"), h("span", { class: "badge live" }, "Live")]),
      h("div", { class: "skeleton", style: "height:120px" })]);
    try {
      const m = await loadModel();
      if (!m.rating) {
        C.fill(target, [h("div", { class: "card-head" }, [h("h2", {}, "Ratings & ODI World Cup 2027"), h("span", { class: "badge soon" }, "Not rated")]),
          h("p", { class: "dim small" }, "Not rated: " + team.name + " hasn't played enough official ODIs for an Elo rating."),
          h("a", { class: "small", href: "/cricket/methodology/" }, "How ratings work →")]);
        return;
      }
      // Windows run back from the data date, not from the team's last match (a team that stopped
      // playing ODIs years ago has no "last 12 months").
      const r = m.rating, ref = Date.parse(m.asOf || new Date().toISOString().slice(0, 10));
      const ago = (days) => new Date(ref - days * 864e5).toISOString().slice(0, 10);
      const pts = m.points.filter((p) => p.date >= ago(730));
      const before = m.points.filter((p) => p.date <= ago(365)).pop();
      const recent = m.points.some((p) => p.date > ago(365));
      const delta = before && recent ? Math.round(r.rating - before.rating) : null;
      const w = m.wc, p = w ? w.probabilities : null;
      const where = !w ? "Not in the 2027 race." : w.direct_qualifier ? "Qualified · group " + w.group + "."
        : pctTxt(p.qualified) + " to get through the Qualifier (Feb–Mar 2027).";
      C.fill(target, [
        h("div", { class: "card-head" }, [h("h2", {}, "Ratings & ODI World Cup 2027"), h("span", { class: "badge live" }, "Live")]),
        h("div", { class: "r-top" }, [
          h("div", { class: "r-big" }, [h("b", {}, String(Math.round(r.rating))), h("span", {}, r.rank ? "#" + r.rank + " of " + m.ranked + " ranked" : "unranked (no recent ODIs)"),
            delta !== null ? h("small", { class: delta >= 0 ? "up" : "down" }, (delta >= 0 ? "▲ " : "▼ ") + Math.abs(delta) + " in 12 months")
              : h("small", { class: "dim" }, "no ODIs in the last 12 months · last " + C.date(r.last_match))]),
          spark(pts)]),
        w ? h("div", { class: "r-wc" }, [
          h("div", {}, [h("b", {}, pctTxt(p.champion)), h("span", {}, "title")]),
          h("div", {}, [h("b", {}, pctTxt(p.final)), h("span", {}, "final")]),
          h("div", {}, [h("b", {}, pctTxt(p.semi)), h("span", {}, "semi-final")])]) : null,
        h("p", { class: "tiny dim", style: "margin:.4rem 0 .5rem" }, where + (m.asOf ? " Forecast as of " + C.date(m.asOf) + "." : "")),
        h("div", { class: "row", style: "gap:1rem;flex-wrap:wrap" }, [h("a", { class: "small", href: "/cricket/predictor/" }, "Full forecast →"),
          h("a", { class: "small", href: "/cricket/methodology/" }, "How ratings work →")])]);
    } catch (e) { C.showError(target, e, "ratings"); }
  }

  function ratingsCard(scope) {
    const men = team.gender === "male", name = C.fmtName(scope);
    if (men && scope === "ODI" && MODEL_ON) { liveRatings(); return; }
    const [title, badge, text] = men && scope === "ODI"
      ? ["Ratings & ODI World Cup 2027", "Next", "Team ratings and title chances arrive with the ODI World Cup 2027 predictor in the next phase."]
      : men && scope === "T20I"
        ? ["T20I ratings & T20 World Cup 2028", "Later", "T20I team ratings come after the ODI World Cup 2027 predictor. A T20 World Cup 2028 forecast is planned once the ODI World Cup 2027 is over."]
        : [name + " ratings", "Later", (men ? "" : "Women's ") + name + " team ratings come after the men's ODI World Cup 2027 predictor."];
    C.fill("f-ratings", [h("div", { class: "card-head" }, [h("h2", {}, title), h("span", { class: "badge " + (badge === "Next" ? "saff" : "soon") }, badge)]),
      h("p", { class: "dim small" }, text)]);
  }

  async function byFormat(scope) {
    document.querySelectorAll("[data-format]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.format === scope)));
    ratingsCard(scope);
    document.querySelectorAll(".fmt-name").forEach((el) => { el.textContent = C.fmtName(scope); });
    const [h2h, ha, runs, wkts] = ["head-to-head", "home-away", "runs", "wickets"].map((id) => C.fill("f-" + id, h("div", { class: "skeleton", style: "height:80px" })));
    const base = "/v1/teams/" + team.slug;
    const load = async (target, path, render, what) => {
      try { const { data } = await C.api(base + path); C.fill(target, data.length ? render(data) : h("p", { class: "muted", style: "padding:1rem" }, "No matches."));
      } catch (e) { C.showError(target, e, what); }
    };
    const leader = (p, val, sub) => h("li", {}, [C.who(p.full_name || p.name, p.matches + " matches", team.name, "/cricket/players/" + p.slug + "/", null, p.photo_url),
      h("span", { class: "val" }, [val, h("small", {}, sub)])]);
    await Promise.all([
      load(h2h, "/head-to-head?scope=" + scope, (rows) => C.table(["Opponent", "Mat", "Won", "Lost", "Win %", "Last"],
        rows.slice(0, 15).map((r) => [h("div", { class: "who" }, [C.teamBadge(r.opponent.name, "sm"),
          r.opponent.slug ? h("a", { href: "/cricket/countries/" + r.opponent.slug + "/", class: "name" }, r.opponent.name) : r.opponent.name]),
          r.matches, r.won, r.lost, C.ratio(r.win_pct), h("span", { class: "row", style: "justify-content:flex-end;gap:.4rem" },
            [h("span", { class: "tiny dim" }, C.date(r.last_played)), C.formDots([r.last_outcome])])]), { textCols: [0] }), "head to head"),
      load(ha, "/home-away?scope=" + scope, (rows) => h("div", { class: "kpis", style: "padding:.4rem 1.3rem 1.2rem" },
        rows.filter((r) => r.where_played !== "unknown").map((r) => h("div", { class: "kpi" }, [
          h("b", {}, C.ratio(r.win_pct) + "%"),
          h("span", {}, { home: "Home", away: "Away", neutral: "Neutral" }[r.where_played] + " · " + r.matches + " mat")]))),
        "home and away"),
      load(runs, "/top-players?metric=runs&limit=8&scope=" + scope, (rows) => h("ol", { class: "rank" }, rows.map((p) => leader(p, C.num(p.runs), "avg " + C.ratio(p.average)))), "most runs"),
      load(wkts, "/top-players?metric=wickets&limit=8&scope=" + scope, (rows) => h("ol", { class: "rank" }, rows.map((p) => leader(p, p.wickets, "avg " + C.ratio(p.average)))), "most wickets"),
    ]);
  }

  function byFormatView(k) {
    document.querySelectorAll("[data-bf]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.bf === k)));
    document.querySelectorAll("[data-bf-pane]").forEach((p) => { p.hidden = p.dataset.bfPane !== k; });
  }

  async function render() {
    header();
    const body = C.fill("c-body", [
      // Form guide: record, recent results and results by year as tabs on one board (like the hub's Match centre).
      h("section", { class: "section panel", "aria-label": "Form guide" }, h("div", { class: "wrap scoreboard match-centre" }, [
        h("div", { class: "sb-head board-head", "aria-hidden": "true" }, [h("span", { class: "bulb" }), "Form guide",
          h("span", { class: "mc-asof" }, " · " + team.name + " " + GENDER[team.gender].toLowerCase()), h("span", { class: "bulb" })]),
        h("div", { class: "sec-tabs", role: "tablist", "aria-label": "Form guide" }, [
          ["record", "📊 Record by format"], ["recent", "📋 Recent results"], ["years", "📈 Results by year"]].map(([k, n], i) =>
          h("button", { class: "sec-tab", type: "button", role: "tab", id: "tab-" + k, "aria-controls": "pane-" + k,
                        "aria-selected": String(i === 0), tabindex: i === 0 ? null : "-1" }, n))),
        h("div", { class: "sec-pane", role: "tabpanel", id: "pane-record", "aria-labelledby": "tab-record" }, [
          h("div", { class: "section-head", style: "margin-bottom:.8rem" }, [h("div", { class: "section-label", style: "margin:0" }, "Record by format"), h("div", { id: "c-period" })]),
          h("div", { class: "grid", id: "c-formats" }, [h("div", { class: "skeleton" }), h("div", { class: "skeleton" })])]),
        h("div", { class: "sec-pane", role: "tabpanel", id: "pane-recent", "aria-labelledby": "tab-recent", hidden: true }, [
          h("div", { class: "section-head" }, [h("div", {}, [h("div", { class: "section-label" }, "Scorecards"), h("h2", { class: "section-title" }, "Recent results")]),
            h("div", { class: "tabs", role: "group", "aria-label": "Format" }, [["ALL", "All"], ["TEST", "Test"], ["ODI", "ODI"], ["T20I", "T20I"]].map(([k, n]) =>
              h("button", { class: "tab", type: "button", "data-rfmt": k, "aria-pressed": String(k === recentFmt), onclick: () => { recentFmt = k; recent(); } }, n)))]),
          C.carousel(h("div", { class: "strip", id: "c-recent", "aria-live": "polite" }, [h("div", { class: "skeleton" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton" })]), "results"),
          h("div", { class: "row", style: "justify-content:space-between;gap:.6rem" }, [
            h("p", { class: "tiny muted", id: "c-recent-note" }, "Newest first."), h("p", { class: "tiny", id: "c-recent-fresh", hidden: true })])]),
        h("div", { class: "sec-pane", role: "tabpanel", id: "pane-years", "aria-labelledby": "tab-years", hidden: true },
          h("div", { class: "card" }, [h("div", { class: "card-head" }, [h("h2", {}, "Results by year"),
            h("div", { class: "tabs", role: "group", "aria-label": "Results by year format" }, [["", "All"]].concat(FORMATS).map(([k, n]) =>
              h("button", { type: "button", class: "tab", "data-yfmt": k, "aria-pressed": String(k === ""), onclick: () => yearsChart(k) }, n)))]),
            h("div", { class: "chart", id: "years-chart" })]))])),
      h("section", { class: "section panel" }, h("div", { class: "wrap stack" }, [
        h("div", { class: "section-head", style: "margin:1rem 0 0" }, [h("div", {}, [h("div", { class: "section-label" }, "By format"), h("h2", { class: "section-title", style: "margin:0" }, ["Head to head & top performers · ", h("span", { class: "fmt-name" }, "ODI")])]),
          h("div", { class: "tabs", role: "group", "aria-label": "Format" }, FORMATS.map(([k, n]) =>
            h("button", { type: "button", class: "tab", "data-format": k, "aria-pressed": "false", onclick: () => byFormat(k) }, n)))]),
        h("div", { class: "grid" }, [
          h("div", { class: "card accent", id: "f-ratings" }),
          h("div", { class: "card tablecard" }, [h("div", { class: "card-head" }, h("h2", {}, ["Home vs away · ", h("span", { class: "fmt-name" }, "ODI")])), h("div", { id: "f-home-away" })])]),
        // Head to head and top performers share one spot (tabs), to save scrolling.
        h("div", { class: "tabs", role: "group", "aria-label": "Show" }, [["h2h", "🤝 Head to head"], ["top", "⭐ Top performers"]].map(([k, n]) =>
          h("button", { type: "button", class: "tab sm", "data-bf": k, "aria-pressed": String(k === "h2h"), onclick: () => byFormatView(k) }, n))),
        h("div", { class: "card tablecard", "data-bf-pane": "h2h" }, [h("div", { class: "card-head" }, h("h2", {}, ["Head to head · ", h("span", { class: "fmt-name" }, "ODI")])), h("div", { id: "f-head-to-head" })]),
        h("div", { class: "grid", "data-bf-pane": "top", hidden: true }, [
          h("div", { class: "card" }, [h("h2", {}, ["Most runs · ", h("span", { class: "fmt-name" }, "ODI")]), h("div", { id: "f-runs" })]),
          h("div", { class: "card" }, [h("h2", {}, ["Most wickets · ", h("span", { class: "fmt-name" }, "ODI")]), h("div", { id: "f-wickets" })])]),
        h("p", { class: "tiny muted" }, ["Matches with play only; ties and draws count in win % (no results don't). Top performers count only matches for this team. Data as of ",
          h("span", { id: "data-note" }, "…"), ". ", h("a", { href: "/cricket/licences/" }, "What the data covers")])]))]);
    C.sectionTabs(body.querySelector(".sec-tabs"));
    window.addEventListener("resize", () => {   // the chart may be drawn while its tab is hidden
      if (chart && chart.ctx) { try { chart.resize(); } catch (e) { /* not drawable yet */ } }
    });
    try {
      const { data: record, meta } = await C.api("/v1/teams/" + team.slug + "/record");
      C.dataNote(meta);
      asOf = meta.data_as_of;
      await formCards();
      const formats = record.map((r) => r.format);
      // ODI first, as everywhere; a team with no ODIs starts on the format it plays most.
      if (!formats.includes("ODI")) recentFmt = (record.slice().sort((a, b) => b.matches - a.matches)[0] || {}).format || "ALL";
      try { source = (await C.api("/v1/status")).data.source || null; } catch (e) { source = null; }
      recent();
      yearsChart("");
      byFormat(["ODI", "T20I", "TEST"].find((f) => formats.includes(f)) || "ODI");
    } catch (e) { C.showError(body, e, "this team"); }
  }

  async function init() {
    try {
      const { data } = await C.api("/v1/teams?type=international");
      teams = data;
      // A team's own address shows that team; the plain Countries page is the cricket world map.
      const slug = C.pathTail("countries");
      const landing = document.getElementById("c-landing"), hero = document.getElementById("c-hero");
      if (!slug && landing && window.cricstatMap) {
        landing.hidden = false;
        if (hero) hero.hidden = true;
        document.getElementById("c-body").hidden = true;
        window.cricstatMap.init();
        return;
      }
      if (landing) landing.hidden = true;
      if (hero) hero.hidden = false;
      team = teams.find((t) => t.slug === slug) || teams.find((t) => t.slug === "india-men");
      if (!team) throw new Error("unknown team");
      render();
    } catch (e) { C.showError("c-body", e, "teams"); }
  }
  init();
})();
