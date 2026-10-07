/* cricstat players page (P0.4): search, profile, career by format, year chart, phases,
   opponents and venues. Player pages live at /cricket/players/<name>-<8-hex id>/. */
(function () {
  "use strict";
  const C = window.cricstat, h = C.h;
  const TABS = [["TEST", "Test"], ["ODI", "ODI"], ["T20I", "T20I"], ["LEAGUES", "Leagues"], ["ALL", "All"]];
  const GENDER = { male: "Men's", female: "Women's" };
  let chart = null, labels = {}, teamName = null, leagueScopes = [];

  if (window.Chart) {
    window.Chart.defaults.color = "#94a3b8";
    window.Chart.defaults.borderColor = "#252a38";
    window.Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";
  }

  async function search(q) {
    const out = C.fill("p-results", h("p", { class: "loading" }, "Searching…"));
    try {
      const { data } = await C.api("/v1/search?type=player&limit=12&q=" + encodeURIComponent(q));
      const players = data.players || [];
      if (!players.length) {
        C.fill(out, h("div", { class: "notice" }, "No player found for “" + q + "”. Try a surname, or initials and a surname (e.g. “S Mandhana”)."));
        return;
      }
      const exact = players.filter((p) => p.match === "exact");
      C.fill(out, [
        h("p", { class: "small dim", style: "margin-bottom:.8rem" },
          exact.length > 1 ? "Several players match “" + q + "” — did you mean:" : "Players matching “" + q + "”:"),
        h("div", { class: "grid-4" }, players.map((p) => h("a", { class: "card", href: "/cricket/players/" + p.slug + "/", style: "padding:1rem" },
          C.who(p.name, C.teamLine(p.main_team, [p.main_team, GENDER[p.gender], p.years, C.num(p.matches) + " matches"].filter(Boolean).join(" · ")), p.main_team)))),
      ]);
    } catch (e) { C.showError(out, e, "search results"); }
  }

  function featured() {
    const names = [["V Kohli", "v-kohli-ba607b88", "India"], ["S Mandhana", "s-mandhana-5d2eda89", "India"],
      ["JJ Bumrah", "jj-bumrah-462411b3", "India"], ["H Kaur", "h-kaur-53cd8da6", "India"],
      ["JE Root", "je-root-a343262c", "England"], ["EA Perry", "ea-perry-be150fc8", "Australia"],
      ["Babar Azam", "babar-azam-8a75e999", "Pakistan"], ["L Wolvaardt", "l-wolvaardt-e60f81c9", "South Africa"]];
    C.fill("p-profile", h("section", { class: "section panel", style: "padding-top:0" }, h("div", { class: "wrap" }, [
      h("div", { class: "section-label" }, "Start here"), h("h2", { class: "section-title" }, "Popular players"),
      h("p", { class: "section-desc" }, "A hand-picked starting point, not a ranking: four India stars and four from other leading" +
        " sides, men and women alike. Use the search above for any of the players in the data."),
      h("div", { class: "grid-4 pop-grid" }, names.map(([n, s, t]) => h("a", { class: "card", href: "/cricket/players/" + s + "/", style: "padding:1rem", "data-id": s.slice(-8) },
        C.who(n, C.teamLine(t, t), t))))])));
    // Roles arrive per player (derived from career figures by the API); cards show without them first.
    names.forEach(([n, s, t]) => C.api("/v1/players/" + s.slice(-8)).then(({ data }) => {
      const card = document.querySelector('#p-profile a[data-id="' + s.slice(-8) + '"]');
      if (card && data.role) C.fill(card, C.who(n, C.teamLine(t, [t, C.roleLabel(data.role)].filter(Boolean).join(" · ")), t, null, C.roleIcon(data.role)));
    }).catch(() => {}));
  }

  // Franchises that renamed (old → current; checked against the data: the old name's last match comes
  // before the new name's first). Display only — the data keeps Cricsheet's names. Barbados is left out:
  // the data shows Tridents → Royals → Tridents again, so it isn't a simple rename.
  const RENAMED = {
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru", "Kings XI Punjab": "Punjab Kings",
    "Delhi Daredevils": "Delhi Capitals", "Rising Pune Supergiants": "Rising Pune Supergiant",
    "St Lucia Zouks": "St Lucia Kings", "St Lucia Stars": "St Lucia Kings",
    "Trinidad & Tobago Red Steel": "Trinbago Knight Riders", "Oval Invincibles": "MI London",
    "Northern Superchargers": "Sunrisers Leeds", "Manchester Originals": "Manchester Super Giants",
  };
  function playedFor(teams) {
    const groups = new Map();
    teams.forEach((t) => {
      const now = RENAMED[t.name] || t.name;
      if (!groups.has(now)) groups.set(now, { name: now, former: [], played: false });
      const g = groups.get(now);
      if (t.name === now) g.played = true; else if (!g.former.includes(t.name)) g.former.push(t.name);
    });
    const list = [...groups.values()].map((g) => g.former.length
      ? (g.played ? g.name + " (formerly " + g.former.join(", ") + ")" : g.former.join(", ")) : g.name);
    if (list.length < 2) return null;
    return h("p", { class: "tiny dim" }, "Played for " + list.slice(0, 8).join(", ") + (list.length > 8 ? "…" : ""));
  }

  function tableCard(title, headers, row, note) {
    return h("div", { class: "card tablecard" }, [h("div", { class: "card-head" }, h("h2", {}, title)),
      row ? C.table(headers, [row]) : h("p", { class: "muted", style: "padding:0 1.3rem 1.1rem" }, "—"),
      note ? h("p", { class: "tiny muted", style: "padding:0 1.3rem 1rem" }, note) : null]);
  }

  async function yearChart(id, scope, mode) {
    const target = document.getElementById("years-chart");
    try {
      const { data } = await C.api("/v1/players/" + id + "/years?scope=" + scope);
      if (chart) { chart.destroy(); chart = null; }
      if (!data.length || !window.Chart) { C.fill(target, h("p", { class: "muted" }, "No yearly data.")); return; }
      C.fill(target, h("canvas", { id: "years-canvas", "aria-label": "Year by year " + mode, role: "img" }));
      const bat = mode === "batting";
      chart = new window.Chart(document.getElementById("years-canvas"), {
        data: { labels: data.map((y) => y.year), datasets: [
          { type: "bar", label: bat ? "Runs" : "Wickets", data: data.map((y) => bat ? y.runs : y.wickets),
            backgroundColor: "rgba(79,127,214,.75)", borderRadius: 6, yAxisID: "y" },
          { type: "line", label: bat ? "Average" : "Economy", data: data.map((y) => bat ? y.average : y.economy),
            borderColor: "#FF9933", backgroundColor: "#FF9933", yAxisID: "y2", spanGaps: true, tension: .3, pointRadius: 3 }] },
        options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
          plugins: { tooltip: { callbacks: { label: (c) => c.dataset.label + ": " + (c.dataset.type === "line" ? C.ratio(c.raw) : C.num(c.raw)) } } },
          scales: { y: { beginAtZero: true, grid: { color: "#1c2130" } },
                    y2: { position: "right", beginAtZero: true, grid: { display: false } }, x: { grid: { display: false } } } } });
    } catch (e) { C.showError(target, e, "year-by-year figures"); }
  }

  async function phases(id, scope) {
    const target = document.getElementById("phases");
    // Leagues adds several leagues together, whose phases don't line up: show the main league's instead.
    if (scope === "LEAGUES" && leagueScopes.length) {
      const main = leagueScopes.slice().sort((a, b) => b.matches - a.matches)[0];
      document.getElementById("phases-title").textContent = "Phase splits · " + (labels[main.scope] || main.scope);
      scope = main.scope;
    }
    if (["ALL", "LEAGUES", "TEST"].includes(scope)) {
      C.fill(target, h("p", { class: "muted small" }, "Phase splits are shown for one limited-overs format or league at a time — pick ODI, T20I or a league."));
      return;
    }
    try {
      const { data } = await C.api("/v1/players/" + id + "/phases?scope=" + scope);
      C.fill(target, data.length ? C.table(["Phase", "Runs", "SR", "Wkts", "Econ"], data.map((p) => [p.label,
        C.num(p.bat_runs), C.ratio(p.bat_strike_rate), p.bowl_wkts, C.ratio(p.bowl_economy)])) : h("p", { class: "muted" }, "No phase data."));
    } catch (e) { C.fill(target, h("p", { class: "muted" }, e.status === 422 ? "No phases in this format." : "Phase splits unavailable.")); }
  }

  // Opponent rows of a renamed franchise are combined under its current name, and the average is
  // recomputed from the summed totals (batting: runs / outs; bowling: runs conceded / wickets).
  function mergeRenamed(rows, bowler) {
    const out = new Map();
    rows.forEach((r) => {
      const key = RENAMED[r.label] || r.label;
      const g = out.get(key);
      if (!g) { out.set(key, Object.assign({}, r, { label: key, slug: key === r.label ? r.slug : null, _names: [r.label] })); return; }
      ["innings", "matches", "runs", "outs", "balls_faced", "legal_balls", "runs_conceded", "wickets"].forEach((k) => {
        if (typeof r[k] === "number") g[k] = (g[k] || 0) + r[k]; });
      if (key === r.label) g.slug = r.slug;
      g._names.push(r.label);
    });
    return [...out.values()].map((g) => {
      if (g._names.length > 1) g.average = bowler ? (g.wickets ? g.runs_conceded / g.wickets : null) : (g.outs ? g.runs / g.outs : null);
      // Only an old name was played against: keep that name, as in "Played for".
      if (!g._names.includes(g.label)) g.label = g._names.join(", ");
      return g;
    });
  }

  async function opponents(id, scope, bowler) {
    const target = document.getElementById("opponents");
    try {
      const [opp, ven] = await Promise.all([C.api("/v1/players/" + id + "/splits?by=opponent&scope=" + scope),
        C.api("/v1/players/" + id + "/splits?by=venue&scope=" + scope)]);
      const kind = bowler ? "bowling" : "batting";
      const rows = mergeRenamed(opp.data[kind], bowler).filter((r) => r.innings >= 3 && r.average !== null);
      const by = (a, b) => bowler ? a.average - b.average : b.average - a.average;
      const item = (r) => h("li", {}, [h("div", { class: "who" }, [C.teamBadge(r.label, "sm"),
        r.slug ? h("a", { href: "/cricket/countries/" + r.slug + "/", class: "name" }, r.label) : h("span", { class: "name" }, r.label)]),
        h("span", { class: "val" }, [C.ratio(r.average), h("small", {}, r.innings + " inns")])]);
      const venues = ven.data.batting.concat(ven.data.bowling).reduce((m, r) => { m[r.label] = Math.max(m[r.label] || 0, r.matches); return m; }, {});
      const top = Object.entries(venues).sort((a, b) => b[1] - a[1]).slice(0, 5);
      C.fill(target, [
        rows.length ? h("div", { class: "grid", style: "grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1.2rem" }, [
          h("div", {}, [h("div", { class: "section-label" }, "Best against (" + (bowler ? "bowling" : "batting") + " avg)"), h("ol", { class: "rank" }, rows.slice().sort(by).slice(0, 3).map(item))]),
          h("div", {}, [h("div", { class: "section-label" }, "Toughest"), h("ol", { class: "rank" }, rows.slice().sort(by).reverse().slice(0, 3).map(item))])])
          : h("p", { class: "muted small" }, "Not enough innings against any one team (min 3)."),
        h("div", { class: "section-label", style: "margin-top:1.2rem" }, "Most-played venues"),
        h("ol", { class: "rank" }, top.map(([v, n]) => h("li", {}, [h("span", { class: "name" }, v), h("span", { class: "val" }, [n, h("small", {}, "matches")])])))]);
    } catch (e) { C.showError(target, e, "opponents and venues"); }
  }

  async function showScope(p, scope) {
    document.querySelectorAll("[data-scope]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.scope === scope)));
    const body = C.fill("p-format", h("div", { class: "skeleton" }));
    try {
      const { data: c, meta } = await C.api("/v1/players/" + p.player_id + "/career?scope=" + scope);
      C.dataNote(meta);
      const name = labels[scope] || scope;
      const bowler = p.role === "bowler";
      // Leagues tab: a "League" first column with one row per league (most matches first), then the total.
      const perLeague = scope === "LEAGUES" && leagueScopes.length;
      let rows = [[null, c]];
      if (perLeague) {
        const each = await Promise.all(leagueScopes.map((s) => C.api("/v1/players/" + p.player_id + "/career?scope=" + s.scope).then(({ data }) => [s, data])));
        each.sort((a, b) => b[1].matches - a[1].matches);
        rows = each.concat(each.length > 1 ? [["total", c]] : []);
      }
      const DASH = "–";
      const label = (s) => s === "total" ? h("b", {}, "All leagues")
        : h("button", { type: "button", class: "link-btn", onclick: () => showScope(p, s.scope) }, labels[s.scope] || s.scope);
      const batRow = (x) => { const b = x.batting; return b ? [C.num(x.matches), C.num(b.innings), C.num(b.not_outs), C.num(b.runs), C.hs(b.high_score, b.high_score_not_out),
        C.ratio(b.average), C.ratio(b.strike_rate), b.hundreds, b.fifties, C.num(b.fours), C.num(b.sixes)] : [C.num(x.matches)].concat(Array(10).fill(DASH)); };
      const bowlRow = (x) => { const w = x.bowling; return w ? [w.overs_display, C.num(w.wickets), C.ratio(w.average), C.ratio(w.economy), C.ratio(w.strike_rate),
        w.wickets ? C.bbi(w.best) : DASH, w.five_wkt_hauls] : Array(7).fill(DASH); };
      const fldRow = (x) => { const f = x.fielding; return f ? [f.catches, f.stumpings, f.run_out_involvements] : Array(3).fill(DASH); };
      const card = (title, headers, make, note, need) => {
        const data = rows.filter(([, x]) => !need || x[need] || perLeague);
        if (!rows.some(([, x]) => x[need])) return tableCard(title, headers, null, null);
        const t = C.table((perLeague ? ["League"] : []).concat(headers),
          data.map(([s, x]) => (perLeague ? [label(s)] : []).concat(make(x))), { textCols: perLeague ? [0] : [] });
        if (perLeague && rows.length > 1) t.querySelector("tbody tr:last-child").classList.add("total");
        return h("div", { class: "card tablecard" }, [h("div", { class: "card-head" }, h("h2", {}, title)), t,
          note ? h("p", { class: "tiny muted", style: "padding:0 1.3rem 1rem" }, note) : null]);
      };
      const fnote = c.fielding ? "* " + c.fielding.notes.run_out_involvements : null;
      const batting = card("Batting · " + name, ["Mat", "Inns", "NO", "Runs", "HS", "Avg", "SR", "100s", "50s", "4s", "6s"], batRow, null, "batting");
      const bowling = card("Bowling · " + name, ["Overs", "Wkts", "Avg", "Econ", "SR", "BBI", "5w"], bowlRow, null, "bowling");
      const fielding = card("Fielding · " + name, ["Catches", "Stumpings", "Run-outs*"], fldRow, fnote, "fielding");
      C.fill(body, [
        batting,
        perLeague ? bowling : null,
        perLeague ? fielding : h("div", { class: "grid" }, [bowling, fielding]),
        h("div", { class: "card" }, [
          h("div", { class: "card-head" }, [h("h2", {}, "Year by year"),
            h("div", { class: "tabs", role: "group", "aria-label": "Chart" }, ["batting", "bowling"].map((m) =>
              h("button", { type: "button", class: "tab", "data-mode": m, "aria-pressed": String(m === (bowler ? "bowling" : "batting")),
                onclick: (ev) => { document.querySelectorAll("[data-mode]").forEach((x) => x.setAttribute("aria-pressed", String(x === ev.currentTarget)));
                  yearChart(p.player_id, scope, m); } }, m === "batting" ? "Runs & average" : "Wickets & economy")))]),
          h("div", { class: "chart", id: "years-chart" })]),
        h("div", { class: "grid" }, [
          h("div", { class: "card tablecard" }, [h("div", { class: "card-head" }, h("h2", { id: "phases-title" }, "Phase splits")), h("div", { id: "phases", style: "padding:0 1.3rem 1.1rem" }, h("p", { class: "loading" }, "Loading…"))]),
          h("div", { class: "card" }, [h("h2", {}, "Opponents & venues"), h("div", { id: "opponents" }, h("p", { class: "loading" }, "Loading…"))])]),
      ]);
      yearChart(p.player_id, scope, bowler ? "bowling" : "batting");
      phases(p.player_id, scope);
      opponents(p.player_id, scope, bowler);
    } catch (e) { C.showError(body, e, "career figures"); }
  }

  async function headline(p) {
    const target = document.getElementById("p-kpis");
    try {
      const { data: c } = await C.api("/v1/players/" + p.player_id + "/career?scope=ALL");
      const b = c.batting || {}, w = c.bowling || {}, f = c.fielding || {};
      const k = (v, l) => h("div", { class: "kpi" }, [h("b", {}, v), h("span", {}, l)]);
      C.fill(target, [k(C.num(c.matches), "Matches"), k(C.num(b.runs || 0), "Runs"), k(C.ratio(b.average), "Bat avg"),
        k(String(b.hundreds || 0), "Hundreds"), k(C.num(w.wickets || 0), "Wickets"),
        k(String((f.catches || 0) + (f.stumpings || 0)), "Dismissals")]);
    } catch (e) { C.fill(target, null); }
  }

  async function profile(id) {
    const out = C.fill("p-profile", h("div", { class: "wrap" }, h("div", { class: "skeleton" })));
    try {
      const [{ data: p, meta }, scopesRes] = await Promise.all([C.api("/v1/players/" + id), C.api("/v1/meta/scopes")]);
      scopesRes.data.forEach((s) => { labels[s.scope] = s.label; });
      labels.ALL = "All"; labels.LEAGUES = "Leagues";
      document.title = p.name + " — career statistics | cricstat";
      document.getElementById("p-search").placeholder = "Search another player";
      const played = new Map(p.scopes.map((s) => [s.scope, s.matches]));
      const leagues = p.scopes.filter((s) => scopesRes.data.some((x) => x.scope === s.scope && x.kind === "league"));
      leagueScopes = leagues;
      const tabs = TABS.filter(([k]) => played.has(k));
      const start = ["TEST", "ODI", "T20I", "LEAGUES"].filter((k) => played.has(k)).sort((a, b) => played.get(b) - played.get(a))[0] || "ALL";
      const team = p.main_team;
      teamName = team ? team.name : null;
      const chips = [team ? h("span", { class: "badge saff team-badge" }, C.teamLine(team.name, team.name)) : null, h("span", { class: "badge fmt" }, GENDER[p.gender] || ""),
        p.role ? h("span", { class: "badge soon role-badge", title: "Derived from career figures" }, [C.roleIcon(p.role), C.roleLabel(p.role) || p.role]) : null,
        h("span", { class: "badge soon" }, (p.first_date || "").slice(0, 4) + "–" + (p.last_date || "").slice(0, 4))];
      C.fill(out, [
        h("section", { class: "section", style: "padding-top:0" }, h("div", { class: "wrap" }, h("div", { class: "card accent", style: "padding:1.8rem;background:linear-gradient(135deg,rgba(19,71,163,.28),rgba(19,22,30,1) 55%)" }, [
          h("div", { class: "row", style: "gap:1.5rem;align-items:center" }, [C.avatar(p.name, teamName, "lg"),
            h("div", { class: "stack", style: "gap:.5rem;flex:1 1 280px" }, [
              h("h1", { style: "font-size:clamp(1.8rem,4vw,2.6rem);font-weight:800;letter-spacing:-.02em" }, p.name),
              h("div", { class: "row", style: "gap:.4rem" }, chips),
              playedFor(p.teams),
              p.bio && p.bio.date_of_birth ? h("p", { class: "tiny dim" }, "Born " + C.date(p.bio.date_of_birth) + (p.bio.birthplace ? ", " + p.bio.birthplace : "") + " · via Wikidata") : null]),
            team && team.team_type === "international" && team.slug ? h("a", { class: "btn ghost", href: "/cricket/countries/" + team.slug + "/" }, [C.teamBadge(team.name, "sm"), team.name + " team page"]) : null]),
          h("div", { class: "kpis", id: "p-kpis", style: "margin-top:1.6rem;padding-top:1.2rem;border-top:1px solid var(--border)" })]))),
        h("section", { class: "section panel" }, h("div", { class: "wrap stack" }, [
          h("div", { class: "tabs", role: "group", "aria-label": "Format" }, tabs.map(([k, n]) =>
            h("button", { type: "button", class: "tab", "data-scope": k, "aria-pressed": "false", onclick: () => showScope(p, k) }, [n, h("small", {}, String(played.get(k)))]))),
          leagues.length ? h("div", { class: "tabs", role: "group", "aria-label": "League" }, leagues.map((s) =>
            h("button", { type: "button", class: "tab", "data-scope": s.scope, "aria-pressed": "false", onclick: () => showScope(p, s.scope) }, [labels[s.scope], h("small", {}, String(s.matches))]))) : null,
          h("div", { id: "p-format", class: "stack" }),
          h("p", { class: "tiny muted" }, ["Derived from Cricsheet ball-by-ball data as of ", h("span", { id: "data-note" }, C.date(meta.data_as_of)),
            ". Averages and rates are cut to two decimals. Coverage gaps (early years, Afghanistan matches) can make totals differ from official records. ",
            h("a", { href: "/cricket/licences/" }, "What the data covers")])]))]);
      headline(p);
      showScope(p, start);
    } catch (e) {
      if (e.status === 404) C.fill(out, h("div", { class: "wrap" }, h("div", { class: "notice" }, "There's no player at this address. Search for a player above.")));
      else C.showError(out, e, "this player");
    }
  }

  const params = new URLSearchParams(location.search);
  const q = params.get("q"), id = C.playerIdFromPath();
  if (q) { document.getElementById("p-search").value = q; search(q); }
  if (id) profile(id); else if (!q) featured();
})();
