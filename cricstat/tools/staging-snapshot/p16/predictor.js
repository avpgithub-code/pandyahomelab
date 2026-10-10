/* ODI World Cup 2027 predictor page (P1.6). Data: /v1/forecasts/wc-2027/latest + /history,
   /v1/ratings, /v1/ratings/<team>/history, /v1/models/predictor/backtest. One model for every
   team: "following" a team (localStorage cricstat:follow, no cookies) changes what is shown first,
   never a number. DOM via textContent only. */
(function () {
  const C = window.cricstat, h = C.h;
  // Categorical slots validated for the dark card surface (#13161e): lightness band, chroma,
  // CVD separation, contrast. Assigned in fixed order to the series, never by team colour.
  const PAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"];
  if (window.Chart) {
    window.Chart.defaults.color = "#94a3b8";
    window.Chart.defaults.borderColor = "#252a38";
    window.Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";
  }
  let F = null, follow = C.getFollow(), charts = {};

  function pct(p, digits) {
    if (p === null || p === undefined) return "—";
    if (p === 0) return "0%";
    if (p < 0.001) return "<0.1%";
    return (100 * p).toFixed(digits === undefined ? 1 : digits) + "%";
  }
  function teamCell(t) {
    const name = t.slug ? h("a", { href: "/cricket/countries/" + t.slug + "/", class: "tname" }, t.team)
      : h("span", { class: "tname" }, t.team);
    return h("span", { class: "wc-team" }, [C.teamBadge(t.team, "sm"), name,
      t.team === "Afghanistan" ? h("sup", { class: "wc-note-mark", title: "Results from a reviewed list: see 'What this forecast can and can't tell you'" }, "†") : null,
      F && (F.tournament.hosts || []).includes(t.team) ? h("span", { class: "wc-host", title: "Host: +" + (((F.model || {}).elo || {}).home || "") + " Elo home advantage in its home matches" }, "🏠") : null]);
  }
  function bar(p, max) {
    return h("span", { class: "wc-bar" }, [h("span", { class: "wc-bar-fill", style: "width:" + Math.max(1.5, 100 * p / (max || 1)).toFixed(1) + "%" }),
      h("span", { class: "wc-bar-val" }, pct(p))]);
  }
  const day = (iso) => C.date(iso);

  // ── Header: stamp + the followed team's line ──
  function stamp() {
    const f = F.forecast;
    C.fill("wc-stamp", ["Elo baseline · " + C.num(f.n_simulations) + " simulated tournaments · updated " + day(f.created_at.slice(0, 10)) +
      " · results to " + day(f.data_as_of) + " · model " + f.model_version]);
    C.fill("wc-asof", " · " + day(f.created_at.slice(0, 10)));
  }
  function followStrip() {
    const t = F.teams.find((x) => x.team_uid === follow) || F.teams.find((x) => x.team_uid === "india-men");
    const sel = h("select", { id: "wc-follow-sel", autocomplete: "off", "aria-label": "Team to follow" },
      F.teams.slice().sort((a, b) => a.team.localeCompare(b.team)).map((x) =>
        h("option", { value: x.team_uid, selected: x.team_uid === t.team_uid ? "selected" : null }, x.team)));
    sel.addEventListener("change", () => { follow = sel.value; C.setFollow(follow); followStrip(); renderDonut(); renderOdds(); renderTime(); renderRatings(); if (SCHED) renderFixtures(); });
    const p = t.probabilities;
    C.fill("wc-follow", h("div", { class: "wc-follow-card" }, [
      h("div", { class: "row", style: "gap:.8rem" }, [C.teamBadge(t.team), h("div", {}, [
        h("div", { class: "wc-follow-big" }, [h("b", {}, pct(p.champion)), " chance that ", h("strong", {}, t.team), " lift the trophy"]),
        h("div", { class: "tiny muted" }, (t.direct_qualifier ? "" : "Reach the World Cup " + pct(p.qualified) + " · ") +
          "Super 7 " + pct(p.super7) + " · semi-final " + pct(p.semi) + " · final " + pct(p.final))])]),
      h("div", { class: "field" }, [h("label", { for: "wc-follow-sel" }, "Following"), sel,
        h("span", { class: "tiny muted" }, "Remembered in this browser only — no cookies")])]));
  }

  // ── Who wins: donut, top five + everyone else (≤ 6 segments: a part-to-whole glance; the table
  //    has the exact numbers). Colours follow the team, not the follow choice. ──
  const OTHER = "#475569";
  function renderDonut() {
    const ranked = F.teams.slice().sort((a, b) => (b.probabilities.champion || 0) - (a.probabilities.champion || 0));
    const top = ranked.slice(0, 5), rest = ranked.slice(5);
    const restP = rest.reduce((s, t) => s + (t.probabilities.champion || 0), 0);
    const me = F.teams.find((x) => x.team_uid === follow) || ranked[0];
    const meInTop = top.some((t) => t.team_uid === me.team_uid);
    const segs = top.map((t, i) => ({ label: t.team, p: t.probabilities.champion || 0, color: PAL[i], uid: t.team_uid }))
      .concat([{ label: "All other " + rest.length + " teams", p: restP, color: OTHER, uid: null }]);
    const canvas = h("canvas", { id: "wc-donut-c", role: "img", "aria-label": segs.map((s) => s.label + " " + pct(s.p)).join(", ") });
    C.fill("wc-donut", [
      h("figcaption", { class: "section-label" }, "Who wins · share of " + C.num(F.forecast.n_simulations) + " simulations"),
      h("div", { class: "wc-donut-box" }, [canvas, h("div", { class: "wc-donut-mid", "aria-hidden": "true" }, [
        h("b", {}, pct(me.probabilities.champion)), h("span", {}, me.team),
        meInTop ? null : h("small", {}, "inside ‘all other teams’")])]),
      h("ul", { class: "wc-donut-legend" }, segs.map((s) => h("li", { class: s.uid === me.team_uid ? "me" : null }, [
        h("i", { style: "background:" + s.color, "aria-hidden": "true" }), h("span", {}, s.label), h("b", {}, pct(s.p))])))]);
    if (charts.donut) charts.donut.destroy();
    if (!window.Chart) return;
    charts.donut = new window.Chart(canvas, { type: "doughnut",
      data: { labels: segs.map((s) => s.label), datasets: [{ data: segs.map((s) => 100 * s.p), backgroundColor: segs.map((s) => s.color),
        borderColor: "#13161e", borderWidth: 2, hoverOffset: 6, offset: segs.map((s) => (s.uid && s.uid === me.team_uid ? 10 : 0)) }] },
      options: { responsive: true, maintainAspectRatio: true, cutout: "64%", layout: { padding: 10 },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => " " + c.label + ": " + c.parsed.toFixed(1) + "% of simulations" } } } } });
  }

  // ── 🏆 Title odds ──
  let oddsView = null;
  function renderOdds() {
    const direct = F.teams.filter((t) => t.direct_qualifier);
    const qual = F.teams.filter((t) => !t.direct_qualifier).sort((a, b) => b.probabilities.qualified - a.probabilities.qualified);
    const max = Math.max.apply(null, F.teams.map((t) => t.probabilities.champion || 0));
    const row = (t, i, q) => h("tr", { class: t.team_uid === follow ? "me" : null }, [
      h("td", { class: "num" }, String(i + 1)), h("td", { class: "txt" }, teamCell(t)),
      h("td", {}, t.group || (q ? "Q" : "—")), h("td", {}, t.rating === null ? "—" : String(Math.round(t.rating))),
      q ? h("td", {}, pct(t.probabilities.qualified)) : null,
      h("td", {}, pct(t.probabilities.super7)), h("td", {}, pct(t.probabilities.semi)),
      h("td", {}, pct(t.probabilities.final)), h("td", { class: "wc-champ" }, bar(t.probabilities.champion || 0, max))]);
    const head = (q) => h("thead", {}, h("tr", {}, ["#", "Team", "Group", "Rating"].concat(q ? ["Reach World Cup"] : [])
      .concat(["Super 7", "Semi-final", "Final", "Champion"]).map((x, i) => h("th", { scope: "col", class: i === 1 ? "txt" : null }, x))));
    const mine = F.teams.find((t) => t.team_uid === follow);
    const view = oddsView || (mine && !mine.direct_qualifier ? "qual" : "direct");
    const tabs = h("div", { class: "tabs", role: "group", "aria-label": "Show" }, [
      ["direct", "Every team's chances"], ["qual", "Through the Qualifier (26 Feb – 21 Mar 2027)"]].map(([k, label]) => {
      const b = h("button", { class: "tab sm", type: "button", "aria-pressed": String(k === view) }, label);
      b.addEventListener("click", () => { oddsView = k; renderOdds(); });
      return b;
    }));
    const body = view === "direct"
      ? [h("p", { class: "tiny muted" }, "The " + direct.length + " teams already in the World Cup."),
        h("div", { class: "scroll" }, h("table", { class: "wc-table", style: "min-width:720px" }, [head(false),
          h("tbody", {}, direct.map((t, i) => row(t, i, false)))]))]
      : [h("p", { class: "tiny muted" }, "Four places are still open. Until the Qualifier is played, each simulation draws them from the candidates by their Elo chances."),
        h("div", { class: "scroll" }, h("table", { class: "wc-table", style: "min-width:780px" }, [head(true),
          h("tbody", {}, qual.map((t, i) => row(t, i, true)))]))];
    C.fill("pane-odds", [
      h("div", { class: "section-head" }, [h("div", {}, [h("div", { class: "section-label" }, "Title odds"),
        h("h2", { class: "section-title" }, "Every team's chances")]),
        h("p", { class: "tiny muted", style: "max-width:420px;margin:0" }, "Share of " + C.num(F.forecast.n_simulations) +
          " simulated tournaments in which each team reached the stage. Title chances add up to 100%, semi-finals to 400% (four places)."
          + ((F.tournament.hosts || []).length ? " 🏠 = host, +" + (((F.model || {}).elo || {}).home || "") + " Elo in its home matches." : ""))]),
      tabs].concat(body));
  }

  // ── 📈 Odds over time ──
  const endLabels = { id: "wcEndLabels", afterDatasetsDraw(chart) {
    const ctx = chart.ctx;
    chart.data.datasets.forEach((ds, i) => {
      const meta = chart.getDatasetMeta(i);
      const pt = meta.data[meta.data.length - 1];
      if (!pt || meta.hidden) return;
      ctx.save(); ctx.fillStyle = "#e2e8f0"; ctx.font = "600 12px system-ui, sans-serif"; ctx.textBaseline = "middle";
      ctx.fillText(ds.label, pt.x + 8, pt.y); ctx.restore();
    });
  } };
  async function renderTime() {
    const target = document.getElementById("pane-time");
    try {
      const [all, mine] = await Promise.all([C.api("/v1/forecasts/wc-2027/history"),
        C.api("/v1/forecasts/wc-2027/history?team=" + encodeURIComponent(follow))]);
      const series = all.data.series;
      const latest = series[series.length - 1].probabilities;
      const top = Object.keys(latest).sort((a, b) => latest[b] - latest[a]).slice(0, 5);
      if (!top.includes(follow) && latest[follow] !== undefined) top.push(follow);
      const name = (uid) => (F.teams.find((t) => t.team_uid === uid) || { team: uid }).team;
      const labels = series.map((s) => day(s.created_at.slice(0, 10)) + (series.length > 1 ? " #" + s.forecast_id : ""));
      const moves = mine.data.series.filter((s) => s.moved_by.length).slice(-8).reverse();
      C.fill(target, [
        h("div", { class: "section-head" }, [h("div", {}, [h("div", { class: "section-label" }, "Odds over time"),
          h("h2", { class: "section-title" }, "How the title chances have moved")]),
          h("p", { class: "tiny muted", style: "max-width:420px;margin:0" }, "A new point appears each morning Cricsheet adds a men's ODI. The history starts on 8 October 2026.")]),
        h("div", { class: "chart-box", style: "height:320px" }, h("canvas", { id: "wc-time", role: "img",
          "aria-label": "Title chances per forecast for " + top.map(name).join(", ") })),
        h("h3", { class: "wc-sub" }, "What moved " + name(follow) + "'s chances"),
        moves.length ? h("ul", { class: "wc-moves" }, moves.map((s) => h("li", {}, [
          h("b", {}, day(s.created_at.slice(0, 10)) + ": " + pct(s.probabilities.champion)), " after ",
          s.moved_by.map((m) => m.team1 + " v " + m.team2 + (m.winner ? " (" + m.winner + " won)" : " (" + m.result.replace("_", " ") + ")")).join("; ")])))
          : h("p", { class: "muted small" }, "No match involving " + name(follow) + " has moved the forecast yet.")]);
      if (charts.time) charts.time.destroy();
      if (!window.Chart) return;
      charts.time = new window.Chart(document.getElementById("wc-time"), { type: "line",
        data: { labels, datasets: top.map((uid, i) => ({ label: name(uid), data: series.map((s) => s.probabilities[uid] === undefined ? null : 100 * s.probabilities[uid]),
          borderColor: PAL[i % PAL.length], backgroundColor: PAL[i % PAL.length], borderWidth: uid === follow ? 3 : 2,
          pointRadius: series.length < 30 ? 4 : 0, pointHoverRadius: 6, tension: 0.2 })) },
        options: { responsive: true, maintainAspectRatio: false, layout: { padding: { right: 110 } },
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { position: "bottom", labels: { boxWidth: 12, boxHeight: 3 } },
            tooltip: { callbacks: { label: (c) => c.dataset.label + ": " + c.parsed.y.toFixed(1) + "%" } } },
          scales: { y: { beginAtZero: true, ticks: { callback: (v) => v + "%" }, grid: { color: "#1c2130" } }, x: { grid: { display: false } } } },
        plugins: [endLabels] });
    } catch (e) { C.showError(target, e, "the forecast history"); }
  }

  // ── 📅 Fixtures + 🏟️ Venues (one request: /fixtures carries both) ──
  let SCHED = null, fxFilter = "all";
  const STAGE = { super_series: "Super Series", group: "Group", super7: "Super 7", semi: "Semi-final", final: "Final" };
  const ORD = ["", "1st", "2nd", "3rd", "4th"];
  function slotLabel(s) {
    let m = s.match(/^([AB])([1-3])$/);
    if (m) return (m[2] === "1" ? "Winner" : ORD[+m[2]]) + " of Group " + m[1];
    if (s === "4TH") return "Best 4th-placed team";
    m = s.match(/^S7-([1-4])$/); if (m) return ORD[+m[1]] + " in the Super 7";
    m = s.match(/^W(\d+)$/); if (m) return "Winner of semi-final " + (+m[1] - 54);
    m = s.match(/^Q([2-4])$/); if (m) return ORD[+m[1]] + " in the Qualifier";
    if (s === "QA" || s === "QB") return "Qualifier " + s[1];
    return s;
  }
  function side(f, k) {
    const name = f[k], slug = f[k + "_slug"];
    const known = F.teams.some((t) => t.team === name);
    if (!known) return h("span", { class: "wc-slot" }, slotLabel(name));
    return h("span", { class: "wc-team" }, [C.teamBadge(name, "sm"), slug ? h("a", { class: "tname", href: "/cricket/countries/" + slug + "/" }, name) : h("span", { class: "tname" }, name)]);
  }
  function chanceBar(f) {
    const c = f.chances;
    if (!c) return h("div", { class: "wc-chance muted tiny" }, f.played ? "" : "Chances once both teams are known");
    const seg = (cls, p, label) => h("span", { class: "wc-seg " + cls, style: "flex-basis:" + (100 * p).toFixed(1) + "%", title: label + ": " + pct(p) });
    const lc = f.last_change;
    const move = (d) => (lc && Math.abs(d) >= 0.05) ? h("small", { class: "wc-move " + (d > 0 ? "up" : "down"),
      title: "Last moved " + day(lc.data_as_of) + " (forecast after that day's matches)" }, (d > 0 ? "▲" : "▼") + Math.abs(d).toFixed(1)) : null;
    const bar = h("div", { class: "wc-chance" }, [h("b", {}, [pct(c.team1, 0), move(lc ? lc.team1_pts : 0)]),
      h("span", { class: "wc-segs", role: "img", "aria-label": f.slot1 + " " + pct(c.team1) + ", tie or no result " + pct(c.tie + c.no_result) + ", " + f.slot2 + " " + pct(c.team2) }, [
        seg("t1", c.team1, f.slot1), seg("nr", c.tie + c.no_result, "Tie or no result"), seg("t2", c.team2, f.slot2)]),
      h("b", {}, [move(lc ? lc.team2_pts : 0), pct(c.team2, 0)])]);
    return lc ? h("div", {}, [bar, h("div", { class: "tiny muted wc-moved" }, "Last moved " + day(lc.data_as_of) + " · points vs the forecast before")]) : bar;
  }
  function renderFixtures() {
    const target = document.getElementById("pane-fixtures");
    const me = (F.teams.find((t) => t.team_uid === follow) || {}).team;
    const filters = [["all", "All 57"], ["A", "Group A"], ["B", "Group B"], ["super_series", "Super Series"], ["super7", "Super 7"], ["ko", "Semis & final"], ["me", "⭐ " + (me || "Following")]];
    const keep = (f) => fxFilter === "all" || (fxFilter === "A" || fxFilter === "B" ? f.stage === "group" && f.group === fxFilter
      : fxFilter === "ko" ? (f.stage === "semi" || f.stage === "final") : fxFilter === "me" ? (f.slot1 === me || f.slot2 === me) : f.stage === fxFilter);
    const list = SCHED.fixtures.filter(keep);
    const tabs = h("div", { class: "tabs", role: "group", "aria-label": "Show" }, filters.map(([k, label]) => {
      const b = h("button", { class: "tab sm", type: "button", "aria-pressed": String(k === fxFilter) }, label);
      b.addEventListener("click", () => { fxFilter = k; renderFixtures(); });
      return b;
    }));
    const days = [];
    list.forEach((f) => { const last = days[days.length - 1]; if (last && last.date === f.date) last.items.push(f); else days.push({ date: f.date, items: [f] }); });
    C.fill(target, [
      h("div", { class: "section-head" }, [h("div", {}, [h("div", { class: "section-label" }, "Fixtures"),
        h("h2", { class: "section-title" }, "57 matches, 2 October – 21 November 2027"),
        h("p", { class: "tiny muted", style: "margin:0" }, "Chances as of " + day(SCHED.forecast.data_as_of) + " · they move only when one of the two teams plays")]), tabs]),
      list.length ? h("div", { class: "wc-days" }, days.map((d) => h("section", { class: "wc-day" }, [
        h("h3", { class: "wc-day-h" }, new Date(d.date + "T00:00:00Z").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" })),
        h("ul", {}, d.items.map((f) => h("li", { class: "wc-fx" + (f.slot1 === me || f.slot2 === me ? " me" : "") }, [
          h("div", { class: "wc-fx-meta" }, [h("span", { class: "badge fmt" }, (STAGE[f.stage] || f.stage) + (f.stage === "group" ? " " + f.group : "")),
            h("span", { class: "tiny muted" }, "Match " + f.match_no + " · " + (f.time || "") + (f.daynight ? " · 🌙 day/night" : "") + " · " + f.city + ", " + f.venue_country)]),
          h("div", { class: "wc-fx-teams" }, [side(f, "slot1"), h("span", { class: "wc-v" }, "v"), side(f, "slot2")]),
          f.played ? h("div", { class: "wc-chance small" }, f.result === "win" ? f.winner + " won" : f.result.replace("_", " ")) : chanceBar(f)])))])))
        : h("p", { class: "muted" }, "No fixtures for this filter yet" + (fxFilter === "me" ? " — " + me + " isn't in the World Cup field yet, or plays only after a stage decides its slot." : ".")),
      h("p", { class: "tiny muted", style: "margin-top:.8rem" }, "Local start times (South Africa and Zimbabwe UTC+2; Namibia UTC+2). Chances: win · tie or no result · win, from today's ratings, home advantage and the host country's October–November no-result rate. " + SCHED.source)]);
  }
  function renderVenues() {
    const target = document.getElementById("pane-venues");
    const card = (v) => {
      const hx = v.history || {};
      const photo = v.photo ? h("figure", { class: "wc-vphoto" }, [h("img", { src: "/cricket/venues/" + v.photo, alt: v.stadium + ", " + v.city, loading: "lazy", width: "640", height: "400" }),
          v.photo_caption ? h("figcaption", { class: "wc-vcap" }, v.photo_caption) : null])
        : h("div", { class: "wc-vphoto none", role: "img", "aria-label": "No free photo of " + v.stadium + " yet" }, [h("span", {}, "🏟️"), h("small", {}, "No freely licensed photo yet")]);
      const credit = v.photo_credit ? h("p", { class: "wc-credit" }, ["Photo: " + (v.photo_credit.author || "unknown") + " · ",
        v.photo_credit.licence_url ? h("a", { href: v.photo_credit.licence_url, rel: "license noopener", target: "_blank" }, v.photo_credit.licence) : v.photo_credit.licence,
        " · ", h("a", { href: v.photo_credit.source, rel: "noopener", target: "_blank" }, /flickr\.com/.test(v.photo_credit.source || "") ? "Flickr" : "Wikimedia Commons")]) : null;
      const order = Object.keys(STAGE);
      const stages = (v.stages_2027 || []).slice().sort((a, b) => order.indexOf(a) - order.indexOf(b)).map((s) => STAGE[s] || s).join(", ");
      return h("article", { class: "card wc-venue" }, [photo, credit,
        h("div", { class: "card-head", style: "margin-top:.6rem" }, [h("h3", {}, v.stadium), v.role ? h("span", { class: "badge saff" }, v.role) : null]),
        h("p", { class: "small dim", style: "margin:0 0 .6rem" }, [C.teamBadge(v.country, "xs"), " " + v.city + ", " + v.country + (v.capacity ? " · " + C.num(v.capacity) + " seats" : "") + (v.note ? " · " + v.note : "")]),
        h("div", { class: "wc-vstats" }, [
          h("div", { class: "kpi" }, [h("b", {}, String(v.matches_2027)), h("span", {}, "2027 matches")]),
          h("div", { class: "kpi" }, [h("b", {}, hx.odis ? String(hx.odis) : "New"), h("span", {}, hx.odis ? "men's ODIs since " + (hx.first || "").slice(0, 4) : "first ODIs in 2027")]),
          h("div", { class: "kpi" }, [h("b", {}, hx.avg_first_innings ? String(hx.avg_first_innings) : "—"), h("span", {}, "avg 1st innings")]),
          h("div", { class: "kpi" }, [h("b", {}, hx.decided ? hx.bat_first_won + "/" + hx.decided : "—"), h("span", {}, "won batting first")])]),
        h("p", { class: "tiny muted", style: "margin:.6rem 0 0" }, stages + (v.day_night_2027 ? " · " + v.day_night_2027 + " day/night" : ""))]);
    };
    C.fill(target, [
      h("div", { class: "section-head" }, [h("div", {}, [h("div", { class: "section-label" }, "Venues"),
        h("h2", { class: "section-title" }, "12 grounds in South Africa, Zimbabwe and Namibia")]),
        h("p", { class: "tiny muted", style: "max-width:440px;margin:0" }, "History: men's ODIs at each ground in the data (including its former names). Averages count full first innings only — 50 overs or all out, no rain rules. Small samples: read as character, not prediction.")]),
      h("div", { class: "grid wc-venues" }, SCHED.venues.map(card)),
      h("p", { class: "tiny muted", style: "margin-top:.8rem" }, SCHED.source)]);
  }
  async function loadSchedule() {
    try {
      SCHED = (await C.api("/v1/forecasts/wc-2027/fixtures")).data;
      renderFixtures(); renderVenues();
    } catch (e) { C.showError("pane-fixtures", e, "the fixtures"); C.showError("pane-venues", e, "the venues"); }
  }

  // ── ⚖️ Ratings ──
  let showAll = false;
  async function renderRatings() {
    const target = document.getElementById("pane-ratings");
    try {
      const [list, hist] = await Promise.all([C.api("/v1/ratings?scope=ODI&gender=male"),
        C.api("/v1/ratings/" + encodeURIComponent(follow) + "/history?scope=ODI").catch(() => null)]);
      const rows = list.data.filter((r) => showAll || r.active);
      const toggle = h("button", { class: "tab sm", type: "button", "aria-pressed": String(showAll) }, showAll ? "Active teams only" : "Show inactive teams too");
      toggle.addEventListener("click", () => { showAll = !showAll; renderRatings(); });
      C.fill(target, [
        h("div", { class: "section-head" }, [h("div", {}, [h("div", { class: "section-label" }, "Ratings"),
          h("h2", { class: "section-title" }, [C.wordmark(), " Elo · men's ODIs ", C.ourModel()]),
          h("p", { class: "tiny muted", style: "margin:.2rem 0 0" }, [C.wordmark(), " own rating, updated daily from every men's ODI since 2002 · tested on every ODI since 2019 before it was played · not the ICC ranking."])]), toggle]),
        h("div", { class: "grid", style: "grid-template-columns:repeat(auto-fit,minmax(320px,1fr));align-items:start" }, [
          h("div", { class: "scroll" }, h("table", { class: "wc-table" }, [
            h("thead", {}, h("tr", {}, ["Rank", "Team", "Rating", "ODIs", "Last ODI"].map((x, i) => h("th", { scope: "col", class: i === 1 ? "txt" : null }, x)))),
            h("tbody", {}, rows.map((r) => h("tr", { class: r.team_uid === follow ? "me" : null }, [
              h("td", { class: "num" }, r.rank ? String(r.rank) : "–"), h("td", { class: "txt" }, teamCell(r)),
              h("td", {}, String(Math.round(r.rating))), h("td", {}, C.num(r.matches)), h("td", {}, day(r.last_match))])))])),
          h("div", {}, [h("h3", { class: "wc-sub", style: "margin-top:0" }, hist ? hist.data.team + "'s rating after every ODI" : ""),
            h("div", { class: "chart-box", style: "height:300px" }, h("canvas", { id: "wc-rating", role: "img", "aria-label": "Rating history" })),
            h("p", { class: "tiny muted" }, "1500 = an average Full Member when the data starts (2002). Ranked: teams with an ODI in the last two years. Change the team with ‘Following’ above.")])]),
      ]);
      if (charts.rating) charts.rating.destroy();
      if (hist && window.Chart) {
        const pts = hist.data.points;
        charts.rating = new window.Chart(document.getElementById("wc-rating"), { type: "line",
          data: { labels: pts.map((p) => p.date), datasets: [{ label: hist.data.team, data: pts.map((p) => p.rating), borderColor: PAL[0],
            backgroundColor: PAL[0], borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.15 }] },
          options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
            plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => day(c[0].label), label: (c) => "Rating " + Math.round(c.parsed.y) } } },
            scales: { x: { ticks: { maxTicksLimit: 8, callback: function (v) { return String(this.getLabelForValue(v)).slice(0, 4); } }, grid: { display: false } },
              y: { grid: { color: "#1c2130" } } } } });
      }
    } catch (e) { C.showError(target, e, "the ratings"); }
  }

  // ── 🗺️ Format ──
  function renderFormat() {
    const t = F.tournament, groups = t.groups || {};
    const slotName = { QA: "Qualifier A", QB: "Qualifier B" };
    const stage = (title, sub, n) => h("li", { class: "wc-stage" }, [h("b", {}, title), h("span", {}, sub), h("small", {}, n)]);
    C.fill("pane-format", [
      h("div", { class: "section-head" }, [h("div", {}, [h("div", { class: "section-label" }, "Format"),
        h("h2", { class: "section-title" }, "14 teams, 54 matches before the semi-finals")]),
        h("p", { class: "tiny muted", style: "max-width:420px;margin:0" }, "Published by the ICC on 15 July 2026 (format) and 1 October 2026 (schedule). The simulator plays every fixture in this order.")]),
      h("ol", { class: "wc-flow" }, [
        stage("Super Series", "Qualifier places 2–4 · round robin in Windhoek · the winner joins the groups", "3 matches"),
        stage("Group stage", "Two groups of six · top three + the best fourth-placed team go through", "30 matches"),
        stage("Super 7", "A fresh round robin · the top four reach the semis", "21 matches"),
        stage("Semi-finals", "1st v 4th (Cape Town) · 2nd v 3rd (Centurion)", "2 matches"),
        stage("Final", "Johannesburg · 21 November 2027", "1 match")]),
      h("div", { class: "grid", style: "margin-top:1rem" }, Object.keys(groups).map((g) => h("div", { class: "card" }, [
        h("div", { class: "card-head" }, [h("h3", {}, "Group " + g)]),
        h("ul", { class: "wc-group" }, groups[g].map((name) => {
          const tm = F.teams.find((x) => x.team === name);
          return h("li", {}, slotName[name] ? h("span", { class: "muted" }, slotName[name] + " (Qualifier winner or Super Series winner)") : (tm ? teamCell(tm) : name));
        }))]))),
      h("h3", { class: "wc-sub" }, "Rules not yet published, and what the simulator assumes"),
      h("ul", { class: "wc-assume" }, (F.assumptions || []).map((a) => h("li", {}, a.replace(/^TBC /, "")))),
      h("p", { class: "tiny muted" }, ["Home advantage applies to " + (t.hosts || []).join(", ") + " in their own country, the same rule as every match. Grounds: ",
        h("span", { class: "wc27" }, "★ WC 2027"), " marks them on match cards across cricstat."])]);
  }

  // ── ✅ How good is it? ──
  async function renderGood() {
    const target = document.getElementById("pane-good");
    try {
      const { data } = await C.api("/v1/models/predictor/backtest");
      const b = data.backtest || {}, ta = b.test_a || {}, tb = (b.test_b || {}).pooled || {}, tc = b.test_c || {};
      const kpi = (title, big, sub) => h("div", { class: "card" }, [h("div", { class: "section-label" }, title), h("div", { class: "kpi" }, [h("b", {}, big), h("span", {}, sub)])]);
      const ll = (x) => x && x.log_loss !== undefined && x.log_loss !== null ? x.log_loss.toFixed(3) : "—";
      C.fill(target, [
        h("div", { class: "section-head" }, [h("div", {}, [h("div", { class: "section-label" }, "Backtests"),
          h("h2", { class: "section-title" }, "Tested on matches it hadn't seen")]),
          h("a", { class: "btn", href: "/cricket/methodology/" }, "Full methodology →")]),
        h("div", { class: "grid-4" }, [
          kpi("Every ODI since 2019", ll(ta.elo), "log loss · win-rate model " + ll(ta.win_rate) + " · coin flip 0.693"),
          kpi("2019 + 2023 World Cups", ll(tb.elo), "log loss on " + ((tb.elo || {}).n || "—") + " matches · win-rate " + ll(tb.win_rate)),
          kpi("Calibration", ta.elo && ta.elo.calibration_slope ? ta.elo.calibration_slope.toFixed(2) : "—", "slope · 1.00 = says 70% when 70% happens"),
          kpi("Favourite won", ta.elo && ta.elo.accuracy ? pct(ta.elo.accuracy, 0) : "—", "of decided ODIs since 2019")]),
        h("p", { class: "small dim", style: "margin-top:1rem" }, "Lower log loss is better. Each year was predicted with settings tuned only on the years before it, and each World Cup from ratings frozen on its eve."),
        h("div", { class: "grid", style: "margin-top:.6rem" }, ["wc2019", "wc2023"].filter((k) => tc[k]).map((k) => {
          const c = tc[k], top = c.teams.slice().sort((a, b) => b.p_champion - a.p_champion);
          const rank = top.findIndex((t) => t.team === c.champion) + 1;
          return h("div", { class: "card" }, [h("div", { class: "card-head" }, [h("h3", {}, (k === "wc2019" ? "2019" : "2023") + " World Cup, simulated on its eve"),
              h("span", { class: "badge live" }, (b.replay && b.replay[k] && b.replay[k].ok) ? "replay ✓" : "")]),
            h("p", { class: "small" }, ["Champion ", h("b", {}, c.champion), ": " + pct(c.p_champion) + " beforehand, the model's #" + rank + " pick (an even guess: " + pct(c.uniform_p_champion, 0) + ")."]),
            h("ol", { class: "rank" }, top.slice(0, 4).map((t) => h("li", {}, [h("span", { class: "name" }, t.team), h("span", { class: "val" }, [pct(t.p_champion), h("small", {}, t.actual_semi ? "reached the semis" : "")])])))]);
        })),
        h("p", { class: "tiny muted", style: "margin-top:.8rem" }, "Two tournaments are too few to prove a forecast right or wrong; the match-level tests above carry the weight.")]);
    } catch (e) { C.showError(target, e, "the backtests"); }
  }

  // ── Limits (always visible) ──
  function renderLimits() {
    const d = F.disclosures;
    const item = (icon, title, text) => h("li", {}, [h("span", { class: "wc-li-icon", "aria-hidden": "true" }, icon), h("div", {}, [h("b", {}, title), " ", text])]);
    C.fill("wc-limits", [h("div", { class: "section-label" }, "Read this first"),
      h("h2", { class: "section-title" }, "What this forecast can and can't tell you"),
      h("ul", { class: "wc-limits-list" }, [
        item("📐", "One model for everyone.", d.model), item("🎲", "Not a tip.", d.not_advice),
        item("🧩", "What it doesn't know.", d.not_used), item("†", "Afghanistan.", d.afghanistan),
        item("📅", "Data.", d.data), item("🎟️", "Qualifier places.", d.qualifier)])]);
  }

  async function init() {
    C.sectionTabs(document.querySelector(".wc-board .sec-tabs"));
    // Hero map: a ground opens the Venues tab (dots are keyboard-reachable too).
    document.querySelectorAll(".wc-hosts .h-ground").forEach((dot) => {
      const name = (dot.querySelector("title") || {}).textContent || "a 2027 ground";
      dot.setAttribute("tabindex", "0");
      dot.setAttribute("role", "button");
      dot.setAttribute("aria-label", name + " — show the venues");
      const go = () => {
        const tab = document.getElementById("tab-venues");
        if (tab) { tab.click(); document.querySelector(".wc-board").scrollIntoView({ behavior: "smooth", block: "start" }); }
      };
      dot.addEventListener("click", go);
      dot.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
    try {
      F = (await C.api("/v1/forecasts/wc-2027/latest")).data;
    } catch (e) { C.showError("pane-odds", e, "the forecast"); return; }
    stamp(); followStrip(); renderDonut(); renderOdds(); renderFormat(); renderLimits();
    renderTime(); renderRatings(); renderGood(); loadSchedule();
    // A chart drawn in a hidden tab has no size: resize when its tab opens.
    document.querySelectorAll(".wc-board [role=tab]").forEach((t) => t.addEventListener("click", () =>
      setTimeout(() => Object.values(charts).forEach((c) => c && c.resize()), 0)));
  }
  init();
})();
