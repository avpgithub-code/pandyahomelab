/* cricstat hub (P0.4): counters, latest results, followed team, leaders, featured leagues. */
(function () {
  "use strict";
  const C = window.cricstat, h = C.h;
  // The "i" ball arrives from a random end of the pitch, above or below the wordmark (CSS: cricstat.css §7-8).
  // On landing the bails fly and splinters burst; clicking the ball replays it with a wooden "tock"
  // (Web Audio, synthesised; browsers allow sound only after a click, so page loads stay silent).
  const pitch = document.querySelector(".hero .pitch");
  const LAND_MS = 1800 * 0.76;                        // the landing keyframe of cs-ball-in
  let audio = null, withSound = false;
  function pick() { if (pitch) pitch.dataset.ball = ["rb", "rt", "lb", "lt"][Math.floor(Math.random() * 4)]; }
  function tock() {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const t = audio.currentTime, out = audio.createGain();
      out.gain.value = 0.5; out.connect(audio.destination);
      const knock = (at, freq, len, vol) => {          // a short band-passed noise burst = wood
        const n = audio.createBuffer(1, Math.ceil(audio.sampleRate * len), audio.sampleRate), d = n.getChannelData(0);
        for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / d.length, 4);
        const src = audio.createBufferSource(), bp = audio.createBiquadFilter(), g = audio.createGain();
        src.buffer = n; bp.type = "bandpass"; bp.frequency.value = freq; bp.Q.value = 6; g.gain.value = vol;
        src.connect(bp).connect(g).connect(out); src.start(t + at);
      };
      const thump = audio.createOscillator(), tg = audio.createGain();   // body of the hit
      thump.frequency.setValueAtTime(190, t); thump.frequency.exponentialRampToValueAtTime(90, t + 0.09);
      tg.gain.setValueAtTime(0.9, t); tg.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
      thump.connect(tg).connect(out); thump.start(t); thump.stop(t + 0.13);
      knock(0, 1700, 0.07, 1.4);                        // the stump
      knock(0.09, 3200, 0.04, 0.6); knock(0.17, 2900, 0.03, 0.4);   // the bails landing
    } catch (e) { /* no audio: the animation still plays */ }
  }
  function burst() {
    const ball = pitch && pitch.querySelector(".i-ball");
    if (!ball || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const chips = [];
    const bail = (dx, rot) => ({ w: ".2em", h: ".045em", c: "#e6c48d", dx: dx, dy: "-.65em", rot: rot });
    const parts = [bail("-.55em", "-320deg"), bail(".6em", "380deg")];
    for (let i = 0; i < 6; i++) {
      const a = Math.PI * (1.05 + i * 0.18), r = 0.35 + Math.random() * 0.3;
      parts.push({ w: ".05em", h: ".03em", c: i % 2 ? "#c99a5b" : "#f0dcb4",
                   dx: (Math.cos(a) * r).toFixed(2) + "em", dy: (Math.sin(a) * r).toFixed(2) + "em", rot: (Math.random() * 540 - 270) + "deg" });
    }
    parts.forEach((p) => {
      const el = document.createElement("span");
      el.className = "chip";
      el.setAttribute("aria-hidden", "true");
      el.style.cssText = "--w:" + p.w + ";--h:" + p.h + ";--c:" + p.c + ";--dx:" + p.dx + ";--dy:" + p.dy + ";--rot:" + p.rot;
      ball.appendChild(el); chips.push(el);
    });
    const h1 = pitch.querySelector(".cs-lockup");
    h1.classList.remove("jolt"); void h1.offsetWidth; h1.classList.add("jolt");
    setTimeout(() => chips.forEach((el) => el.remove()), 1000);
  }
  if (pitch) {
    pick();
    const dot = pitch.querySelector(".i-dot");
    const tip = document.createElementNS("http://www.w3.org/2000/svg", "title");   // hover hint
    tip.textContent = "Click the ball to bowl it again 🔊";
    dot.prepend(tip);
    dot.addEventListener("animationstart", (e) => {
      if (e.animationName !== "cs-ball-in") return;
      setTimeout(() => { burst(); if (withSound) tock(); withSound = false; }, LAND_MS);
    });
    dot.addEventListener("click", () => {             // replay: a fresh delivery, with sound
      pick(); withSound = true;
      if (audio && audio.state === "suspended") audio.resume();
      dot.style.animation = "none"; void dot.getBoundingClientRect(); dot.style.animation = "";
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { tock(); withSound = false; }
    });
  }
  const GENDER = { male: "men", female: "women" };
  let asOf = null, source = null, period = "ytd", followed = null, teamList = [];

  async function counters() {
    try {
      const { data, meta } = await C.api("/v1/status");
      asOf = meta.data_as_of;
      source = data.source || null;
      // One date everywhere: Cricsheet's own last update (the date the source published). It moves
      // only when Cricsheet publishes; the daily job then syncs. Fallback: the newest match in the data.
      const src = data.source || {};
      const label = src.last_updated ? "Cricsheet " + C.date(src.last_updated.slice(0, 10)) : "as of " + C.date(meta.data_as_of);
      document.getElementById("h-asof").textContent = "Live data · checked daily · " + label;
      document.getElementById("mc-asof").textContent = " · " + label;
      C.countUp(document.getElementById("k-matches"), data.counts.matches);
      const d = document.getElementById("k-deliveries");
      if (d) C.scoreText(d, C.compact(data.build.deliveries));
      C.countUp(document.getElementById("k-players"), data.counts.players);
      C.countUp(document.getElementById("k-teams"), data.counts.teams);
    } catch (e) { /* the hero still reads fine without numbers */ }
    return asOf;
  }

  // Internationals involving ICC full members (associate T20Is are plentiful and would crowd the
  // strip), plus featured leagues under "All".
  const FULL = new Set(["India", "Australia", "England", "Pakistan", "South Africa", "New Zealand", "Sri Lanka",
                        "West Indies", "Bangladesh", "Afghanistan", "Zimbabwe", "Ireland"]);
  const state = { fmt: "ODI", gender: "male" };
  async function latest() {
    document.querySelectorAll("[data-lfmt]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lfmt === state.fmt)));
    const out = C.fill("latest", [h("div", { class: "skeleton" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton" })]);
    try {
      const { data } = await C.api("/v1/matches?scope=" + state.fmt + "&gender=" + state.gender + "&limit=100");
      const keep = data.filter((m) => ["T20_LEAGUE", "HUNDRED"].includes(m.format) || m.teams.some((t) => FULL.has(t.name))).slice(0, 16);
      C.fill(out, keep.length ? keep.map(C.matchCard) : h("p", { class: "muted" }, "No matches."));
      out.scrollLeft = 0;
      arrows();
      const span = keep.length ? " · " + C.date(keep[keep.length - 1].date) + " – " + C.date(keep[0].end_date || keep[0].date) : "";
      document.getElementById("latest-note").textContent = keep.length + " " + (state.gender === "female" ? "women's" : "men's") +
        " matches involving ICC full members" + (state.fmt === "ALL" ? " and featured leagues" : "") + span + ", newest first.";
      freshness();
    } catch (e) { C.showError(out, e, "latest results"); }
  }
  function freshness() { C.freshness(document.getElementById("latest-fresh"), source, asOf); }
  function arrows() {
    const s = document.getElementById("latest");
    const [prev, next] = [document.querySelector(".car-btn.prev"), document.querySelector(".car-btn.next")];
    if (!s || !prev) return;
    prev.disabled = s.scrollLeft <= 4;
    next.disabled = s.scrollLeft + s.clientWidth >= s.scrollWidth - 4;
  }
  function wireCarousel() {
    const s = document.getElementById("latest");
    document.querySelectorAll("[data-car]").forEach((b) => b.addEventListener("click", () => {
      s.scrollBy({ left: Number(b.dataset.car) * Math.max(280, s.clientWidth - 60), behavior: "smooth" });
    }));
    s.addEventListener("scroll", () => window.requestAnimationFrame(arrows), { passive: true });
    window.addEventListener("resize", arrows);
    document.querySelectorAll("[data-lfmt]").forEach((b) => b.addEventListener("click", () => { state.fmt = b.dataset.lfmt; latest(); }));
    document.querySelectorAll('input[name="lgender"]').forEach((r) => r.addEventListener("change", () => { state.gender = r.value; latest(); }));
  }

  // In form, one format at a time (runs and wickets only add up within a format), over the SAME
  // period as the format cards. Short periods read as "In form"; 5 years / All as "Top performers".
  async function inFormCard(team) {
    const p = C.periodRange(period, asOf);
    const short = ["last10", "ytd", "1y"].includes(period);
    const counts = { TEST: 0, ODI: 0, T20I: 0 }, windows = {};
    if (p.last) {
      // Each format's own last-N window: from the date of its N-th most recent match.
      await Promise.all(Object.keys(counts).map(async (k) => {
        const { data } = await C.api("/v1/teams/" + team.slug + "/results?scope=" + k + "&limit=" + p.last);
        counts[k] = data.length;
        if (data.length) windows[k] = { from: data[data.length - 1].date, to: asOf };
      }));
    } else {
      // Exact counts from the record endpoint (a match list would be capped by paging).
      const span = p.from ? "&from=" + p.from + "&to=" + p.to : "";
      await Promise.all(Object.keys(counts).map(async (k) => {
        const { data } = await C.api("/v1/teams/" + team.slug + "/record?scope=" + k + span);
        counts[k] = data[0] ? data[0].matches : 0;
        windows[k] = p.from ? { from: p.from, to: p.to } : null;
      }));
    }
    const formats = Object.keys(counts).filter((k) => counts[k]);
    if (!formats.length) return null;
    // Open on ODI (the default); if the team has no ODIs in the period, on its busiest format
    // (for "last N", equal counts, on the one with the freshest window).
    const start = counts.ODI ? "ODI" : formats.slice().sort((a, b) => p.last
      ? (windows[b].from > windows[a].from ? 1 : windows[b].from < windows[a].from ? -1 : 0)
      : counts[b] - counts[a])[0];
    const body = h("div", { class: "inform-body" });
    const sub = h("span", { class: "tiny muted" });
    const caps = h("div", { class: "tabs", role: "group", "aria-label": "By format" },
      ["TEST", "ODI", "T20I"].map((k) => h("button", { type: "button", class: "tab sm", "data-inform": k,
        "aria-pressed": String(k === start), disabled: counts[k] ? null : true,
        title: counts[k] ? counts[k] + " matches" : "No matches in this period", onclick: () => show(k) }, C.fmtName(k))));
    async function show(scope) {
      caps.querySelectorAll("[data-inform]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.inform === scope)));
      const w = windows[scope];
      sub.textContent = C.fmtName(scope) + " · " + counts[scope] + " matches · " +
        (p.last ? "last " + counts[scope] + " (since " + C.date(w.from) + ")"
                : p.from ? p.label + " to " + C.date(asOf) : "all time, since " + (team.first_date || "").slice(0, 4));
      C.fill(body, h("div", { class: "skeleton", style: "height:160px" }));
      try {
        const q = "&scope=" + scope + (w ? "&from=" + w.from + "&to=" + w.to : "") + "&limit=2";
        const [bat, bowl] = await Promise.all([
          C.api("/v1/teams/" + team.slug + "/top-players?metric=runs" + q),
          C.api("/v1/teams/" + team.slug + "/top-players?metric=wickets" + q)]);
        const line = (pl, val, unit, sub2) => h("li", {}, [C.who(pl.full_name || pl.name, sub2, team.name, "/cricket/players/" + pl.slug + "/", null, pl.photo_url),
          h("span", { class: "val" }, [val, h("small", {}, unit)])]);
        C.fill(body, [
          h("div", { class: "section-label", style: "margin:.2rem 0 0" }, "Runs"),
          h("ol", { class: "rank" }, bat.data.map((pl) => line(pl, C.num(pl.runs), "runs", pl.innings + " inns · avg " + C.ratio(pl.average)))),
          h("div", { class: "section-label", style: "margin:.6rem 0 0" }, "Wickets"),
          h("ol", { class: "rank" }, bowl.data.map((pl) => line(pl, pl.wickets, "wkts", pl.innings + " inns · avg " + C.ratio(pl.average))))]);
      } catch (e) { C.showError(body, e, "players"); }
    }
    show(start);
    return h("div", { class: "card accent" }, [
      h("div", { class: "card-head", style: "margin-bottom:.4rem" }, [h("h3", {}, short ? "In form" : "Top performers"), caps]),
      h("p", { style: "margin:0 0 .4rem" }, sub), body]);
  }

  async function cards(slug, teams) {
    followed = slug; teamList = teams;
    const team = teams.find((t) => t.slug === slug) || teams.find((t) => t.slug === "india-men");
    C.fill("follow-period", C.periodControl(period, (k) => { period = k; cards(followed, teamList); }));
    document.getElementById("following-title").textContent = team.name + " " + GENDER[team.gender];
    C.fill("follow-badge", C.teamBadge(team.name, "lg"));
    const out = C.fill("follow-cards", [h("div", { class: "skeleton" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton" })]);
    try {
      const href = "/cricket/countries/" + team.slug + "/";
      const built = await Promise.all([C.formatCard(team, "ODI", period, asOf, href), C.formatCard(team, "T20I", period, asOf, href),
        C.formatCard(team, "TEST", period, asOf, href), inFormCard(team)]);
      const shown = built.filter(Boolean);
      C.fill(out, shown.length ? shown : h("p", { class: "muted" }, "No recent international matches for this team."));
    } catch (e) { C.showError(out, e, "this team's cards"); }
  }

  async function follow() {
    const select = document.getElementById("follow");
    const radios = document.querySelectorAll('input[name="fgender"]');
    try {
      const { data: teams } = await C.api("/v1/teams?type=international");
      const keep = teams.filter((t) => t.matches >= 20);
      const bySlug = {};
      keep.forEach((t) => { bySlug[t.slug] = t; });
      const india = (t) => t.name === "India" ? 0 : 1;                       // India first: the default
      // One list per gender, names only; Men/Women picks the list. The stored value stays the team slug.
      const fill = (gender, slug) => {
        const list = keep.filter((t) => t.gender === gender)
          .sort((a, b) => india(a) - india(b) || a.name.localeCompare(b.name));
        C.fill(select, list.map((t) => h("option", { value: t.slug }, t.name)));
        select.value = list.some((t) => t.slug === slug) ? slug : list[0].slug;
        radios.forEach((r) => { r.checked = r.value === gender; });
      };
      const show = (slug) => {
        const t = bySlug[slug] || bySlug["india-men"];
        fill(t.gender, t.slug);
        C.setFollow(t.slug); showReset(); cards(t.slug, keep);
      };
      const reset = document.getElementById("follow-reset");
      const showReset = () => { if (reset) reset.hidden = select.value === "india-men"; };
      select.addEventListener("change", () => show(select.value));
      radios.forEach((r) => r.addEventListener("change", () => {
        // Same country in the other gender when it has a side, else India.
        const name = (bySlug[select.value] || {}).name;
        const other = keep.find((t) => t.gender === r.value && t.name === name) ||
          keep.find((t) => t.gender === r.value && t.name === "India");
        show(other.slug);
      }));
      if (reset) reset.addEventListener("click", (ev) => { ev.preventDefault(); show("india-men"); });
      const current = C.getFollow();
      const start = bySlug[current] || bySlug["india-men"];
      fill(start.gender, start.slug);
      showReset();
      await cards(select.value, keep);
    } catch (e) { C.showError("follow-cards", e, "teams"); }
  }

  async function leaders(scope) {
    const year = asOf.slice(0, 4);
    document.getElementById("leaders-title").textContent = year + " leaders";
    document.querySelectorAll("[data-leaders]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.leaders === scope)));
    const out = C.fill("leaders", [h("div", { class: "skeleton" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton" })]);
    const q = "?scope=" + scope + "&from=" + year + "&to=" + asOf + "&limit=5&gender=";
    try {
      const sets = await Promise.all([["batting", "male", "Most runs · men"], ["bowling", "male", "Most wickets · men"],
        ["batting", "female", "Most runs · women"], ["bowling", "female", "Most wickets · women"]].map(async ([kind, g, title]) => {
        const { data } = await C.api("/v1/leaderboards/" + kind + q + g);
        return h("div", { class: "card " + (g === "female" ? "blue" : "accent") }, [
          h("div", { class: "card-head" }, [h("h3", {}, title)]),
          data.length ? h("ol", { class: "rank" }, data.map((p) => h("li", {}, [
            C.who(p.full_name || p.name, p.team + " · " + p.matches + " matches", p.team, "/cricket/players/" + p.slug + "/", null, p.photo_url),
            h("span", { class: "val" }, kind === "batting" ? [C.num(p.runs), h("small", {}, "avg " + C.ratio(p.average))]
                                                            : [p.wickets, h("small", {}, "econ " + C.ratio(p.economy))])]))) :
            h("p", { class: "muted small" }, "No matches yet this year.")]);
      }));
      C.fill(out, sets);
    } catch (e) { C.showError(out, e, "leaders"); }
  }

  async function leagues() {
    const out = document.getElementById("leagues");
    try {
      const { data } = await C.api("/v1/meta/competitions?featured=true");
      const bySlug = {};
      data.forEach((c) => {
        const b = bySlug[c.competition_slug] || (bySlug[c.competition_slug] = { name: c.event_name, gender: c.gender, matches: 0, seasons: new Set(), first: c.first_date, last: c.last_date });
        b.matches += c.matches; c.seasons.forEach((s) => b.seasons.add(s));
        if (c.first_date < b.first) b.first = c.first_date;
        if (c.last_date > b.last) { b.last = c.last_date; b.name = c.event_name; }
      });
      const list = Object.entries(bySlug).sort((a, b) => b[1].matches - a[1].matches);
      C.fill(out, list.map(([slug, l]) => h("div", { class: "card" }, [
        h("div", { class: "card-head" }, [C.teamBadge(l.name.replace(/Men's|Women's|Competition/g, "").trim(), "sm"),
          h("span", { class: "badge " + (l.gender === "female" ? "fmt" : "saff") }, l.gender === "female" ? "Women" : "Men")]),
        h("h3", { style: "margin:.2rem 0 .3rem" }, l.name),
        h("p", { class: "tiny dim" }, C.num(l.matches) + " matches · " + l.seasons.size + " seasons · " + l.first.slice(0, 4) + "–" + l.last.slice(0, 4))])));
    } catch (e) { C.showError(out, e, "leagues"); }
  }

  wireCarousel();
  document.querySelectorAll("[data-leaders]").forEach((b) => b.addEventListener("click", () => leaders(b.dataset.leaders)));
  C.sectionTabs(document.querySelector(".sec-tabs"));
  // ODI World Cup 2027 teaser (full P1.6 build only): the followed country's men's side, else India.
  async function wcTeaser() {
    const out = document.getElementById("wc-answer");
    if (!out) return;
    try {
      const [{ data }, { data: teams }] = await Promise.all([C.api("/v1/forecasts/wc-2027/latest"), C.api("/v1/teams?type=international&gender=male")]);
      const followed = (teams.find((t) => t.slug === C.getFollow()) || {}).name
        || (C.getFollow().endsWith("-women") ? C.getFollow().replace(/-women$/, "") : null);
      const ranked = data.teams.slice().sort((a, b) => (b.probabilities.champion || 0) - (a.probabilities.champion || 0));
      const pick = (name) => ranked.find((t) => t.team === name || (name && t.slug === name + "-men"));
      const t = pick(followed) || pick("India");
      const rank = ranked.indexOf(t) + 1, p = t.probabilities.champion || 0;
      const nth = (n) => n + ([, "st", "nd", "rd"][(n % 100 >> 3 ^ 1) && n % 10] || "th");
      document.getElementById("wc-qtext").textContent = "What are the chances of " + t.team + " lifting the 2027 ODI World Cup?";
      C.fill(out, [h("b", {}, t.team + ": " + (p < 0.001 ? "<0.1%" : (100 * p).toFixed(1) + "%")),
        " · " + nth(rank) + " favourite · ", C.wordmark(), " Elo forecast · updated " + C.date(data.forecast.data_as_of)]);
    } catch (e) { out.hidden = true; }   // the question still links to the predictor
  }

  wcTeaser();
  counters().then((d) => { if (!d) asOf = new Date().toISOString().slice(0, 10); latest(); follow(); leaders("ODI"); leagues(); });
})();
