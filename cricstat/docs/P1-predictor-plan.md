# P1 — ODI World Cup 2027 predictor: plan

Status: **approved 2026-10-08** (branch `feat/cricstat-p1-elo`); decisions locked in §10. Nothing is built yet.
Companion: `P1-afghanistan-audit.md` (entity audit, crosswalks, supplement load jobs and CI/CD).
Scope: the Elo + Monte Carlo baseline end to end (data → model → backtests → job → API → pages). It also sets the
frame the ML and DL challengers will plug into later (§8). Decisions needed from the owner are collected in §10.

## 1. Facts this plan rests on (checked 2026-10-08)
**The 2027 tournament.** The ICC published the format on 15 Jul 2026 and the schedule on 1 Oct 2026. It runs from
2 Oct to 21 Nov 2027 in South Africa, Zimbabwe and Namibia: 14 teams, 57 matches, 12 venues.
| Stage | Teams | Rule | Matches |
|---|---|---|---|
| Super Series (Windhoek) | 3 | Qualifier places 2–4; round robin; the winner joins the group stage | 3 |
| Group stage | 12 in 2 groups of 6 | Round robin; the top 3 of each group **plus the best 4th-placed team** go through | 30 |
| Super 7 | 7 | A fresh round robin (21 = every pair once, so no points carried over) | 21 |
| Semi-finals | 4 | 1st v 4th (17 Nov, Cape Town), 2nd v 3rd (18 Nov, Centurion) | 2 |
| Final | 2 | 21 Nov, Johannesburg | 1 |

- **Groups (pre-seeded):** A = India, Australia, Pakistan, Afghanistan, Zimbabwe, Qualifier-A;
  B = New Zealand, South Africa, Sri Lanka, England, Bangladesh, Qualifier-B.
- **Direct qualifiers (10):** hosts South Africa and Zimbabwe, plus the top 8 of the ODI rankings on 30 Sep 2026:
  Afghanistan, Australia, Bangladesh, England, India, New Zealand, Pakistan and Sri Lanka. **West Indies and Ireland
  must qualify.** Namibia co-hosts but is not guaranteed a place.
- **Qualifier:** 10 teams, 26 Feb – 21 Mar 2027 (Namibia + South Africa). Its winner goes straight into a group, and
  places 2–4 go to the Super Series. Which group the Qualifier winner joins (A or B) is still to be confirmed against the
  official fixture list in step P1.1.
- **Still to confirm in P1.1 from the playing conditions:** the tie-break order (points, wins, NRR …), how the "best 4th"
  is compared across groups of equal size, and the reserve-day / washed-out-semi rule (in 2019 and 2023 the
  higher-placed team went through).

**Data (live serving DB, build of 2026-10-08).**
- 2,581 men's ODIs (`match_type='ODI'`), 27 Jun 2002 → 5 Oct 2026. Coverage is dense from 2003, which is enough for a
  burn-in period before the 2019 backtest. 2,451 have a winner, 27 were ties (6 decided by super over),
  103 no result; 223 used D/L.
- `team_results.home_away` is filled for every row. **Home sides win 59.2%** of decided games (1,859); that's about
  +64 Elo points before any fitting.
- **Afghanistan men: 0 rows.** Cricsheet withholds those matches (379 incl. the Afghanistan Premier League, per cricsheet.org/matches/; reason in §2.1). This also removes every other team's games against
  Afghanistan.
- **World Cup coverage:** 2019 has 36 of 48 matches (the 9 Afghanistan games and 3 washouts with no ball bowled are
  missing); 2023 has 39 of 48 (the 9 Afghanistan games). Fixture lists for the backtests therefore come from a
  hand-entered tournament file, not from the DB.
- **Associates form a loosely connected pool:** since 2019 they played 284 ODIs among themselves (mainly CWC League 2)
  and only 66 against Full Members. Plain Elo would over-rate them (Scotland 40–23, Nepal 36–41 since 2022). This
  matters for the Qualifier and Super Series slots.

## 2. The baseline model: Elo + Monte Carlo
### 2.1 Data used
- Official men's ODIs only: `matches` with `gender='male' AND match_type='ODI'`, joined to `team_results`. This leaves
  out ODMs, List A and warm-ups, and composite sides (Asia XI, Africa XI, ICC World XI) are excluded. Each match is
  used in date order, then by `match_id` (stable; `match_key` can renumber on a full rebuild).
- Per match: date, both teams, the venue country → home/away/neutral (from `venue_map.csv`, already used by the
  build), and the outcome. The model does not use margins, the toss, D/L or squads (see §2.3).
- **Afghanistan (D1 = S1, locked):** a small, reviewed **results-only** file,
  `cricstat/cricstat-models/supplement/afg_odi_results.csv` (models image, not `cricstat/sql/`): date, opponent, venue country and result for each Afghanistan men's
  ODI, taken from public results lists (Wikipedia's per-season lists, attributed) and cross-checked. Elo needs nothing
  more than results, so Afghanistan is then rated **by exactly the same rule as everyone else**, and the other teams'
  missing games against Afghanistan come back too. It is 188 rows (19 Apr 2009 → 15 Aug 2026), plus a few each year.
  - **Keys and constraints (checked 2026-10-08).** The rows stay **out of the serving DB**. The build gate fails if
    `matches` ≠ raw active matches; `matches` needs `source_sha256`, `venue_key` and `has_deliveries`, which a
    results-only row can't truthfully fill; and public team records, head-to-heads and golden team figures would
    silently change. They live in the models domain (`supplement_results`, loaded into `forecast.sqlite`) with
    the same key spaces:
    | Column | Must match | Check (failure → exit 2, old forecast stays) |
    |---|---|---|
    | `match_id` TEXT PK | Same ESPNcricinfo id space as `matches.match_id` (the Wikipedia scorecard link) | Unique; **not** already in `matches` (if Cricsheet restores a match, its row wins and the supplement row is ignored) |
    | `start_date` | ISO date, like `matches.start_date` | 2009-04-01 ≤ date ≤ data_as_of |
    | `team1`, `team2` | Exact `teams.name` for gender male, team_type international; one side is Afghanistan | The opponent resolves to an existing team identity |
    | `venue_country` | The country names used by `venue_map.csv` | Resolves; home/away/neutral is derived by **the same rule as `team_results.home_away`** (so Afghanistan's "home" series in the UAE count as neutral, like everyone's) |
    | `result`, `winner`, `method`, `decided_by` | The same value sets as `matches` | CHECK constraints copied from serving_schema.sql |
    | `source_url`, `odi_status_note` | The Wikipedia article (credit) | Present; 2009 Qualifier rows tagged ODI by hand |
    Whole-file check: won/lost/tied/NR per opponent equals Wikipedia's Afghanistan ODI records page.
    **Players: none added.** Elo uses no player data. Afghan players already exist with Cricsheet ids from other
    matches (e.g. Rashid Khan `5f547c8b`, Mohammad Nabi `62af8546`). Should a challenger ever need Afghan squads, the
    join goes ESPNcricinfo id → Register `key_cricinfo` → Cricsheet id, never by name (the Register has two
    "Rashid Khan"s). **Team:** Afghanistan men has no `team_key` (0 rows); the models domain uses the team identity
    (name + gender + type, as decided in P0.3), and the predictor row for Afghanistan has no team page link.
  - **Why Cricsheet withholds them (their article of 14 Nov 2024,
    cricsheet.org/article/explanation-for-withholding-of-afghanistani-matches/):** not licensing. It's a protest:
    the maintainer is not comfortable publishing "matches involving, or played in, Afghanistan while the Afghan
    women's players are simply being ignored by the ICC and most of the full members". It covers every Afghanistan
    men's match and the Afghanistan Premier League; the /matches/ page says 379 are withheld today. They may be
    restored later.
  - **Guardrail:** adding Afghanistan's results from another source is legally fine, because who won a match is a
    plain fact; we'd still copy no scorecards, scrape neither ESPNcricinfo nor the ICC, and credit the source. But it
    works around a deliberate, ethically motivated choice by the source we depend on. That's a values call, not a
    legal one. Whichever option you pick, the page should give Cricsheet's reason and link to the article.
    Chosen: S1, Afghanistan's results are used only for ratings, the predictor and backtests (see the audit).

### 2.2 Rating method
- Expected score `E_a = 1 / (1 + 10^(-(R_a - R_b + H·h)/400))`, where `h` = +1 at home, −1 away, 0 neutral.
- Result: win 1, loss 0, **tie 0.5** (also when a super over decided it, because the 50 overs were level). No result =
  no update.
- Update `R_a += K · m · (S_a − E_a)`, symmetric for the other team.
- **Parameters, tuned only on data before each backtest tournament (no leakage):**
  | Parameter | Search range | Note |
  |---|---|---|
  | K | 16–64 | Higher = reacts faster to form |
  | H (home advantage) | 0–120 | The raw data suggests ~60 |
  | Margin multiplier m | off / on | When on: from margin in runs, or wickets + balls left, capped. It stays only if it improves log loss |
  | Season regression | 0–30% toward the mean at each 1 Jan | Lets teams that rarely play drift back to average |
  | Starting rating | Full Member 1500; Associate 1500 − Δ, Δ in 0–300 | One rule by ICC status **at first appearance**, the same for every team (D2) |
- The objective is log loss of the one-step-ahead prediction (rating before the match vs result) over the tuning window,
  scored from 2007 (2003–06 is burn-in). Grid search, a few hundred runs, each one an MLflow child run.
- **Uncertainty.** A point Elo rating overstates how sure we are about a team. In each simulation, every team's rating
  gets a draw of `N(0, σ)`, where σ is estimated from how much ratings move over a tournament-length gap and is fixed
  before each backtest. A second option, ratings updated inside each simulated tournament (538-style), is tested; it
  stays only if it helps.

### 2.3 Squads, form and what the baseline ignores
- **Form** is only what K and recency put into the rating. There is no separate form term.
- **Squads, injuries, retirements, captaincy, conditions, toss and pitch: not used.** The baseline rates teams, not
  players. That is exactly the gap the ML and DL challengers are there to close (§8), and the page says so plainly.
- **One model for everyone:** the same parameters, the same rule for every team and no hand adjustments for any team.
  The followed team only changes what the page shows first.

### 2.4 Simulating the tournament
- A config per tournament (`cricstat-models/tournaments/wc2019.yaml`, `wc2023.yaml`, `wc2027.yaml`) holds the teams,
  groups, the full fixture list with venue country (hence home/neutral), the stage rules, points (win 2, NR/tie 1)
  and the knockout rules. One engine runs all three tournaments, and unit tests pin each format.
- Per match: P(win) from Elo; P(no result) = a flat rate fitted from the data (~4% of ODIs). Knockouts use the reserve-day
  rule: a washed-out semi sends the higher-placed team through. A tie in a knockout counts as a super over (50/50).
- **Tie-breaks:** NRR is not modelled from scores (the baseline doesn't predict margins). Equal points are split by wins,
  then by a random draw. This is disclosed, and it barely affects the title odds.
- **Qualifier slots before 21 Mar 2027 (D3):** I recommend simulating the Qualifier itself from Elo once its
  10-team field and format are confirmed. Its top four fill Qualifier-A/B and the Super Series in each run. The page
  shows "Qualifier slot" rows with each candidate's chance of reaching the World Cup. Once the Qualifier ends, the real
  teams drop in.
- 50,000 runs with a seeded RNG (stage probabilities have a standard error of 0.2 points or less), vectorised in numpy.
  This should take seconds on the NAS.
- **Output per team:** P(reach group stage) for qualifiers, P(Super 7), P(semi-final), P(final), P(champion), and the
  expected Super 7 finish. Checks: the champion probabilities sum to 1, the semi-final ones to 4, and so on.

### 2.5 As built in P1.2 (2026-10-08)
- **Regression target refined:** each 1 January a team moves r of the way toward the base rating for its
  ICC status *on that day* (1500 Full Member, 1500 − Δ Associate), not toward its starting rating, which
  would keep pulling Ireland and Afghanistan (associates at their first match, Full Members since 2017)
  toward an associate level. It lowered test-A log loss (0.6054 → 0.6049) and fixed calibration
  (slope 0.91 → 0.97).
- **Tuned (2,016 combinations, log loss on 2007 → cutoff):** K = 20, home advantage = 75 Elo points,
  margin multiplier on, Δ = 400–500. Regression r = 0 for the 2019/2023 windows, 0.05 with all data.
  Walk-forward picked K = 20, H = 75, margin on every year (K = 16 once), so the fit is stable.
- **Grid points are not MLflow child runs:** the whole grid is one artifact (grid.csv), so the
  experiment stays readable.

### 2.6 Host conditions for 2027 (checked 2026-10-08, men's ODIs 2003–2026)
The 2027 World Cup is played in South Africa (44 matches), Zimbabwe (10) and Namibia (6), 2 Oct–21 Nov.
- **Home advantage:** one term for every team (H ≈ 75), applied to South Africa in South Africa, Zimbabwe
  in Zimbabwe, Namibia in Windhoek. Residual check since 2007: home sides expected 58.0%, won 58.6%.
  No regional "touring" effect beyond it (Asian teams in SA/ENG/NZ/AUS −0.8 pts, SENA teams in Asia
  −2.0 pts, Asian visitors in South Africa +4.6 ± 11 pts: all noise).
- **Batting first vs chasing:** no reliable effect at the host venues once team strength is accounted for
  (South Africa −1 ± 7 pts, Zimbabwe −6 ± 7, Namibia −1 ± 15; Newlands +16 ± 20, Centurion −12 ± 16 are
  small samples). Before the toss each team has an even chance of batting first, so a uniform
  bat-first edge would cancel out in a pre-match forecast anyway. It matters after the toss, so it belongs
  in the in-match model (P1c), together with day/night (the 2027 schedule flags day/night games;
  Cricsheet doesn't, so dew can't be measured historically).
- **Rain:** Cricsheet omits matches abandoned without a ball, so no-result rates come from the complete
  Wikipedia ODI list: 6.5% of all ODIs since 2008 (2.6% abandoned without a ball), not the ~4%
  Cricsheet alone suggests. Host countries in October–November: South Africa 3 of 32, Zimbabwe 1 of 34,
  Namibia 0 of 8. **P1.3 uses a per-country Oct–Nov no-result rate shrunk toward the global rate**
  (too few matches to trust alone), and the knockouts' reserve-day rule.
- **Venue character (scoring level):** first-innings averages differ (Wanderers/Newlands/Kingsmead about
  265, Gqeberha 235, Harare 240, Windhoek 223). That changes margins and NRR, not who wins, so it isn't
  in Elo. It is a P1b feature (venue profile, plus squad make-up if bowling styles become available).
- **Not available in any allowed source:** pitch reports, weather, bowling type (Cricsheet has none;
  Wikidata's bowling style is patchy and not fetched yet).
- **Data fix found:** `sql/venue_map.csv` leaves sponsor renames as separate grounds (Bloemfontein =
  Goodyear Park / Chevrolet Park / OUTsurance Oval / Mangaung Oval; "New Wanderers" vs "The Wanderers";
  Boland Bank Park vs Boland Park; De Beers Diamond Oval vs Diamond Oval). venue_map is applied on every
  build and isn't in rules_sha, so the fix needs no full rebuild.

### 2.7 As built in P1.3 (2026-10-08)
- **Simulator:** one engine driven by each tournament's format.json; 2,000 simulated 2027 tournaments
  take about 3 s on the NAS (50,000 in about 80 s).
- **Rating drift (sigma), measured not chosen:** SD of Full Members' rating change over a horizon, since
  2007: 11 points over 30 days, 35 over a year, 42 over 18 months; a random walk fits
  (sigma = sqrt(3.36 × days)). The 2027 forecast 360 days out uses sigma = 35; backtests on the eve use 0,
  with ratings updated after each simulated match (K = 20).
- **No-result rates (complete Wikipedia ODI list, shrunk toward 6.5% global):** South Africa 7.6%,
  Zimbabwe 5.1%, Namibia 5.6% (October–November); ties 1.1%. Knockouts use the rate squared (reserve day).
- **Qualifier (owner decision 2026-10-08):** until the field is known, one simulated round robin of West
  Indies, Ireland and the eight CWC League 2 teams fills Q1–Q4 (wcq2027/format.json lists the assumptions).
- **Results:** gates 1–4 pass. Test B (92 World Cup matches, eve ratings): Elo log loss 0.548 / Brier 0.177
  vs win-rate 0.659 / 0.229. Test C: 2019 champion England had the highest pre-tournament chance (36%);
  2023 champion Australia had the second highest (16%; India 42% lost the final). Replays reproduce the
  real semi-finalists and champions. MLflow run eae84b75.

### 2.8 As built in P1.4 (2026-10-08)
- **Gate 5 passed** (owner, 2026-10-08) → first champion `cricstat-wc2027-predictor` version 1 (`elo-v1`,
  MLflow run 79539be4), forecast #1 written to data/db/forecast.sqlite.
- **Commands:** `forecast` (daily; fingerprint = rating input + champion + fixtures + Qualifier field, so it
  skips in <1 s when nothing changed), `train [--owner-approved]` (backtests → promotion gate: gates 1–4
  and no regression beyond +0.002 test-A / +0.005 test-B log loss), `selftest` (cd-pull smoke test,
  no writes, no network), `supplement-check` (weekly proposal).
- **The champion is frozen data** (candidate.json: Elo parameters, drift, no-result/tie rates, simulation
  settings, backtest metrics), so the daily forecast needs no Wikipedia; if MLflow is down it uses the
  copy cached in forecast.sqlite.
- **During the tournament:** fixtures carry the 2027 scorecard ids, so played results are taken from
  Cricsheet automatically (`overlay_results`) and the odds follow the event.
- **forecast.sqlite tables:** team_identities, model_versions, team_ratings, forecast_runs, forecast_team,
  forecast_inputs (matches new since the previous forecast: "why did the odds move?"), backtest_metrics,
  reliability_bins. Stable ids only.

## 3. Backtests and "good enough to publish"
### 3.1 What is tested
| Test | Sample | Why |
|---|---|---|
| **A. Rolling match-level:** every men's ODI, rating as it stood before the match | 2019-01 → today, ~900 decided matches | The only sample big enough to judge calibration |
| **B. World Cup matches**, ratings frozen on the eve of the tournament | WC 2019 (45 played) + WC 2023 (48) | The real use case, made before a ball was bowled |
| **C. Tournament outcomes**, pre-tournament simulation vs what happened | 2019 + 2023 (10 teams each) | Stage probabilities vs reality |

Tuning windows: everything before 30 May 2019 for the 2019 tests, everything before 5 Oct 2023 for the 2023 tests.
Test A uses walk-forward parameters, refitted each 1 Jan.

### 3.2 Measures
- **Brier score** (mean squared error of P(win)) and **log loss**, against two baselines: a coin flip (0.25 / 0.693)
  and a **win-rate model** (a logistic fit on each team's win % over the previous 24 months plus home/away). The win-rate
  model is our own "ranking-based baseline" from F1; ICC rankings aren't used because of the ICC's terms.
- **Reliability:** predicted vs observed win rate in 5 bins (0.5–0.6 … 0.9–1.0, the favourite's view), each showing
  its count, plus the calibration slope and intercept from a logistic recalibration.
- Tournament: Brier per stage (semi, final, champion) over all teams, and the log of the probability we gave to the
  actual champion (2019 England, 2023 Australia).
- MLflow logs every number, the reliability table and a PNG chart.

### 3.3 Publish bar (D4)
The model goes public only if all of these hold:
1. Test A: log loss and Brier beat **both** baselines.
2. Test A calibration: slope within 0.8–1.2, and no bin with n ≥ 30 off by more than 8 points.
3. Test B (both World Cups pooled): log loss no worse than the win-rate baseline.
4. Format and sum checks pass, and 2019 and 2023 replayed with their real results reproduce the real semi-finalists.
5. You review a "sanity sheet" (ratings top 14, title odds) and confirm it looks plausible, without changing any number.

Test C is published, with a note that 2 tournaments are too few to prove anything on their own. It is reported but is
not a gate.

## 4. Where it runs
```
05:30 DSM "cricstat daily refresh": pipeline recent && build && models forecast   (chained: forecast runs only after a good build)
        └─ cricstat-models forecast: new men's ODIs since the last forecast? no → exit 0 (seconds)
                                     yes → Elo replay with the champion's params → 50k sims → forecast.sqlite.new
                                           → checks → atomic swap → MLflow run in cricstat-wc2027-forecast
weekly/manual: cricstat-models train   → tuning + backtests A/B/C → MLflow cricstat-elo-backtest
                                        → gate vs the "champion" alias → alias moves only if nothing regresses
```
- **New service `cricstat/cricstat-models/`** (Python 3.12 image, numpy + mlflow-skinny + PyYAML; no pandas/sklearn
  needed for Elo). It is the `cricstat-models` container F6 already reserved: 172.25.0.15 plus ml-network .40 for
  MLflow. It runs and exits like the pipeline, with exit codes 0 / 1 / 2 (2 = forecast check failed, the old
  forecast stays live).
- **Output file `data/db/forecast.sqlite`, not the serving DB.** The pipeline owns `cricstat.sqlite`, and editing
  `serving_schema.sql` forces a 12-minute full rebuild. The models job writes its own small file with the same
  `.new` → checks → `os.replace` swap, and the API opens it read-only next to the serving DB. Tables: `team_identities`,
  `team_ratings`, `forecast_runs`, `forecast_team`, `forecast_moves` (which match moved whose odds), `backtest_*`,
  `supplement_results`. **They key on stable ids only** (team_uid from (name, gender, team_type), `match_id`,
  `player_id`), never on the serving surrogates, which a full rebuild can renumber; the API joins to the current
  build's keys. The placeholder `team_key`-based tables in `serving_schema.sql` are dropped at the next schema change
  that happens anyway.
- **MLflow** (the existing ML-domain tracker, public read-only): experiments `cricstat-elo-backtest` and
  `cricstat-wc2027-forecast`, and a registered model `cricstat-wc2027-predictor` with alias `champion`. The registered
  "model" is the parameter set plus the code version (a pyfunc wrapper). The daily job loads parameters **only** from
  the champion, and `train` can move the alias only through the §3.3 gates 1–4. The very first promotion also waits for
  your OK (gate 5).
- **CI/CD (same pattern as the pipeline/API):** `cricstat-ci.yml` gains `models-tests` (ruff + pytest on Python 3.12
  only, because it runs only in Docker) and `models-image` (non-root smoke test). Tests cover the Elo maths, the
  tournament formats against known results, seeded simulation snapshots, and a mini backtest on a fixture DB.
  `cricstat-models-publish.yml` has the `nas-production` approval gate. `cd-pull.sh` adds the service, and its NAS
  smoke test runs `cricstat-models selftest` against the real DB (no AVX: numpy wheels need SSE4.2 at most, which the
  J3455 has, but this has to be proven on the NAS).
- **DSM:** you append `&& … run --rm cricstat-models forecast` to the daily refresh task. I prefer chaining it to F6's
  separate 05:50 task, so it never runs on a half-finished build. `train` is manual at first and later weekly (Sunday,
  after register/enrich/build).
- **Admin:** `/admin/cricket` job status gains the forecast job (last run, champion version, the title-odds change).

## 5. API (F5 already lists these)
`GET /v1/forecasts/wc-2027/latest`, `/history?team=`, `GET /v1/ratings?scope=ODI&gender=male`,
`/v1/ratings/{team_slug}/history`, `GET /v1/models/predictor/backtest`. They use the same envelope, with
`model_version`, `mlflow_run_id`, `data_as_of` and `n_simulations` in meta, and ETag = forecast id. If
`forecast.sqlite` is missing, these return 503 and the rest of the API is unaffected.

## 6. On the site
- **Predictor page `/cricket/predictor/`** (replaces "ODI WC 2027 soon"). The headline is a board with the 14 rows
  (qualifier slots included), columns Super 7 · Semis · Final · **Champion**, sortable, with the followed team
  highlighted (view only). Tabs: Title odds over time (line chart; hovering a step shows the match that moved it) ·
  Ratings (Elo table + chart) · Format (the stages above as a diagram, with groups and fixtures) · How good is it?
  (the backtest summary, linking to Methodology). Stamp: "Updated <date> · data to <Cricsheet date> · 50,000
  simulations · model v<…>".
- **Team pages:** the existing "Ratings & ODI World Cup 2027 (Next)" card for men's ODI becomes live: current Elo,
  rank, a 2-year sparkline, and the chances of reaching the semis and of winning, linking to the predictor. Women's
  pages are unchanged.
- **Hub teaser:** "What are the chances of India lifting the 2027 ODI World Cup?" gets the real number for the
  followed team, e.g. "India: 17% · Elo baseline · updated 9 Oct". Line 2 stays honest: the ML and DL challengers are
  "coming", until they exist.
- **Methodology page `/cricket/methodology/`** (replaces "soon"; the About drawer's #predictor section links here).
  It covers: the model in plain words plus the formulas, all parameters and how they were tuned, backtest tables,
  the reliability chart, baselines, the MLflow run link, and a changelog of champion versions. Later it adds the
  three-model comparison and the analyst evals.
- **Limits, shown on the predictor page itself (not only in Methodology):**
  - A statistical estimate from past results, not a tip and **not betting advice**.
  - It knows nothing about squads, injuries or conditions (yet).
  - **Afghanistan:** Cricsheet withholds Afghanistan men's matches, as a protest over Afghan women's cricket (with a
    link to their article). "Afghanistan's results come from Wikipedia, are added after review and are rated by the
    same rule; their player stats are not in cricstat." Afghan players' pages and opponents' H2H get a one-line note.
  - The data starts in 2002, NRR is not modelled, and rain is a flat rate.
  - The same model applies to every team. India is the default view, not a thumb on the scale.
- SEO: the predictor and methodology pages go into the sitemap with their own title/description and Dataset/Article
  JSON-LD. The homepage ML card links to /cricket/predictor/ once it's live.

## 7. Steps (one branch `feat/cricstat-p1-elo`; I stop for your review after each one)
| Step | Deliverable | Review on |
|---|---|---|
| P1.0 | This plan | Decisions §10 |
| P1.1 ✅ built 2026-10-08, in review | Data layer: men's ODI extract, tournament configs (2019, 2023, 2027 + Qualifier) checked against the official fixtures, the Afghanistan supplement + crosswalks (`team_codes`, `supplement_venues`, `team_identities`) and its weekly check, data checks + tests | Configs, row counts, supplement source list |
| P1.2 ✅ built 2026-10-08, in review | Elo engine + tuning + backtest A, logged to MLflow (run on the NAS host or in a dev container) | Parameters, calibration, baselines |
| P1.3 ✅ built 2026-10-08, gate 5 pending | Tournament simulator + backtests B and C + the first 2027 forecast (offline) | Sanity sheet, publish bar |
| P1.4 ✅ built 2026-10-08, in review | `cricstat-models` service, forecast.sqlite, registry + gate, CI/publish/cd-pull, DSM text | CI green, NAS smoke test |
| P1.5 | API endpoints + tests | JSON on the dev API (8048) |
| P1.6 | Predictor, Methodology, team card, hub teaser in `tools/staging/web` | Preview (8090), section by section |
| Deploy | Merge `--no-ff`, publishes (models, API), cd-pull, DSM edit, rsync web, sitemap | Live check |

## 8. The ML and DL challengers later (P1b, P1c)
- **Same harness:** each challenger implements one function, `p_win(team_a, team_b, venue, as_of)`. It reuses the
  simulator, backtests A/B/C, the publish bar and the MLflow gate. The champion is chosen by **log loss + calibration on
  test A and test B pooled**. The comparison table (Elo vs ML vs DL, plus both baselines) goes on Methodology, and the
  winner powers the live forecast. Any challenger that doesn't beat Elo is still published as a result.
- **P1b ML (gradient boosting, scikit-learn HistGradientBoosting):** features = the Elo difference + home/away +
  **squad strength** from the XI's player atoms *as of the match date* (batting average/SR and bowling economy/SR over
  the last 2–3 years, caps, top-6 and attack summaries) + recent form. For 2027, squads come from each team's
  most-used XI in the last 12 months, then from the announced squads (~Sept 2027).
- **P1c DL (player embeddings):** a ball-by-ball sequence model trained on men's limited-overs deliveries (ODI + List A
  first, T20 as transfer learning) learns batter and bowler embeddings; squad strength = pooled embeddings → p_win.
  Training runs on the laptop (no AVX on the NAS; the Arc GPU via PyTorch XPU or CPU). The NAS only loads exported
  arrays and runs numpy at inference, proven by a NAS smoke test. The same model gives **in-match win probability**,
  shown on past matches (match pages). True live in-match odds need a live feed, which is out of v1's scope (F1).
- **Afghanistan in the challengers:** their ODI/T20I ball-by-ball data is withheld, so squad features are thin (only
  league cricket, e.g. Rashid Khan in the IPL). This is handled by one rule for every team: a team whose XI coverage
  falls below a threshold gets the Elo component only. It is disclosed, and backtest scores are also shown without
  Afghanistan games.

## 9. Risks
| Risk | Mitigation |
|---|---|
| The associate pool is over-rated | The D2 starting-rating rule + season regression; check the Qualifier odds against the record v Full Members |
| Overconfident tournament odds | σ rating noise; reliability published; the bar in §3.3 |
| The format still has unknowns (tie-breaks, the Qualifier winner's group) | Confirmed in P1.1 from the official playing conditions; the config marks anything assumed |
| Two World Cups are a tiny sample | Gate on test A (~900 matches); tournament scores are reported, not gated |
| Fan bias accusations | One rule set, no hand tweaks; the parameters and code are public |

## 10. Decisions (locked by the owner 2026-10-08)
- **D1 Afghanistan = S1, predictor only.** A results-only supplement from Wikipedia (188 ODIs, 19 Apr 2009 → 15 Aug
  2026; the checksum is the team-article infobox), kept outside the serving DB and used only for ratings, the predictor
  and backtests. Stable ids, crosswalks, provenance labels, restore and withdraw paths, colour badge (no flag), and
  "automatic detection, reviewed acceptance" for updates: see `P1-afghanistan-audit.md` §3, §5–§7.
- **D2:** associates start lower, by one rule on ICC status at first appearance, with Δ tuned on data.
- **D3:** simulate the Qualifier until 21 Mar 2027, then the real teams drop in.
- **D4:** the publish bar in §3.3 as written.
- **D5:** `models forecast` is chained onto the 05:30 daily task (no separate 05:50 task).

Sources: ICC format announcement (15 Jul 2026) icc-cricket.com/news/icc-revamp-formats-for-marquee-men-s-events;
ICC schedule release (1 Oct 2026) icc-cricket.com/media-releases/icc-men-s-cricket-world-cup-2027-schedule-revealed-and-ballot-system-opens;
en.wikipedia.org/wiki/2027_Cricket_World_Cup and /2027_Cricket_World_Cup_qualification (qualifiers, the Qualifier, venues).
