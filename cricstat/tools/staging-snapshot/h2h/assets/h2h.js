/* cricstat Head to Head (docs/h2h-plan.md, H4). One shell serves the landing page (/cricket/h2h/:
   picker + popular list) and every pair page (/cricket/h2h/<a>-vs-<b>/). Player slugs end in an 8-hex
   Cricsheet id, team slugs end in -men or -women. Every number comes from /cricket/api. */
(function () {
  "use strict";
  const C = window.cricstat, h = C.h;
  const FORMATS = [["ODI", "ODI"], ["TEST", "Test"], ["T20I", "T20I"]];
  const FMT_PLURAL = { ODI: "ODIs", TEST: "Tests", T20I: "T20Is" };
  const GENDERS = [["male", "Men"], ["female", "Women"]];
  const PID = /([0-9a-f]{8})$/;

  // ── URLs ──
  function pairFromPath() {
    const m = location.pathname.match(/^\/cricket\/h2h\/([a-z0-9-]+)-vs-([a-z0-9-]+)\/?$/);
    return m ? [m[1], m[2]] : null;
  }
  const isPlayer = (slug) => PID.test(slug);
  const pidOf = (slug) => slug.match(PID)[1];
  // One page per pair: the two slugs in alphabetical order (the server 301-redirects the reverse in H5).
  function pairUrl(a, b) {
    const [x, y] = [a, b].sort();
    return "/cricket/h2h/" + x + "-vs-" + y + "/";
  }

  // ── Picker ──
  const state = { mode: "players", gender: "male", a: null, b: null, formatTabs: null };

  function seg(options, current, onPick, label) {
    return h("div", { class: "tabs", role: "group", "aria-label": label }, options.map(([k, text]) =>
      h("button", { type: "button", class: "tab", "aria-pressed": String(k === current), onclick: () => onPick(k) }, text)));
  }

  function picker(prefill) {
    if (prefill) Object.assign(state, prefill);
    const box = document.getElementById("h-picker");
    const go = h("button", { class: "btn pri", type: "button", disabled: true }, "Compare");
    const ready = () => { go.disabled = !(state.a && state.b && state.a.slug !== state.b.slug); };
    go.addEventListener("click", () => { if (!go.disabled) location.href = pairUrl(state.a.slug, state.b.slug); });
    const sides = state.mode === "players"
      ? [playerBox("a", "First player", ready), h("span", { class: "h-vs", "aria-hidden": "true" }, "vs"),
         playerBox("b", "Second player", ready)]
      : [countryBox("a", ready), h("span", { class: "h-vs", "aria-hidden": "true" }, "vs"), countryBox("b", ready)];
    C.fill(box, [
      h("div", { class: "h-switches" }, [
        seg([["players", "Players"], ["countries", "Countries"]], state.mode,
            (k) => { if (k !== state.mode) { state.mode = k; state.a = state.b = null; picker(); } }, "Compare players or countries"),
        seg(GENDERS, state.gender,
            (k) => { if (k !== state.gender) { state.gender = k; state.a = state.b = null; picker(); } }, "Men or women"),
        state.formatTabs && state.mode === "players" && state.a && state.b ? state.formatTabs : null,
      ]),
      h("div", { class: "h-row" }, sides.concat([go])),
      h("p", { class: "tiny dim", style: "margin-top:.5rem" }, state.mode === "players"
        ? "Search by name, surname or initials. Once the first player is picked, the second box suggests the players they faced most."
        : "The second list shows only the teams the first one has played, with the number of matches."),
    ]);
    ready();
  }

  // A search-as-you-type box (the Players search API). Side b, when empty, suggests who side a met most.
  function playerBox(side, label, ready) {
    const wrap = h("div", { class: "h-box" });
    const list = h("ul", { class: "h-suggest", role: "listbox", hidden: true });
    const input = h("input", { type: "search", class: "h-input", placeholder: label + " — e.g. Kohli", "aria-label": label,
                               autocomplete: "off", role: "combobox", "aria-expanded": "false" });
    const choose = (p) => {
      state[side] = { slug: p.slug, name: p.full_name || p.name, team: p.main_team, photo: p.photo_url };
      render(); ready();
      if (side === "a" && !state.b) { const next = document.querySelector(".h-box[data-side=b] input"); if (next) next.focus(); }
    };
    const show = (items, title) => {
      list.hidden = !items.length; input.setAttribute("aria-expanded", String(!!items.length));
      C.fill(list, (title ? [h("li", { class: "h-suggest-title", role: "presentation" }, title)] : []).concat(items.map((p) =>
        h("li", { role: "option", tabindex: "-1", onmousedown: (e) => { e.preventDefault(); choose(p); },
                  onkeydown: (e) => { if (e.key === "Enter") choose(p); } },
          C.who(p.full_name || p.name, p.sub || [p.main_team, p.years].filter(Boolean).join(" · "), p.main_team, null, null, p.photo_url)))));
    };
    let timer = null, seq = 0;
    input.addEventListener("input", () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) { suggestFaced(); return; }
      timer = setTimeout(async () => {
        const n = ++seq;
        try {
          const { data } = await C.api("/v1/search?type=player&limit=8&gender=" + state.gender + "&q=" + encodeURIComponent(q));
          if (n === seq) show(data.players || []);
        } catch (e) { show([]); }
      }, 220);
    });
    async function suggestFaced() {
      if (side !== "b" || !state.a) { show([]); return; }
      try {
        const id = pidOf(state.a.slug);
        const all = await Promise.all(FORMATS.map(([f]) => C.api("/v1/h2h/opponents/" + id + "?scope=" + f + "&limit=8")
          .then((r) => r.data).catch(() => [])));
        const by = new Map();
        all.flat().forEach((r) => { const o = by.get(r.player_id) || Object.assign({}, r, { balls: 0 }); o.balls += r.balls; by.set(r.player_id, o); });
        const top = [...by.values()].sort((x, y) => y.balls - x.balls).slice(0, 8)
          .map((r) => Object.assign(r, { sub: C.num(r.balls) + " balls between them" }));
        show(top, top.length ? "Faced " + state.a.name + " most" : null);
      } catch (e) { show([]); }
    }
    input.addEventListener("focus", () => { if (!input.value.trim()) suggestFaced(); });
    input.addEventListener("blur", () => setTimeout(() => show([]), 150));
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { const first = list.querySelector('[role="option"]'); if (first) { e.preventDefault(); first.focus(); } }
      if (e.key === "Escape") show([]);
    });
    list.addEventListener("keydown", (e) => {
      const items = [...list.querySelectorAll('[role="option"]')], i = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown" && i < items.length - 1) { e.preventDefault(); items[i + 1].focus(); }
      if (e.key === "ArrowUp") { e.preventDefault(); (i > 0 ? items[i - 1] : input).focus(); }
    });
    function render() {
      const p = state[side];
      C.fill(wrap, p
        ? h("div", { class: "h-chosen" }, [C.who(p.name, p.team, p.team, null, null, p.photo),
            h("button", { type: "button", class: "h-clear", "aria-label": "Change " + label.toLowerCase(),
                          onclick: () => { state[side] = null; if (side === "a") state.b = null; picker(); } }, "✕")])
        : [input, list]);
    }
    wrap.dataset.side = side;
    render();
    return wrap;
  }

  // Two dropdowns of international teams; side b lists only teams side a has played.
  function countryBox(side, ready) {
    const sel = h("select", { class: "h-select", "aria-label": side === "a" ? "First country" : "Second country" },
      h("option", { value: "" }, side === "a" ? "Choose a country…" : (state.a ? "Choose an opponent…" : "Pick the first country")));
    sel.disabled = side === "b" && !state.a;
    sel.addEventListener("change", () => {
      const o = sel.selectedOptions[0];
      state[side] = sel.value ? { slug: sel.value, name: o.dataset.name } : null;
      if (side === "a") { state.b = null; picker(); } else ready();
    });
    const load = side === "a"
      ? C.api("/v1/teams?type=international&gender=" + state.gender).then(({ data }) =>
          data.sort((x, y) => y.matches - x.matches).map((t) => [t.slug, t.name, t.matches]))
      : state.a ? C.api("/v1/teams/" + state.a.slug + "/head-to-head").then(({ data }) => {
          const by = new Map();
          data.forEach((r) => { const o = by.get(r.opponent.slug) || [r.opponent.slug, r.opponent.name, 0]; o[2] += r.matches; by.set(r.opponent.slug, o); });
          return [...by.values()].sort((x, y) => y[2] - x[2]);
        }) : Promise.resolve([]);
    load.then((rows) => {
      rows.forEach(([slug, name, n]) => sel.appendChild(h("option", { value: slug, "data-name": name }, name + " (" + C.num(n) + " matches)")));
      if (state[side]) sel.value = state[side].slug;
    }).catch(() => {});
    return h("div", { class: "h-box" }, sel);
  }

  // ── Player pair page ──
  const BAT_ROWS = [["Matches", (s) => s.matches, 1], ["Innings", (s) => s.batting && s.batting.innings, 0],
    ["Runs", (s) => s.batting && s.batting.runs, 1], ["Average", (s) => s.batting && s.batting.average, 1, true],
    ["Strike rate", (s) => s.batting && s.batting.strike_rate, 1, true], ["100s", (s) => s.batting && s.batting.hundreds, 1],
    ["50s", (s) => s.batting && s.batting.fifties, 1]];
  const BOWL_ROWS = [["Wickets", (s) => s.bowling && s.bowling.wickets, 1], ["Average", (s) => s.bowling && s.bowling.average, -1, true],
    ["Economy", (s) => s.bowling && s.bowling.economy, -1, true], ["Strike rate", (s) => s.bowling && s.bowling.strike_rate, -1, true]];

  function sideBySide(d) {
    const rows = (defs) => defs.map(([label, get, better, isRatio]) => {
      const va = get(d.a), vb = get(d.b), show = (v) => (isRatio ? C.ratio(v) : C.num(v));
      let wa = false, wb = false;
      if (better && va !== null && va !== undefined && vb !== null && vb !== undefined && va !== vb) {
        wa = better > 0 ? va > vb : va < vb; wb = !wa;
      }
      return h("tr", {}, [h("td", { class: "num" + (wa ? " h-best" : "") }, show(va)), h("th", { scope: "row" }, label),
                          h("td", { class: "num" + (wb ? " h-best" : "") }, show(vb))]);
    });
    const block = (title, defs) => h("div", { class: "card tablecard" }, [h("div", { class: "card-head" }, h("h2", {}, title)),
      h("div", { class: "scroll" }, h("table", { class: "h-sbs" }, [
        h("thead", {}, h("tr", {}, [h("th", { scope: "col", class: "num" }, d.a.player.full_name),
          h("th", { scope: "col" }, ""), h("th", { scope: "col", class: "num" }, d.b.player.full_name)])),
        h("tbody", {}, rows(defs))]))]);
    const anyBowl = (d.a.bowling && d.a.bowling.legal_balls) || (d.b.bowling && d.b.bowling.legal_balls);
    return h("div", { class: "grid-2 h-sbs-grid" }, [block("Batting", BAT_ROWS), anyBowl ? block("Bowling", BOWL_ROWS) : null]);
  }

  function matchupCard(m, batter, bowler, fmt) {
    if (!m) return null;
    const kp = (v, label) => h("div", { class: "kpi" }, [h("b", {}, v), h("span", {}, label)]);
    return h("div", { class: "card h-mu" }, [
      h("div", { class: "card-head" }, [h("h2", {}, bowler + " bowling to " + batter),
        m.small_sample ? h("span", { class: "badge soon", title: "Fewer than 30 balls between them" }, "small sample") : null]),
      h("div", { class: "kpis" }, [kp(C.num(m.balls), "balls"), kp(C.num(m.runs), "runs"), kp(C.num(m.outs), "dismissals"),
        kp(C.ratio(m.average), "average"), kp(C.ratio(m.strike_rate), "strike rate"),
        kp(m.dot_pct === null ? "—" : Math.round(m.dot_pct) + "%", "dot balls"), kp(m.fours + " / " + m.sixes, "4s / 6s")]),
      m.dismissals.length ? h("p", { class: "small", style: "margin-top:.8rem" }, "How " + batter + " got out: " +
        m.dismissals.map((x) => x.n + " " + x.kind).join(", ") + ".") : null,
      h("p", { class: "tiny dim", style: "margin-top:.4rem" }, "In " + C.num(m.matches) + " " + (m.matches === 1 ? FMT_PLURAL[fmt].slice(0, -1) : FMT_PLURAL[fmt]) +
        " from " + C.date(m.first_date) + " to " + C.date(m.last_date) + "."),
    ]);
  }

  // "Head to head in words": neutral sentences from the numbers (H5 also writes them on the server).
  function inWords(d, fmt) {
    const A = d.a.player.full_name, B = d.b.player.full_name, F = FMT_PLURAL[fmt], out = [];
    const ra = d.a.batting && d.a.batting.runs, rb = d.b.batting && d.b.batting.runs;
    const runs = (n) => C.num(n || 0) + (n === 1 ? " run" : " runs");
    if (ra || rb) out.push("In " + F + ", " + A + " has " + runs(ra) + (d.a.batting && d.a.batting.average ? " at an average of " + C.ratio(d.a.batting.average) : "") +
      " and " + B + " has " + runs(rb) + (d.b.batting && d.b.batting.average ? " at " + C.ratio(d.b.batting.average) : "") + ".");
    [[d.matchup.a_batting, A, B], [d.matchup.b_batting, B, A]].forEach(([m, bat, bowl]) => {
      if (m) out.push(bowl + " has bowled " + C.num(m.balls) + " balls to " + bat + " in " + F + ", conceding " + C.num(m.runs) +
        " runs and taking " + (m.outs === 1 ? "1 wicket" : C.num(m.outs) + " wickets") + ".");
    });
    if (!d.matchup.a_batting && !d.matchup.b_batting) out.push("They have not faced each other as batter and bowler in " + F + " in our data.");
    return out.join(" ");
  }

  async function playerPage(sa, sb) {
    const res = document.getElementById("h-result");
    C.fill(res, h("section", { class: "section" }, h("div", { class: "wrap" }, h("p", { class: "loading" }, "Loading the head to head…"))));
    let fmt = new URLSearchParams(location.search).get("f");
    try {
      const [pa, pb, first] = await Promise.all([C.api("/v1/players/" + pidOf(sa)), C.api("/v1/players/" + pidOf(sb)),
        C.api("/v1/h2h/players/" + pidOf(sa) + "/" + pidOf(sb) + "?scope=ODI")]);
      const formats = first.data.formats;
      if (!FORMATS.some(([k]) => k === fmt)) {     // default: where they met most, else ODI
        const top = formats.slice().sort((x, y) => y.balls_between - x.balls_between)[0];
        fmt = top && top.balls_between ? top.scope : "ODI";
      }
      const A = pa.data, B = pb.data;
      document.getElementById("h-title").textContent = (A.full_name || A.name) + " v " + (B.full_name || B.name);
      document.getElementById("h-sub").textContent = "Head to head: careers side by side, and every ball between them as batter and bowler.";
      if (!C.serverHead) document.title = (A.full_name || A.name) + " vs " + (B.full_name || B.name) + ": Head to Head Stats — cricstat";
      picker({ mode: "players", gender: A.gender || "male",
               a: { slug: sa, name: A.full_name || A.name, team: A.main_team && A.main_team.name, photo: A.photo && A.photo.url },
               b: { slug: sb, name: B.full_name || B.name, team: B.main_team && B.main_team.name, photo: B.photo && B.photo.url } });
      const body = h("div", { class: "wrap stack" });
      C.fill(res, h("section", { class: "section", style: "padding-top:0" }, body));
      const tabs = h("div", { class: "tabs h-formats", role: "group", "aria-label": "Format" });
      state.formatTabs = tabs;                      // shown in the picker row, next to Men | Women
      picker();
      const pane = h("div", { class: "stack" });
      const cards = h("div", { class: "grid-2 h-who" }, [A, B].map((p) => h("a", { class: "card", href: "/cricket/players/" + p.slug + "/", style: "padding:1rem" },
        C.who(p.full_name || p.name, C.teamLine(p.main_team && p.main_team.name, [p.main_team && p.main_team.name, C.roleLabel(p.role)].filter(Boolean).join(" · ")),
              p.main_team && p.main_team.name, null, p.role ? C.roleIcon(p.role) : null, p.photo && p.photo.url))));
      C.fill(body, [cards, pane, h("p", { class: "tiny dim" }, "Our data covers men's Tests and ODIs from 2002–03, T20Is from 2005 and women's internationals mostly from 2016 (Cricsheet). Afghanistan men's matches are withheld by Cricsheet, so they are missing here. ",
        h("a", { href: "/cricket/licences/" }, "Data & licences"))]);
      const show = async (k) => {
        fmt = k;
        C.fill(tabs, FORMATS.map(([f, label]) => {
          const n = (formats.find((x) => x.scope === f) || {}).balls_between || 0;
          return h("button", { type: "button", class: "tab", "aria-pressed": String(f === k), onclick: () => show(f) },
            [label, n ? h("small", {}, C.num(n) + " balls") : null]);
        }));
        history.replaceState(null, "", location.pathname + (k === "ODI" ? "" : "?f=" + k));
        C.fill(pane, h("p", { class: "loading" }, "Loading…"));
        try {
          const d = k === "ODI" ? first.data : (await C.api("/v1/h2h/players/" + pidOf(sa) + "/" + pidOf(sb) + "?scope=" + k)).data;
          const An = d.a.player.full_name, Bn = d.b.player.full_name;
          const mus = [matchupCard(d.matchup.a_batting, An, Bn, k), matchupCard(d.matchup.b_batting, Bn, An, k)].filter(Boolean);
          C.fill(pane, [
            h("div", { class: "card h-words" }, [h("div", { class: "section-label" }, "Head to head in words"), h("p", {}, inWords(d, k))]),
            mus.length ? h("div", { class: mus.length > 1 ? "grid-2" : "" }, mus)
              : h("div", { class: "notice" }, "No balls between them as batter and bowler in " + FMT_PLURAL[k] + " in our data."),
            (d.a.matches || d.b.matches) ? sideBySide(d) : h("div", { class: "notice" }, "Neither has played " + FMT_PLURAL[k] + " in our data."),
          ]);
        } catch (e) { C.showError(pane, e, "this head to head"); }
      };
      show(fmt);
    } catch (e) { C.showError(res, e, "this head to head"); }
  }

  // ── Country pair page ──
  async function countryPage(sa, sb) {
    const res = document.getElementById("h-result");
    C.fill(res, h("section", { class: "section" }, h("div", { class: "wrap" }, h("p", { class: "loading" }, "Loading the head to head…"))));
    try {
      const [ta, tb, rec, recent] = await Promise.all([C.api("/v1/teams/" + sa), C.api("/v1/teams/" + sb),
        C.api("/v1/teams/" + sa + "/head-to-head?opponent=" + sb), C.api("/v1/teams/" + sa + "/results?opponent=" + sb + "&limit=10")]);
      const A = ta.data, B = tb.data, G = A.gender === "female" ? " women" : "";
      document.getElementById("h-title").textContent = A.name + " v " + B.name + (G ? " (women)" : "");
      document.getElementById("h-sub").textContent = "Every meeting in our data, by format, and the most recent results.";
      if (!C.serverHead) document.title = A.name + " vs " + B.name + G + ": Head to Head Record — cricstat";
      picker({ mode: "countries", gender: A.gender, a: { slug: sa, name: A.name }, b: { slug: sb, name: B.name } });
      const rows = FORMATS.map(([k]) => rec.data.find((r) => r.format === k)).filter(Boolean);
      const kp = (v, label) => h("div", { class: "kpi" }, [h("b", {}, v), h("span", {}, label)]);
      const card = (r) => h("div", { class: "card" }, [
        h("div", { class: "card-head" }, [h("h2", {}, C.fmtName(r.format) + "s"), h("span", { class: "badge fmt" }, C.num(r.matches) + " matches")]),
        h("div", { class: "kpis" }, [kp(C.num(r.won), A.name + " won"), kp(C.num(r.lost), B.name + " won"),
          r.format === "TEST" ? kp(C.num(r.drawn), "drawn") : kp(C.num(r.no_result), "no result"), kp(C.num(r.tied), "tied")]),
        h("p", { class: "tiny dim", style: "margin-top:.6rem" }, "Last met " + C.date(r.last_played) + ": " +
          ({ won: A.name + " won", lost: B.name + " won", drawn: "drawn", tied: "tied", no_result: "no result" }[r.last_outcome] || "—") + "."),
      ]);
      const words = rows.map((r) => "In " + FMT_PLURAL[r.format] + ", " + A.name + " and " + B.name + " have met " + C.num(r.matches) +
        " times in our data: " + A.name + " won " + C.num(r.won) + ", " + B.name + " won " + C.num(r.lost) +
        (r.format === "TEST" ? ", " + C.num(r.drawn) + " drawn" : "") + (r.tied ? ", " + C.num(r.tied) + " tied" : "") +
        (r.no_result ? ", " + C.num(r.no_result) + " no result" : "") + ".").join(" ");
      const res2 = (m) => {
        const won = m.outcome === "won" ? A.name : m.outcome === "lost" ? B.name : null;
        const by = m.margin_innings ? "an innings and " + m.margin_runs + " runs" : m.margin_runs ? m.margin_runs + " runs" : m.margin_wickets ? m.margin_wickets + " wickets" : "";
        const text = won ? won + " won" + (by ? " by " + by : "") : m.outcome === "drawn" ? "Drawn" : m.outcome === "tied" ? "Tied" : "No result";
        return [C.date(m.date), C.fmtName(m.format), text, [m.venue, m.city].filter(Boolean).join(", ")];
      };
      C.fill(res, h("section", { class: "section", style: "padding-top:0" }, h("div", { class: "wrap stack" }, [
        h("div", { class: "grid-2 h-who" }, [A, B].map((t) => h("a", { class: "card", href: "/cricket/countries/" + t.slug + "/", style: "padding:1rem;display:flex;gap:.8rem;align-items:center" },
          [C.teamBadge(t.name), h("span", { class: "name" }, t.name + (G ? " women" : ""))]))),
        rows.length ? h("div", { class: "card h-words" }, [h("div", { class: "section-label" }, "Head to head in words"), h("p", {}, words)])
          : h("div", { class: "notice" }, A.name + " and " + B.name + " haven't met in Tests, ODIs or T20Is in our data."),
        rows.length ? h("div", { class: "grid-3" }, rows.map(card)) : null,
        recent.data.length ? h("div", { class: "card tablecard" }, [h("div", { class: "card-head" }, h("h2", {}, "Most recent meetings")),
          C.table(["Date", "Format", "Result", "Venue"], recent.data.map(res2), { textCols: [0, 1, 2, 3] })]) : null,
        h("p", { class: "tiny dim" }, "Our data covers men's internationals from 2002–03 and women's mostly from 2016 (Cricsheet), so older meetings aren't counted. ",
          h("a", { href: "/cricket/licences/" }, "Data & licences")),
      ])));
    } catch (e) { C.showError(res, e, "this head to head"); }
  }

  // ── Start ──
  const pair = pairFromPath();
  if (pair && isPlayer(pair[0]) && isPlayer(pair[1])) playerPage(pair[0], pair[1]);
  else if (pair && !isPlayer(pair[0]) && !isPlayer(pair[1])) countryPage(pair[0], pair[1]);
  else {
    // Landing; "Compare with…" links pre-fill side a: ?a=<player slug> or ?a=<team slug>.
    const a = new URLSearchParams(location.search).get("a");
    if (a && isPlayer(a)) {
      C.api("/v1/players/" + pidOf(a)).then(({ data }) => picker({ mode: "players", gender: data.gender || "male",
        a: { slug: data.slug, name: data.full_name || data.name, team: data.main_team && data.main_team.name, photo: data.photo && data.photo.url } }))
        .catch(() => picker());
    } else if (a) {
      C.api("/v1/teams/" + a).then(({ data }) => picker({ mode: "countries", gender: data.gender, a: { slug: data.slug, name: data.name } }))
        .catch(() => picker());
    } else picker();
  }
})();
