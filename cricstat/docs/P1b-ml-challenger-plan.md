# P1b — the machine-learning challenger: plan

Status: **draft for the owner's review (2026-10-10)**, branch `feat/cricstat-p1b-ml`. Nothing is built yet.
Builds on `P1-predictor-plan.md` (§2 Elo, §3 backtests + publish bar, §8 challenger harness) and the live P1
baseline (champion `elo-v2`, MLflow `cricstat-wc2027-predictor`). Decisions for the owner are collected in §11.

## 1. What this phase answers
"Does knowing **who is playing** (squads, player form) predict ODI results better than cricstat Elo, which only
knows team results?" The challenger runs through the same backtests A/B/C, gates and MLflow promotion. It replaces
Elo only if it wins on log loss **and** calibration (§8). Otherwise the comparison is published on the methodology
page as a result. A well-run "no, it doesn't help" is a finding worth showing.

## 2. Facts this plan rests on (checked 2026-10-10 on the live serving DB, build 10)
- **Team sheets:** `match_players` has the XI for every men's ODI (5,052 team sheets of 11, 110 of 12 with a
  concussion/super-sub). Batting and bowling atoms (`batting_innings`, `bowling_innings`) carry `start_date`, so
  every player stat can be cut off at any date.
- **XI coverage** (share of an XI with ≥ 5 ODI appearances in the 3 years before the match), men's ODIs since 2007:
  about 85% on average. Full Members 0.83–0.90, associates 0.42–0.81. Under 50% in about 4% of team-matches
  (2021: 14%, the COVID-era squads). **Afghanistan: 0%, always.** Every Afghanistan ODI is withheld, and the
  supplement holds results only, with no XIs.
- **Feasibility probe** (scratch code, not the deliverable; logistic regression on top of the Elo prediction,
  trained 2008–18, tested 2019+, about 820 matches, log loss):
  | Model | Actual XI | Projected XI |
  |---|---|---|
  | Elo alone (recalibrated) | 0.6087 | 0.6090 |
  | Elo + batting, bowling and caps | 0.6306 | 0.6244 |
  | Elo + bowling only | 0.6092 | **0.6071** |
  | Elo + caps only | 0.6314 | 0.6231 |
  | Elo + "selection gap" (actual XI strength − usual XI strength) | 0.6091 | n/a |

  Lessons: (1) **caps/experience drifts with the era**: the XIs' mean log-caps fell from 5.5 to 5.0 after 2019 because
  fewer ODIs are played, so a coefficient learned before 2019 misfires after it. Raw batting rates drift as well.
  Features must be **era-normalised**, and caps are left out. (2) Bowling-attack quality is the only feature with a
  hint of signal. (3) Rotated or weakened XIs didn't add anything once Elo was known.
  **Honest expectation: the challenger will probably match Elo, or beat it by very little.** The design below is
  built to make that answer trustworthy whichever way it goes.
- **Libraries on the NAS (no AVX, SSE4.2 only), proven 2026-10-10** inside the running `ml-titanic-automl`
  container (Python 3.10): scikit-learn 1.4.2 `HistGradientBoostingClassifier` with monotonic constraints, and
  LightGBM 4.7.0 with `init_score`, both train and predict correctly. The models image is Python 3.12 and
  **stdlib-only today**, so the exact wheels still have to be proven by the cd-pull NAS smoke test (§9).

## 3. Model design
### 3.1 Boost on top of Elo, not instead of it
`logit P(team1 wins) = elo_logit(R1 − R2 + H·h) + f(features)`.
The Elo part is the champion family's formula, with parameters tuned on data before each cutoff (exactly as in
P1.2). The trees learn only the **correction** `f`. This is boosting from an initial score (LightGBM `init_score`).
Why this way:
- With about 2,000 training matches, trees struggle to rebuild the smooth Elo curve; a model that starts from Elo
  and shrinks toward it defaults to Elo when the features carry no signal.
- **The simulator stays an Elo simulator.** `f` does not take the Elo difference as an input, so for a given
  pair, venue and date it is one number. It becomes a per-pair **offset in Elo points**
  (`f · 400 / ln 10`), added in `simulator._match` and in test B. Rating noise σ, in-tournament updates
  (`k_update`), no-result rates and knockout rules work unchanged.
- **Symmetric by construction:** features are team1 − team2 differences; training uses both orientations with
  the label flipped; prediction averages `f(a,b,h)` and `−f(b,a,−h)`. Team order carries no information, as in
  the win-rate baseline.
- **Monotonic constraints:** a better attack or batting line can never lower a team's chance. This avoids
  embarrassing quirks and matches the "one rule, no thumb on the scale" promise.

### 3.2 Features (pre-registered: this list is fixed before any test is run; §5 rule 6)
All are team1 − team2 differences, computed for the **projected XI** (§4) from men's ODIs with
`start_date < match date`.
| Feature | Definition | Constraint |
|---|---|---|
| `bat` | Mean of the top 7 batting values in the XI. A player's batting value is runs per dismissal × runs per ball over the last 3 years, **as a z-score against all men's ODI batters in the same 3-year window** (era-normalised), shrunk to 0 with weight n/(n + 10) innings | + |
| `bowl` | Mean of the top 5 bowling values: runs conceded per ball and balls per wicket, z-scored in the window the same way, shrunk with weight balls/(balls + 300), sign flipped so that higher is better | + |
| `form` | The sum of Elo surprises (S − E) over the team's last 10 ODIs. If Elo's K is right, this carries nothing; it tests whether Elo misses momentum | none |
| `h` | home / away / neutral (the trees may adjust Elo's single home term by context) | none |
| `coverage` | Share of the projected XI with ≥ 5 ODI appearances in the window (lets the trees trust thin squads less) | none |
Left out on purpose: caps/experience (era drift, §2), the toss and batting first (not known before the match), venue
scoring level (it changes margins, not who wins; P1 §2.6), bowling style (§11 D6).

### 3.3 Libraries and hyperparameters
- **LightGBM** (recommended, §11 D1): it supports `init_score`; its model is saved as **plain text** (`model_to_string`), so no
  pickle is loaded from MLflow; it runs on the NAS (§2). It adds numpy, scipy, lightgbm and the `libgomp1` package
  to the models image (about +80 MB).
- **Diagnostic row (no new library):** a logistic regression on the same features over the Elo logit, with the
  existing stdlib `metrics.logistic_fit`. If boosting doesn't beat a straight line, that is worth saying too.
- **Small fixed grid:** num_leaves {4, 8}, learning_rate {0.03, 0.1}, min_data_in_leaf {40, 80}, lambda_l2 {1, 10},
  rounds by early stopping. Choices are made **only** on a validation slice at the end of each training window
  (the last 2 years before the cutoff). Test A and test B are never used to pick anything.

## 4. Squads: what XI the model assumes
- **Projected XI (every backtest and the live forecast, one rule):** the 11 players with the most appearances in
  the team's last 10 men's ODIs before the as-of date; ties go to the more recent appearance. It is computed from
  data with no hand edits, so it lags a retirement or an injury by a few matches. That limitation is disclosed.
- **Why not the actual XI:** XIs are announced at the toss. The predictor forecasts before the match, and the 2027
  forecast weeks or months ahead. Training on actual XIs and forecasting on projected ones would be a
  train/serve mismatch. The probe shows no measurable cost (0.6087 v 0.6090). The actual-XI score is still logged
  as a diagnostic ("what knowing the XI at the toss would add").
- **For 2027:**
  1. **Until squads are announced** (about Aug–Sep 2027): the projected XI from each team's last 10 ODIs.
  2. **After that:** a reviewed `tournaments/wc2027/squads.csv` (team, player_id, announced_on, source_url,
     replaced_by) taken from Wikipedia's "2027 Cricket World Cup squads" article (facts; credited, CC BY-SA text not
     copied). The projected XI is the 11 of the announced 15 with the most appearances in the last 10 ODIs.
     Replacements are edits to the file, reviewed like the Afghanistan supplement ("automatic detection, reviewed
     acceptance"). **Ids are resolved, never names:** Wikipedia → Wikidata P2697 (ESPNcricinfo id) → Register
     `key_cricinfo` → Cricsheet `player_id`. Any player who can't be resolved is listed for review, never guessed.
  3. **Backtests B/C, matched to the live path (D3):** the same squads files for WC 2019 and 2023 (10 teams × 15
     each), so the announced-squad step is tested on the past tournaments before it runs live.
- The predictor page can show "the XI the model assumes" per team: transparent, and a fan feature (P1b.4,
  optional).

## 5. Leakage rules (each one is a unit test)
1. **Strictly before:** every feature for a match on date D uses only matches with `start_date < D`.
   Same-day games don't see each other.
2. **Time-travel test:** features for a match computed from the full DB must equal those computed from a copy
   truncated at that date. This is run on a sample of matches in CI on the fixture DB.
3. **Era normalisation** (means/SDs of player rates) uses only the same lookback window before D.
4. **The Elo prior** inside the challenger uses Elo parameters tuned on data before the cutoff (P1.2's grid,
   walk-forward per year for test A, eve parameters for test B), never the current champion's parameters.
5. **Walk-forward:** test A refits the challenger each 1 January on data before that year; hyperparameters are
   chosen on the last 2 years of the training window only.
6. **Pre-registration:** the features (§3.2), grid (§3.3), fallback threshold (§6) and promotion rule (§8) are
   committed to the repo (`ml/spec.json`) **before** the first test-A score is computed. Every variant ever run
   is logged in MLflow and listed in the published table. No quiet cherry-picking against the test years.
7. **No later knowledge:** nothing from Wikidata or the Register that describes a player "as of now" (role,
   retirement) enters a feature. Squads files carry `announced_on` and are used only from that date.
8. **Supplement rows** (results-only) never get invented features; they fall under §6.

## 6. Afghanistan and thin squads: the coverage rule (one rule for every team)
- If **either** team's projected-XI coverage is **below 0.6**, the challenger's correction is 0 and its
  prediction **is the Elo prediction** for that match. Such matches are also left out of training.
- **Afghanistan is always below** (0%), and so are its supplement opponents' matches, which have no XIs. In 2027,
  Afghanistan's matches therefore use cricstat Elo only. Other teams fall under the rule now and then (Canada,
  Hong Kong, some associates; the 2021 COVID squads).
- **Why 0.6:** it is fixed before testing, not tuned on test results. Measured on actual XIs since 2007
  (Cricsheet rows only), both teams clear it in 94% of Full Member v Full Member matches and 88% of all matches;
  the thinnest associate XIs drop out. P1b.1 re-measures it on projected XIs.
- **Reported three ways:** all matches; **without Afghanistan** (as for Elo today); and the "**ML-active**"
  subset where the challenger actually differs from Elo. The fallback dilutes the overall difference, so that
  subset is where the comparison is judged fairly.
- **Disclosed** on the predictor and methodology pages: "For Afghanistan's matches the machine-learning model falls
  back to cricstat Elo: Cricsheet withholds their scorecards, so the model can't see their players." Link to
  Cricsheet's article, as now.

## 7. MLflow
- **New experiment `cricstat-ml-backtest`:** one run per `train --family gbm` (run name `gbm-backtest-YYYY-MM-DD`),
  tagged with git sha, data_as_of, build_id and spec hash. Params: the spec and the chosen hyperparameters per
  window. Metrics: tests A/B/C for the challenger, the Elo it is compared with, both baselines and the logistic
  diagnostic, and the three subsets of §6. Artifacts: `spec.json`, `model-<window>.txt` (LightGBM text models),
  `feature_importance.csv`, `test_a_predictions.csv` (both models side by side), `reliability.svg` (Elo v ML),
  `variants.csv` (§5 rule 6), `coverage.csv`, `bootstrap.json`. No child-run explosion, like P1.2.
- **Registry:** still **one** registered model `cricstat-wc2027-predictor` (it is "the thing that powers the
  forecast"). A challenger version is registered with tag `family=gbm` and alias **`challenger-gbm`**; the
  `champion` alias moves only by §8. Version labels become `<family>-v<n>`: the version counter is shared, so the
  first GBM version would be `gbm-v3`. `forecast_service.load_champion` currently hard-codes `elo-v%s`; it will
  read the family.
- `cricstat-wc2027-forecast` stays the experiment for daily forecasts. It records the champion family.

## 8. Comparison table and promotion
**The table** (methodology page, API, MLflow), one row per model:
| | Test A log loss / Brier / accuracy | Calibration slope · worst bin | A without AFG | A, ML-active subset | Test B pooled | Test C P(champion) 2019 · 2023 | Verdict |
|---|---|---|---|---|---|---|---|
| Coin flip · Win-rate baseline | … | | | | | | baseline |
| **cricstat Elo** (champion) | … | | | | | | champion |
| **ML challenger** (gbm-vN) | … | | | | | | promoted / not promoted, and why |
| Logistic on the same features | … | | | | | | diagnostic |
Plus a paired-bootstrap interval for "ML − Elo" log loss, and a reliability chart with both models.

**Promotion across families (stricter than the same-family rule, D4).** A challenger replaces Elo only if **all**
hold:
1. It passes publish gates 1–4 on its own (§3.3 of the P1 plan).
2. **Log loss:** pooled test A + B log loss is lower than the champion's by **≥ 0.002**, and Brier is not worse.
3. **Not luck:** in a paired bootstrap over matches (5,000 resamples), the improvement is above 0 in **≥ 95%** of
   them.
4. **Calibration:** its slope is in 0.8–1.2 and no further from 1 than Elo's + 0.05; its worst bin (n ≥ 30) is
   no more than 2 points worse than Elo's.
5. Test B pooled is no worse than Elo's + 0.005 (as today).
6. **Owner gate 5 again:** a family change is a first champion, so the sanity sheet needs your OK
   (`--owner-approved`).
After that, retrains of the same family use today's no-regression rule. If the challenger fails any step, Elo
stays champion, the challenger keeps alias `challenger-gbm`, and the table says which step it failed.

**Storage and API:** `forecast.sqlite.backtest_metrics` and `reliability_bins` already have a `model` column
(today elo / win_rate / coin), so the challenger's rows go in with `model = 'gbm'` (and `'logistic_squad'`) and
**no schema change** is needed. `GET /v1/models/predictor/backtest` gains an additive `comparison` block (rows above +
bootstrap + verdict). The API stays backward compatible.

**If the GBM wins:** the daily forecast loads the family from the champion. It replays Elo with the embedded
parameters, builds projected XIs as of today, computes pair offsets for the 20 possible teams (14 + Qualifier
candidates), and simulates. The fingerprint gains the XIs and the squads.csv hash. Ratings pages still show
cricstat Elo; the predictor copy changes to "forecast: cricstat Elo + squad model". If LightGBM fails to import,
the forecast **keeps the last good forecast and exits 2** (no silent fallback that changes the model).
**If it loses:** nothing on the forecast changes; the methodology page gains the comparison and a plain verdict.

## 9. Where it runs
- **Image:** `cricstat-models` gains numpy, scipy, lightgbm (pinned versions) and the `libgomp1` package. The Elo
  path keeps working without them (imports are lazy). `selftest` imports LightGBM and trains and predicts a tiny
  model, so **cd-pull's NAS smoke test proves the no-AVX wheels** before the image goes live.
- **Training:** `train --family gbm` (manual at first). Features for about 2,600 matches take about 10 s on the NAS
  (probe), and LightGBM on 2,000 rows takes milliseconds, so the whole walk-forward grid should finish in minutes on
  the NAS. No laptop is needed (unlike P1c).
- **CI:** models-tests run on Python 3.12 with the new requirements; tests for features, leakage (time travel),
  symmetry, monotonicity, fallback, the pair-offset simulator path (an offset of 0 must reproduce Elo's numbers
  exactly), the promotion rule, and a mini walk-forward on the fixture DB.

## 10. Steps (branch `feat/cricstat-p1b-ml`; I stop for your review after each)
| Step | Deliverable | Review on |
|---|---|---|
| P1b.0 | This plan | §11 decisions |
| P1b.1 | **Feature layer:** projected XI, era-normalised player values, form, coverage, `ml/spec.json`; leakage + time-travel tests; coverage report per team/year; squads.csv for WC 2019/2023 (if D3) via the id route; the Wikidata bowling-style coverage check (D6) | Feature samples (e.g. India v Australia on the 2023 eve), coverage table, squads files |
| P1b.2 | **Model + harness:** the `p_win` / pair-offset interface in the simulator and test B; LightGBM correction + logistic diagnostic; walk-forward test A, tests B/C; bootstrap; MLflow `cricstat-ml-backtest`; image deps tested in a dev container | **The comparison table** (first time anyone sees test scores) |
| P1b.3 | **Promotion + forecast:** family-aware champion loading, §8 rule, `challenger-gbm` alias, comparison rows in forecast.sqlite, selftest, CI, publish, NAS smoke test | CI green, NAS smoke test, the promotion decision (and gate 5 if it wins) |
| P1b.4 | **API + pages:** `comparison` block; methodology "Elo v machine learning" section (table, both reliability curves, verdict in words); predictor "How good is it?" and hub/About copy updated with the outcome; optional "XI the model assumes" | Preview (8090), section by section |
| Deploy | Merge `--no-ff`, publishes (models, API), cd-pull (models first), `train --family gbm` on the NAS, `forecast --force` only if promoted, rsync web | Live check |

## 11. Decisions for the owner
- **D1 Library:** LightGBM (recommended: initial-score boosting on top of Elo, plain-text model files, proven on
  the NAS) **or** scikit-learn HistGradientBoosting (the name in P1 §8). HGB has no initial score, so it would have
  to learn the Elo curve itself from about 2,000 matches, and the simulator would need a lookup table over rating
  differences.
- **D2 XI rule:** projected XI everywhere (recommended), with the actual XI logged as a diagnostic only.
- **D3 Squads files for WC 2019/2023:** build them, so backtests B/C test the same announced-squad path as 2027
  (recommended; about 300 rows, reviewed) **or** use the projected-XI rule only for the past tournaments.
- **D4 Promotion rule:** the stricter cross-family rule in §8 (≥ 0.002 log loss, 95% bootstrap, calibration no
  worse, gate 5).
- **D5 Coverage threshold:** 0.6, fixed before testing; Afghanistan always falls back to Elo.
- **D6 Bowling style (pace/spin share of the attack):** not in v1 (recommended). Wikidata coverage is patchy, and
  every extra feature is another fork. P1b.1 measures coverage, and if it is ≥ 90% it can be pre-registered for a
  **v2** spec, published as its own row.
- **D7 "The XI the model assumes" on the predictor page:** yes / later.

Sources: P1 plan and audit (this folder); feasibility probe and NAS library check run on 2026-10-10 (scratch, not
committed; numbers above).
