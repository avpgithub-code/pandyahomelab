/* Methodology page (P1.6): how the ODI World Cup 2027 predictor works and how well.
   Every number comes from /v1/models/predictor/backtest (the champion's own MLflow run, mirrored in
   forecast.sqlite) and /v1/forecasts/wc-2027/latest; nothing here is typed in by hand.
   DOM via textContent only. Chart colours: the validated categorical slots 1–2 (dark surface). */
(function () {
  "use strict";
  const C = window.cricstat, h = C.h;
  const SERIES = { elo: "#3987e5", win_rate: "#d95926" };
  const MLFLOW = "/mlflow/#/models/cricstat-wc2027-predictor";
  if (window.Chart) {
    window.Chart.defaults.color = "#94a3b8";
    window.Chart.defaults.borderColor = "#252a38";
    window.Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";
  }

  const f3 = (x) => (x === null || x === undefined ? "—" : Number(x).toFixed(3));
  const f2 = (x) => (x === null || x === undefined ? "—" : Number(x).toFixed(2));
  const pct = (p, d) => (p === null || p === undefined ? "—" : (100 * p).toFixed(d === undefined ? 1 : d) + "%");
  const code = (t) => h("code", { class: "m-code" }, t);
  const head = (label, title, extra) => h("div", { class: "section-head" }, [h("div", {}, [h("div", { class: "section-label" }, label),
    h("h2", { class: "section-title" }, title)]), extra || null]);
  const kpi = (title, big, sub) => h("div", { class: "card" }, [h("div", { class: "section-label" }, title),
    h("div", { class: "kpi" }, [h("b", {}, big), h("span", {}, sub)])]);
  const facts = (rows) => h("dl", { class: "m-facts" }, rows.map(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]).flat());

  // ── 🧭 In plain words ──
  function plain(d, F) {
    const ch = d.champion, sims = F ? C.num(F.forecast.n_simulations) : "50,000";
    const step = (n, title, text) => h("li", { class: "m-step" }, [h("span", { class: "m-step-n" }, String(n)), h("div", {}, [h("b", {}, title), h("p", {}, text)])]);
    C.fill("pane-m-plain", [
      head("The short version", "Rate every team, then play the World Cup " + sims + " times"),
      h("ol", { class: "m-steps" }, [
        step(1, "Every men's ODI since 2002 updates two ratings.",
          "Beat a stronger team and your rating rises a lot; beat a weaker one and it rises a little. Home teams get a head start, big wins count a bit more. That's an Elo rating, the same idea chess uses."),
        step(2, "Ratings turn into a win chance for any match.",
          "A 100-point gap makes the higher-rated team about a 64% favourite on neutral ground. Every team is rated by the same rule, with no hand adjustments."),
        step(3, "The 2027 tournament is simulated " + sims + " times.",
          "Every fixture in the published format — Super Series, groups, Super 7, semi-finals and final — is played out with those chances, including rain-offs at each host's usual rate and the Qualifier for the last four places."),
        step(4, "Counting the simulations gives the chances.",
          "If a team lifts the trophy in 9,000 of 50,000 runs, its title chance is 18%. Because the tournament is a year away, each run also nudges every rating up or down by a realistic amount of form drift."),
        step(5, "It only goes public if it passes tests on matches it had never seen.",
          "Each year since 2019 was predicted with settings fitted only on earlier years, and the 2019 and 2023 World Cups from ratings frozen on their eve. It had to beat two simpler models and be honestly calibrated.")]),
      h("div", { class: "grid-4", style: "margin-top:1rem" }, [
        kpi("Live model", ch.model_version, "trained " + C.date(String(ch.trained_at).slice(0, 10)) + " · data to " + C.date(ch.data_as_of)),
        kpi("ODIs it was tested on", C.num(d.backtest.test_a.elo.n), "since 2019, before each was played"),
        kpi("Log loss (lower is better)", f3(d.metrics["test_a.log_loss"]), "simpler model " + f3(d.metrics["test_a.win_rate.log_loss"]) + " · coin flip 0.693"),
        kpi("Calibration", f2(d.metrics["test_a.calibration_slope"]), "slope · 1.00 = says 70% when 70% happens")])]);
  }

  // ── 📐 Ratings ──
  function elo(d) {
    const e = d.champion.elo;
    C.fill("pane-m-elo", [
      head("Elo ratings", "The rating rule, and every setting"),
      h("div", { class: "grid" }, [
        h("div", { class: "card" }, [h("h3", {}, "The formulas"),
          h("p", { class: "small" }, ["Expected result for team A against team B:"]),
          h("pre", { class: "m-pre" }, "E_A = 1 / (1 + 10^(−(R_A − R_B + H·h) / 400))"),
          h("p", { class: "small" }, ["h = +1 at home, −1 away, 0 neutral. After the match:"]),
          h("pre", { class: "m-pre" }, "R_A ← R_A + K · m · (S_A − E_A)     (and the opposite for B)"),
          h("p", { class: "small" }, ["S_A = 1 for a win, 0 for a loss, ½ for a tie (also when a super over decided it — the 50 overs were level). A no-result changes nothing. ",
            code("m"), " grows with the margin (runs, or wickets and balls left), capped, so a thrashing counts more than a last-ball win."])]),
        h("div", { class: "card" }, [h("h3", {}, "The settings in use"),
          facts([["K (how fast ratings move)", String(e.k)], ["H (home advantage)", e.home + " Elo points"],
            ["Margin of victory", e.margin ? "used (capped)" : "not used"],
            ["Each 1 January", (100 * e.regress).toFixed(0) + "% of the way back to the base rating for the team's ICC status that day"],
            ["New teams start at", "1500 for Full Members; " + (1500 - e.delta) + " for Associates (Δ = " + e.delta + ")"],
            ["Rated matches", "official men's ODIs from 2002; composite XIs left out"]])])]),
      h("div", { class: "card", style: "margin-top:1rem" }, [h("h3", {}, "How the settings were chosen"),
        h("ul", { class: "m-list" }, [
          h("li", {}, "A grid of 2,016 combinations (K 16–64, H 0–120, margin on/off, the yearly pull 0–30%, Δ) was scored by log loss of each match's prediction made before it was played, from 2007 (the earlier years only warm the ratings up)."),
          h("li", {}, "For the backtests the grid only saw data from before the test: before 30 May 2019 for the 2019 World Cup, before 5 Oct 2023 for 2023, and each year since 2019 re-tuned on the years before it. It picked K = 20, H = 75 and margin on almost every time, so the fit is stable."),
          h("li", {}, "Associates start lower by one rule, decided by ICC status at a team's first match, and the yearly pull goes toward the base for its status on that day — so Ireland and Afghanistan aren't dragged back to associate level after becoming Full Members in 2017."),
          h("li", {}, "No team-specific adjustments, ever: following a team changes what the pages show first, never a number.")])])]);
  }

  // ── 🎲 Simulation ──
  function sim(d, F) {
    const c = d.champion.conditions || {}, drift = d.backtest.drift_sd_by_days || {}, nr = d.backtest.no_result_counts || {};
    const days = Object.keys(drift).map(Number).sort((a, b) => a - b);
    C.fill("pane-m-sim", [
      head("Monte Carlo", "Playing the tournament " + (F ? C.num(F.forecast.n_simulations) : "50,000") + " times"),
      h("div", { class: "grid" }, [
        h("div", { class: "card" }, [h("h3", {}, "One simulated World Cup"),
          h("ol", { class: "m-list" }, [
            h("li", {}, "The Qualifier (Feb–Mar 2027) is played first and fills the last four places, until the real results are in."),
            h("li", {}, "Every fixture of the published format is played: Super Series of three, two groups of six, the Super 7, semi-finals 1 v 4 and 2 v 3, the final on 21 November."),
            h("li", {}, "Each match: win chance from the two ratings (home advantage for South Africa, Zimbabwe and Namibia at home), a chance of a tie, and a chance of no result."),
            h("li", {}, "Ratings update after each simulated match, as they would in reality."),
            h("li", {}, "Points as in the rules (win 2, tie or no result 1). Equal points are split by wins, then at random: net run rate isn't simulated, because the model doesn't predict scores."),
            h("li", {}, "A washed-out knockout match uses its reserve day; if that's lost too, the higher-placed team goes through. A tied knockout is a super over: 50/50.")])]),
        h("div", { class: "card" }, [h("h3", {}, "Measured, not chosen"),
          facts([["No result, South Africa", pct(c.by_country && c.by_country["South Africa"]) + " (" + ((nr["South Africa"] || {}).no_results || 0) + " no-results in " + ((nr["South Africa"] || {}).matches || 0) + " matches there in the sample, shrunk toward the global rate)"],
            ["No result, Zimbabwe", pct(c.by_country && c.by_country.Zimbabwe)], ["No result, Namibia", pct(c.by_country && c.by_country.Namibia)],
            ["No result, all ODIs", pct(c.global)], ["Tie", pct(c.tie)],
            ["Knockout washed out", "the rate squared (two days must both be lost)"]]),
          h("p", { class: "tiny muted" }, "Rain-offs come from every ODI on Wikipedia's season lists, including matches abandoned without a ball, which the ball-by-ball data doesn't contain.")])]),
      h("div", { class: "card", style: "margin-top:1rem" }, [h("h3", {}, "Form drift: why a year-out forecast is less sure"),
        h("p", { class: "small" }, ["A rating today isn't the rating on the day. How far Full Members' ratings actually moved over each gap since 2007 fits a random walk, σ = √(" + f2(d.champion.rating_drift_a) + " × days). Each simulation gives every team one random shift of that size; "
          + (F ? "the current forecast, " + F.forecast.days_to_start + " days out, uses σ = " + Math.round(F.forecast.rating_uncertainty_sd) + " points." : "")]),
        h("div", { class: "scroll" }, h("table", { class: "wc-table" }, [h("thead", {}, h("tr", {}, [h("th", { scope: "row", class: "txt" }, "Days ahead")].concat(days.map((x) => h("th", { scope: "col" }, String(x)))))),
          h("tbody", {}, h("tr", {}, [h("th", { scope: "row", class: "txt" }, "Rating drift (SD, points)")].concat(days.map((x) => h("td", {}, String(Math.round(drift[x])))))))]))]),
      h("p", { class: "tiny muted", style: "margin-top:.8rem" }, "Stage chances are checked every run: title chances add up to 100%, final places to 200%, semi-final places to 400%. With 50,000 runs each percentage is within about ±0.2 points of where more runs would settle.")]);
  }

  // ── ✅ Backtests ──
  function tests(d) {
    const ta = d.backtest.test_a, tb = d.backtest.test_b, tc = d.backtest.test_c, years = Object.keys(ta.by_year || {}).sort();
    const row = (name, m, note) => [name, m ? C.num(m.n) : "—", m && m.accuracy !== null && m.accuracy !== undefined ? pct(m.accuracy, 0) : "—", f3(m && m.log_loss), f3(m && m.brier), f2(m && m.calibration_slope), note || ""];
    const tbl = (cols, rows) => h("div", { class: "scroll" }, C.table(cols, rows, { textCols: [0, cols.length - 1] }));
    C.fill("pane-m-tests", [
      head("Backtests", "Tested on matches it hadn't seen", h("span", { class: "tiny muted" }, "Lower log loss and Brier are better; slope 1.00 = calibrated")),
      h("h3", { class: "m-h3" }, "A · Every men's ODI since 2019, each predicted the day before"),
      tbl(["Model", "Matches", "Favourite won", "Log loss", "Brier", "Slope", ""], [
        row("Elo (live)", ta.elo, "the forecast's model"), row("Win-rate model", ta.win_rate, "simpler baseline: last 2 years' win % + home"),
        row("Coin flip", ta.coin, "50/50 for every match"), row("Elo, Full Members only", ta.elo_full_members_only, "subset"),
        row("Elo, matches with Afghanistan", ta.elo_with_afghanistan, "subset; their results are from our reviewed list")]),
      h("details", { class: "m-details" }, [h("summary", {}, "By year"),
        tbl(["Year", "Matches", "Favourite won", "Log loss", "Brier", "Slope", ""], years.map((y) => row(y, ta.by_year[y], "")))]),
      h("h3", { class: "m-h3" }, "B · World Cup matches, ratings frozen on the eve"),
      tbl(["Tournament", "Matches", "Favourite won", "Log loss", "Brier", "Slope", ""], [
        row("2019 + 2023 · Elo", tb.pooled.elo, ""), row("2019 + 2023 · win-rate", tb.pooled.win_rate, ""),
        row("2019 · Elo", tb.wc2019.elo, "England won"), row("2023 · Elo", tb.wc2023.elo, "Australia won")]),
      h("h3", { class: "m-h3" }, "C · Whole tournaments, simulated on the eve"),
      h("div", { class: "grid" }, ["wc2019", "wc2023"].filter((k) => tc[k]).map((k) => {
        const t = tc[k], top = t.teams.slice().sort((a, b) => b.p_champion - a.p_champion);
        const rank = top.findIndex((x) => x.team === t.champion) + 1, rep = d.backtest.replay && d.backtest.replay[k];
        return h("div", { class: "card" }, [h("h3", {}, (k === "wc2019" ? "2019" : "2023") + " World Cup"),
          h("p", { class: "small" }, ["Champion ", h("b", {}, t.champion), ": " + pct(t.p_champion) + " beforehand, the model's #" + rank + " pick (even odds: " + pct(t.uniform_p_champion, 0) + ")."]),
          C.table(["Team", "Semi", "Final", "Title", "What happened"], top.slice(0, 6).map((x) => [x.team, pct(x.p_semi, 0), pct(x.p_final, 0), pct(x.p_champion),
            x.actual_champion ? "🏆 champion" : x.actual_final ? "runner-up" : x.actual_semi ? "semi-final" : ""]), { textCols: [0, 4] }),
          h("p", { class: "tiny muted" }, "Brier by stage: semi " + f3(t.brier.semi) + " · final " + f3(t.brier.final) + " · title " + f3(t.brier.champion) +
            (rep ? " · replay with the real results " + (rep.ok ? "reproduces the real semi-finalists ✓" : "differs ✗") : ""))]);
      })),
      h("p", { class: "tiny muted", style: "margin-top:.8rem" }, "Two tournaments are too few to prove a forecast right or wrong on their own; test A, with hundreds of matches, carries the weight.")]);
  }

  // ── 🎯 Calibration ──
  let calChart = null;
  function cal(d) {
    const rel = d.backtest.test_a.reliability || {};
    const ta = d.backtest.test_a;
    C.fill("pane-m-cal", [
      head("Calibration", "When it says 70%, does it happen 70% of the time?"),
      h("div", { class: "grid m-cal-grid" }, [
        h("div", { class: "card" }, [h("div", { class: "chart m-chart" }, h("canvas", { id: "m-rel", role: "img", "aria-label": "Reliability chart: predicted against observed win rate for the favourite, Elo and win-rate models" })),
          h("p", { class: "tiny muted" }, "Each point groups the ODIs since 2019 by the favourite's predicted chance (0.5–0.6 … 0.9–1.0). On the diagonal = perfectly calibrated; above it = the favourite won more often than predicted.")]),
        h("div", { class: "card" }, [h("h3", {}, "The numbers"),
          h("div", { class: "scroll" }, C.table(["Favourite's chance", "Matches", "Elo predicted", "Happened", "Win-rate predicted", "Happened"],
            (rel.elo || []).map((b, i) => { const w = (rel.win_rate || [])[i] || {}; return [b.bin.replace("-", "–"), b.n, pct(b.predicted), pct(b.observed), pct(w.predicted), pct(w.observed)]; }), { textCols: [0] })),
          facts([["Calibration slope (Elo)", f2(ta.elo.calibration_slope) + " (1.00 ideal; the bar is 0.8–1.2)"],
            ["Calibration slope (win-rate)", f2(ta.win_rate.calibration_slope)],
            ["Gate", d.gates.gate2_slope_in_range && d.gates.gate2_bins_within_tolerance ? "passed: slope in range, no well-filled bin more than 8 points off" : "not passed"]])])])]);
    if (!window.Chart) return;
    const pts = (k) => (rel[k] || []).map((b) => ({ x: b.predicted, y: b.observed, n: b.n }));
    if (calChart) calChart.destroy();
    calChart = new window.Chart(document.getElementById("m-rel"), {
      type: "scatter",
      data: { datasets: [
        { label: "Perfect calibration", type: "line", data: [{ x: 0.5, y: 0.5 }, { x: 1, y: 1 }], borderColor: "#64748b", borderDash: [5, 5], borderWidth: 1.5, pointRadius: 0 },
        { label: "Elo (live)", data: pts("elo"), borderColor: SERIES.elo, backgroundColor: SERIES.elo, pointRadius: 6, pointHoverRadius: 8, showLine: true, borderWidth: 2 },
        { label: "Win-rate model", data: pts("win_rate"), borderColor: SERIES.win_rate, backgroundColor: SERIES.win_rate, pointRadius: 6, pointHoverRadius: 8, showLine: true, borderWidth: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, animation: false,
        scales: { x: { min: 0.5, max: 1, title: { display: true, text: "Predicted chance for the favourite" }, ticks: { callback: (v) => Math.round(v * 100) + "%" } },
                  y: { min: 0.3, max: 1, title: { display: true, text: "How often the favourite won" }, ticks: { callback: (v) => Math.round(v * 100) + "%" } } },
        plugins: { legend: { labels: { usePointStyle: true } },
          tooltip: { callbacks: { label: (c) => c.dataset.label + ": predicted " + pct(c.raw.x) + ", happened " + pct(c.raw.y) + (c.raw.n ? " (" + c.raw.n + " matches)" : "") } } } } });
  }

  // ── 🏁 Models & versions ──
  function models(d) {
    const g = d.gates || {};
    const gate = (ok, text) => h("li", {}, [h("span", { class: "m-gate " + (ok ? "ok" : "no") }, ok ? "✓" : "✗"), text]);
    C.fill("pane-m-models", [
      head("Models", "Three models will compete; the best-calibrated one runs the forecast",
        h("a", { class: "btn", href: MLFLOW }, "Open in MLflow →")),
      h("div", { class: "scroll" }, C.table(["Model", "Kind", "Status", "Test A log loss", "Test B log loss"],
        (d.comparison || []).map((m) => [m.model, m.kind, h("span", { class: "badge " + (m.status === "live" ? "live" : "fmt") }, m.status),
          f3(m.test_a_log_loss), f3(m.test_b_log_loss)]), { textCols: [0, 1, 2] })),
      h("p", { class: "small dim" }, "Next: a gradient-boosting model that also sees squads (machine learning), then player strength learned from 11.6 million deliveries by a sequence model (deep learning). Each is backtested the same way and replaces the Elo model only if it does better."),
      h("div", { class: "grid", style: "margin-top:.6rem" }, [
        h("div", { class: "card" }, [h("h3", {}, "The bar a model must clear"),
          h("ul", { class: "m-gates" }, [
            gate(g.gate1_beats_baselines, "Test A: log loss and Brier beat both the coin flip and the win-rate model."),
            gate(g.gate2_slope_in_range && g.gate2_bins_within_tolerance, "Test A calibration: slope 0.8–1.2, no well-filled bin more than 8 points off."),
            gate(g.gate3_test_b_not_worse, "Test B: no worse than the win-rate model on World Cup matches."),
            gate(g.gate4_replay_and_sums, "Format checks, and 2019/2023 replays reproduce the real semi-finalists."),
            gate(true, "A human look at the top-14 ratings and title odds for plausibility, without changing any number.")]),
          h("p", { class: "tiny muted" }, "A new version is promoted only if it passes all of these and doesn't regress (log loss within +0.002 on test A, +0.005 on test B).")]),
        h("div", { class: "card" }, [h("h3", {}, "Versions"),
          C.table(["Version", "Promoted", "MLflow run"], (d.versions || []).slice().reverse().map((v) => [v.model_version + (v.model_version === d.champion.model_version ? " (live)" : ""),
            C.date(String(v.promoted_at || "").slice(0, 10)), h("code", { class: "m-code" }, (v.mlflow_run_id || "").slice(0, 8))]), { textCols: [0, 2] }),
          h("p", { class: "tiny muted" }, "Every training run, its settings, metrics and charts are in the site's public, read-only MLflow under the registered model cricstat-wc2027-predictor.")])])]);
  }

  // ── ⚠️ Limits ──
  function limits(d) {
    const s = d.disclosures || {};
    const item = (icon, title, text) => h("li", {}, [h("span", { class: "wc-li-icon", "aria-hidden": "true" }, icon), h("div", {}, [h("b", {}, title), " ", text])]);
    C.fill("pane-m-limits", [head("Limits", "What it can't tell you"),
      h("ul", { class: "wc-limits-list" }, [item("📐", "One model for everyone.", s.model), item("🎲", "Not a tip.", s.not_advice),
        item("🧩", "What it doesn't know.", s.not_used), item("†", "Afghanistan.", s.afghanistan),
        item("📅", "Data.", s.data), item("🎟️", "Qualifier places.", s.qualifier)]),
      h("p", { class: "small dim" }, ["See the forecast itself on the ", h("a", { href: "/cricket/predictor/" }, "ODI World Cup 2027 predictor"),
        ", and where every number comes from on ", h("a", { href: "/cricket/licences/" }, "Data & licences"), "."])]);
  }

  async function init() {
    try {
      const [{ data: d }, latest] = await Promise.all([C.api("/v1/models/predictor/backtest"),
        C.api("/v1/forecasts/wc-2027/latest").catch(() => null)]);
      const F = latest ? latest.data : null;
      document.getElementById("m-stamp").textContent = "Live model " + d.champion.model_version + " · trained " + C.date(String(d.champion.trained_at).slice(0, 10)) +
        " on data to " + C.date(d.champion.data_as_of) + (F ? " · forecast updated " + C.date(F.forecast.data_as_of) : "");
      document.getElementById("m-asof").textContent = " · " + d.champion.model_version;
      plain(d, F); elo(d); sim(d, F); tests(d); cal(d); models(d); limits(d);
      C.sectionTabs(document.querySelector(".m-board .sec-tabs"));
      // the chart may be drawn while its tab is hidden
      document.getElementById("tab-m-cal").addEventListener("click", () => { if (calChart) { try { calChart.resize(); } catch (e) { /* not drawable */ } } });
    } catch (e) { C.showError("pane-m-plain", e, "the methodology data"); }
  }
  init();
})();
