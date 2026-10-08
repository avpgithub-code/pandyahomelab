# P1 — Afghanistan men: entity audit before locking D1

Status: **approved 2026-10-08: D1 = S1 (predictor only)**, with every precaution in §3 and the design in §5–§7.
Method: every table in the live serving DB (build of 2026-10-08), raw `register_people`, the web assets and the API
were checked for Afghanistan. Afghan internationals come from Wikipedia's lists of Afghanistan ODI / T20I / Test
cricketers (87 men), resolved to ESPNcricinfo ids through Wikidata (P2697), then to Cricsheet ids through the Register.

## 1. Why it's missing
Cricsheet withholds every match involving the Afghanistan men's team or played in the Afghanistan Premier League:
379 matches on cricsheet.org/matches/ today. This is a protest over Afghan women's cricket (article of 14 Nov 2024).
Nothing **involving** Afghanistan exists anywhere in our data. Its players appear only through matches they played for
other sides (mostly T20 leagues).

## 2. Entity by entity
| Area | Tables | What's there for Afghanistan | Gap | Can a results-only feed fill it? |
|---|---|---|---|---|
| Team identity | `teams` (533) | **No row** (men or women; Afghanistan has no women's team, which is the point of the protest) | Countries page, ratings, predictor | Identity only (name, gender, type), **outside** the serving DB |
| Competitions | `competitions` (1,111) | No Afghanistan Premier League (withheld); World Cups, Asia Cups etc. exist | None for P1 | Not needed |
| Venues | `venues` (971) | Afghanistan's "home" grounds abroad exist (Sharjah, Abu Dhabi, Lucknow, Hambantota, Doha); no ground in Afghanistan has hosted an ODI | Some "home" grounds may be missing (e.g. Greater Noida, Dehradun) | Only a venue **country** is needed, using `venue_map.csv` names |
| Players | `players` (13,711), `player_external_ids`, `player_names`, `player_bio` | **30 of 87** Afghan internationals have a row (they played in a covered league/match, e.g. Rashid Khan, Nabi, Gurbaz); they are enriched from Wikidata like everyone | **37** are in the Register only (no covered match → no row, by design, e.g. Hashmatullah Shahidi, Rahmat Shah); **20** didn't resolve in this quick pass (Wikipedia disambiguation) | Not without scorecards. Results don't create players |
| Player ↔ team | `player_teams` | Clubs only (Rashid: Gujarat Titans, SRH, Adelaide…); never Afghanistan. Rashid's single T20I is for the 2018 ICC World XI | The team chip on their pages shows a franchise | No |
| Player stats | `batting_innings`, `bowling_innings`, `fielding_events`, `phase_stats`, `player_career`, `player_year`, views `v_player_*` | League stats only | Afghan players' entire ODI/T20I/Test careers; **every other player's** matches v Afghanistan (e.g. Kohli's T20I 122*) | **No.** These are derived from ball-by-ball data, and none exists |
| Match facts | `matches`, `innings`, `deliveries`, `dismissals*`, `match_players`, `player_of_match`, `match_officials`, `reviews`, `powerplays`, `replacements` | Nothing | Everything | Only the result-level facts (date, teams, venue, result, method), kept **separate** |
| Team aggregates | `team_results`, `v_team_record`, `v_head_to_head` | Nothing | Every team's record and H2H v Afghanistan | Possible, but it would mix sources inside public stats (see §4) |
| Predictor | `team_ratings`, `forecast_*` | Empty (P1) | Afghanistan's rating; opponents' games v Afghanistan | **Yes. This is what D1 is for** |
| Site | Countries, Players, hub, golden figures | Already disclosed: players page note, licences note, API `coverage`, golden "explained" rows; colour badge AFG (#0B3D91/#D32011) in `cricstat.js`; **no flag file** | No Afghanistan team page; Afghan players' pages show leagues only, with no note on the page itself | Notes, yes; stats, no |

## 3. Design precautions (apply whatever scope you choose)
1. **Stable IDs only across stores.** `team_key`, `match_key` and `player_key` are build surrogates (rowid in load
   order, `serving_store.py:93`), so a full rebuild can renumber them. Anything outside the serving DB keys on:
   match → ESPNcricinfo `match_id` (Cricsheet's own id space); team → (name, gender, team_type); player → Cricsheet
   8-hex `player_id`. **This also applies to the P1 forecast tables:** `team_ratings` / `forecast_team` in
   serving_schema.sql use `team_key` and must not be copied as-is into `forecast.sqlite`. Store team identity, and let
   the API join to the current build's `team_key`.
2. **Players are joined by id, never by name.** This audit's own quick name match got it wrong: "Zahir Khan" on
   Wikipedia's Afghan list resolved to India's Zahir Khan (132 ODIs), and the Register has two "Rashid Khan"s.
   The chain is ESPNcricinfo id → Register `key_cricinfo` → Cricsheet id; a row that doesn't resolve stays
   unresolved and is reported.
3. **Provenance on every row and field:** `source = 'cricsheet' | 'supplement:wikipedia'`. The API and pages label any
   supplement-derived number. Supplement rows never enter Cricsheet-derived tables, metrics, the golden checks or the
   `matches = raw` build gate.
4. **Restore path:** if Cricsheet restores a match, its `match_id` appears in `matches` and the supplement row is
   ignored automatically. A check reports the overlap so the file can be trimmed.
5. **Withdraw path:** deleting the one supplement file (plus a forecast rerun) removes every trace, so a later change of
   heart costs nothing.
6. **Flag:** keep the colour badge, as with West Indies. Afghanistan's flag is politically contested (the 2021
   change of government; the cricket team still plays under the tricolour), so a "national flag" would pick a side.
7. **Respecting the protest's spirit:** use Afghanistan's results only where leaving them out would make the forecast
   unfair to **other** teams (ratings, predictor, backtests). Don't rebuild Afghanistan's stats presence on the site.

## 4. Scope options for D1
| Option | Afghanistan appears in | Effort | Fit with Cricsheet's protest |
|---|---|---|---|
| **S1 Predictor only (recommended)** | Ratings, predictor, backtests (labelled "results from Wikipedia"); a one-line note on Afghan players' pages and opponents' H2H | Small | Closest: uses the facts only where fairness needs them |
| S2 + results-only team page | S1 + `/cricket/countries/afghanistan-men/` with record + results list, labelled; no player stats | Medium; also makes other teams' pages look inconsistent (their H2H still lacks AFG) | Re-creates a public Afghanistan stats page |
| S3 full stats | Players' international careers, scorecards | Not possible: needs ball-by-ball, which only Cricsheet (withheld) or terms-restricted sites have | — |

## 5. Relationship (crosswalk) tables: where they are needed
Inside the serving DB, each stable id is already unique in its own table, so that table **is** the 1:1 map from
stable id to surrogate key: `matches.match_id` (UNIQUE), `teams (name, gender, team_type)` (UNIQUE), `players.player_id`
(UNIQUE). `player_external_ids` (player_key, source, external_id) is the existing crosswalk to ESPNcricinfo and 11
other sites. So **no extra relationship table is needed for the ids themselves**. The API resolves stable id →
current surrogate on every request.

Crosswalks **are** needed where the supplement and our data name things differently. They live in the models domain:
| Crosswalk | Maps | Why | Integrity check |
|---|---|---|---|
| `team_codes.csv` | Wikipedia `{{cr|UAE}}` code → `teams.name` (male, international) | Wikipedia writes UAE, USA, PNG; we store "United Arab Emirates", "United States of America", "Papua New Guinea" | Every code used in the supplement maps; every target exists in `teams`, except Afghanistan, which is listed in `team_identities` |
| `team_identities` (in `forecast.sqlite`) | team_uid (e.g. `afghanistan-men`) ↔ (name, gender, team_type), with `in_serving` 0/1 | One stable team id for ratings and forecasts, including Afghanistan, which has no `team_key` | UNIQUE (name, gender, team_type); every rated team resolves; composite sides (Asia XI, Africa XI, ICC World XI) are excluded from Elo |
| `supplement_venues.csv` | Wikipedia venue link → country (the `venue_map.csv` country names) | Ground names differ between sources; only the country is needed for home/away | Every supplement row has a country; country names exist in `venue_map.csv` |
| `player` crosswalk | Not needed for S1 (no players in the supplement) | If a challenger ever needs Afghan squads: ESPNcricinfo id → `player_external_ids` → `player_id` | Unresolved ids are reported, never guessed |

SQLite can't enforce foreign keys across two files (ATTACH ignores them), and the build already runs with
`foreign_keys=OFF` and counts violations instead. The models job does the same: every check above runs on each load,
and a failure exits 2 with the old forecast kept. Inside `forecast.sqlite` itself, `PRAGMA foreign_keys=ON` is used.

## 6. Loading jobs and CI/CD for the Afghanistan supplement
**Precaution first:** anyone can edit Wikipedia, so automatic ingestion would let one vandal edit move our forecast.
Rule: **detection is automatic, acceptance is a reviewed commit.**

| Where | What runs | Afghanistan part |
|---|---|---|
| Files | `cricstat/cricstat-models/supplement/afg_odi_results.csv`, `team_codes.csv`, `supplement_venues.csv`, `afg_totals.csv` (the checksum: played/W/L/T/NR overall and this year, from the infobox of the "Afghanistan national cricket team" article; the separate records page is stale, "as of" Oct 2025 with 176 ODIs) | Owned by the models image, **not** `cricstat/sql/`: no pipeline publish, no change to `rules_sha`, no serving rebuild |
| Daily 05:30 (chained) | `pipeline recent && build && models forecast` | `forecast` loads the supplement from the image and runs §5 checks plus an anti-join with live `matches` (a restored Cricsheet match wins; the overlap shows on admin) |
| Weekly Sun 06:00 | `register && enrich && build && models supplement-check` | Fetches the team-article infobox totals and this season's Afghanistan series articles (MediaWiki API, 1 req/s, UA with privacy@) → compares with the CSV → writes a **proposal** (new/changed rows + diff) to the log, `/admin/cricket` and the weekly report email. It changes nothing by itself |
| Monthly day 1 | `full && build --full && models forecast --force` | A full rebuild may renumber the surrogate keys; the forecast replays from stable ids. A test pins this (two builds, different key order, same forecast) |
| Accepting a proposal | Branch → edit CSV → PR | Reviewed by you; the source URL is required on each row |
| CI (`cricstat-ci.yml`, job `models-tests`) | ruff + pytest | CSV schema (columns, enums, ISO dates, unique `match_id`, Afghanistan on one side); every code/venue resolves through the crosswalks; overall and this-year totals equal `afg_totals.csv`; no row dated after the commit |
| Publish (`cricstat-models-publish.yml`) | Paths `cricstat/cricstat-models/**` (supplement included); `nas-production` approval gate | A supplement update = one models publish |
| CD (`cd-pull.sh`) | NAS smoke test `cricstat-models selftest` against the real DB | Runs the §5 checks against live `teams`/`matches`; a failure rolls back to `:previous` |
| Admin | Job status | Supplement rows, last check, pending proposal, Cricsheet-restored overlaps |

Latency: a new Afghanistan ODI reaches the forecast after the weekly check, your review and a publish, so up to a few
days. That's acceptable for a handful of matches a year, and it's disclosed ("Afghanistan results are added after
review"). During the World Cup itself (Oct–Nov 2027) the check can run daily.

## 7. Time spans (checked 2026-10-08)
| Data | From | To | Matches |
|---|---|---|---|
| Our DB, all matches | 19 Dec 2001 | 7 Oct 2026 | 23,008 |
| Our DB, men's ODIs | 27 Jun 2002 | 5 Oct 2026 | 2,581 (1,904 since 19 Apr 2009) |
| Afghanistan men's ODIs (Wikipedia infobox) | 19 Apr 2009 (v Scotland, Benoni) | 15 Aug 2026 (v Ireland, Belfast) | **188**: 93 W, 88 L, 1 T, 6 NR; 7 in 2026 |

Afghanistan's whole ODI history sits inside our window, so there is no span to extend and no gap at either end.
Since April 2009 the supplement adds about 10% to the men's ODI rows (188 on 1,904). To check in P1.1: whether the
188 include matches abandoned without a ball (e.g. Ireland v Afghanistan, 5 Aug 2026). Cricsheet leaves those out,
so the supplement keeps them as `no_result` with `has_play = 0`, and Elo skips them either way.

## 8. As built in P1.1 (2026-10-08)
- **Source of rows:** Wikipedia's "International cricket in <season>" pages (38 pages, 2008–09 to
  2026–27), not one article per series: they list every ODI with its official number and scorecard id.
  The parser was tested on every ODI they list: **1,982 of 1,985** overlapping Cricsheet matches agree on
  date, teams, result and winner; the differences are Wikipedia rows linking the wrong scorecard.
- **Second source:** each row is compared with the match box in its series/tournament article.
  178 of 193 rows confirmed; 15 need a reviewer (2 one-day date differences in 2010; 9 rows with no
  series article found; the 4 Asia Cup 2014 games, whose article has no match boxes).
- **Checksum:** the team article's "ODI record versus other nations" table (current to 15 Aug 2026),
  not the stale records page. Reconciled exactly per opponent and in total: 188 = 93 W, 88 L, 1 T, 6 NR,
  plus 5 fixtures abandoned without a ball (kept as `has_play = 0`, not counted).
- **Id hazards found:** the same ODI number on two matches (a season page mislabels three 2022 UAE
  tri-series games as ODI 4631–4633, the real Asia Cup 2023 numbers), and one scorecard id on two
  matches (England v Sri Lanka 2015 links Australia v Afghanistan's id). Rows are therefore keyed by
  scorecard id + teams, and an Afghanistan row's id must not exist in Cricsheet.
- **Restore path, implemented:** a Cricsheet match involving Afghanistan replaces the supplement copy
  automatically; the checksum then counts both sources together.
- **Reviews (2026-10-08):** the owner accepted the 15 unconfirmed rows. Decisions live in
  `supplement/reviews.csv` (two 2010 dates corrected to the series article's date); every draft applies
  them, so a review is never redone. If Wikipedia later changes an overruled value, the row is flagged.

## 9. What a full reload or rebuild does to the supplement
| Event | Effect on the Afghanistan data | Work needed |
|---|---|---|
| Daily `recent` + `build`, weekly `register/enrich/build`, monthly `full` + `build --full` | None: the supplement isn't in raw.sqlite or cricstat.sqlite; the jobs never write it | None. Surrogate keys may renumber; the supplement uses stable ids |
| Serving DB deleted and rebuilt from scratch | None (same reason) | None |
| Cricsheet restores Afghanistan matches | Their rows replace the supplement copies automatically | Optional tidy-up later |
| New Afghanistan ODI | Weekly `supplement-check` proposes the row (about a minute; Wikipedia pages cached for a day) | Review the proposal, commit, publish the models image |
| NAS lost / repo re-cloned | Everything (CSVs, crosswalks, reviews) is in git | None |
| Wikipedia restructures its season pages | The weekly check reports a diff or parse issues; the committed data keeps serving | Fix the parser; past reviews still apply |
