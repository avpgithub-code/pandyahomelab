# cricstat — Project Context

Cricket statistics and ML project, part of pandyaHomeLab (Synology NAS, pandyahomelab.com).
This file carries over decisions from a planning conversation in claude.ai (Oct 2026).

## Goal
Build a legally clean cricket data pipeline on the NAS, then ML models
(e.g. win probability, player role/bowling-type classification) and a
public demo on pandyahomelab.com.
Primary purpose (2026-10-05): showcase ML, DL, NLP **and LLM** engineering to recruiters. Planned products:
country stats, player profiles, an ODI World Cup 2027 winner predictor (live-updating), and an LLM
"Ask the Analyst" agent with published eval scores.

## Data sources (decided)
| Source | Use | Access | License / terms |
|---|---|---|---|
| Cricsheet (cricsheet.org) | Primary: ball-by-ball match data | Bulk zip downloads, no API, no key | ODC-BY 1.0 stated on Register page; match-file license not explicitly stated (third parties cite ODC-BY / CC BY 3.0). Attribution required. |
| Cricsheet Register (people.csv) | Player identity + cross-site IDs (incl. Cricinfo ID) | Download | ODC-BY 1.0 |
| Wikidata | Player bio metadata (DOB, birthplace, country, image) | SPARQL: https://query.wikidata.org/sparql (no key) | CC0 |
| CricketData.org (CricAPI) | Optional: live scores / player profiles demo | REST API, free tier 100 calls/day | Provider terms |
| Sportmonks | Optional: learning sandbox only | REST API, free plan = T20I, BBL, CSA T20 Challenge | Provider terms |

### Sources to AVOID (terms prohibit automated / bulk use)
- ESPNcricinfo / Statsguru — terms prohibit high-volume automated use and transferring content.
- icc-cricket.com — terms cover data; personal-use extracts only, no modification, no commercial use.
- Cricbuzz, howstat — no sanctioned access.
Use these only for manual reference/validation.

## Cricsheet facts
- ~22,983 matches (18,316 men's, 4,667 women's), 2001–2026; dense from ~2012.
- Formats: ~919 Tests, 3,187 ODIs, 5,729 T20Is, plus 40+ leagues (IPL 1,243, BBL 662, T20 Blast, PSL, CPL, SA20, The Hundred, WPL, MLC...).
- Gaps: Afghanistan men's & Afghanistan Premier League matches withheld (379 on 2026-10-08; a protest over Afghan women's cricket, see cricsheet.org/article/explanation-for-withholding-of-afghanistani-matches/, 14 Nov 2024); completed matches only (~1 day lag); no player bio data.
- Match files named by match_id, usually the ESPNcricinfo match ID, BUT 25 ids are non-numeric (`wi_*`, West Indies
  women's domestic matches). Never assume match_id is numeric; it is TEXT everywhere.
- match_type values: T20 (14,274), ODI (3,187), MDM (2,217), ODM (2,066), Test (919), IT20 (320) as of 2026-10-05.
  MDM/ODM = multi-day/one-day domestic; IT20 = T20s between non-full members. `info.event` is missing on 89 matches.
- Player stats (batting, bowling, fielding, phase, matchups) must be DERIVED from ball-by-ball data.

## Player metadata join
Match JSON `info.registry.people` -> Cricsheet person ID -> Register `people.csv`
(Cricinfo ID column, verify exact header e.g. key_cricinfo) -> Wikidata property
P2697 (ESPNcricinfo player ID) -> Wikidata item -> P569 DOB, P19 birthplace, P1532 country for sport.
- Batch SPARQL queries (few hundred IDs), descriptive User-Agent, cache results locally.
- Wikidata coverage weaker for women's/associate/domestic players; batting/bowling style patchy.
- Keep Cricsheet ID as primary key; metadata columns nullable.

## Refresh strategy (decided)
- Initial: full load `all_json.zip`.
- Daily: `recently_added_7_json.zip` -> upsert by match_id (idempotent).
- Weekly: full replace `people.csv`; query Wikidata only for new Cricinfo IDs.
- Monthly: re-download `all_json.zip`, hash-diff vs stored, upsert diffs, report IDs no longer present.
- Schedule via Synology Task Scheduler (Python). Log added/updated/unchanged counts.
- Future: map to AWS (S3 raw zips, Lambda/Glue on EventBridge) + CI/CD.

## Attribution (required on site + README)
"Match data from Cricsheet (cricsheet.org), used under the Open Data Commons Attribution License 1.0."
Do not imply Cricsheet endorsement. TODO (user): email Cricsheet to confirm match-file license; keep reply in docs/.

## Location and hosting (decided 2026-10-05)
- Code lives **inside the pandya-homelab monorepo** at `/volume1/pandya-homelab/cricstat/` (ADR-008: one repo).
  It is not a separate `/volume1/cricstat` share or repo. Deployment config will go in `deployment/cricstat/`.
- Hosted as a **cross-domain flagship project** on the main site (needs a new ADR-022 to define this category):
  - Homepage stays one scrolling page. Add a "Cricket" nav link, a hero button, a "Flagship project" banner,
    and a small cross-link card in each domain section (ML → predictor, Agentic → analyst agent, etc.).
  - Hub at `pandyahomelab.com/cricket/` with its own menu: Countries · Players · WC 2027 Predictor ·
    Ask the Analyst · Methodology & Evals · Data & Licences. API under `/cricket/api/`.
  - No literal two-tab homepage (it would hide content from visitors and search engines).
- Keep the site's privacy promise ("no cookies, nothing loaded from third parties"). Rate-limit on the server side
  (Nginx + Cloudflare rules) rather than with Turnstile. Disclose Anthropic as a server-side processor.

## Environment notes
- NAS: Celeron J3455 (4 cores, **no AVX**), 16 GB RAM (~7 GB free), no GPU. Host Python 3.8.15 (EOL),
  SQLite 3.40, pandas 2.0.3, requests 2.28.1. Apps that need Python >= 3.10 (LangGraph etc.) run in Docker.
- The folder initially had no Synology ACL. It was fixed 2026-10-05 with `synoacltool -enforce-inherit` and now inherits the share ACL.
- User's laptop (benchmarks only): i7-12700H, 32 GB RAM, Intel Arc A370M (4 GB, no CUDA).
- Earlier Claude Code launch error ("native binary failed to launch / libc") was caused by folder permissions,
  NOT a binary/libc problem.

## Plan (approved 2026-10-05)
Background: `docs/llm-strategy-research-2026-10-05.md`.
- Database: **SQLite** (stdlib, single file; DuckDB can read it later for analytics).
- Wireframes: a clickable, shareable web page (Artifact).
- India theme (2026-10-05): India-blue (#1347A3) + saffron (#FF9933) palette; "Follow a team" defaults to India
  (stored in the browser only, no cookies); "Why I built this" note on the hub; IPL + "India at World Cups (2003–2023)"
  features. Guardrails: the model is identical for every team (fandom changes the view, never the forecast);
  no national flag (Flag Code) or BCCI/team logos (trademarks); disclose that pre-2001 history (e.g. 1983) is not in the data.
- v1 scope: men's **and women's** cricket; all formats (Tests, ODIs, T20Is + major leagues). WC 2027 predictor is men's only.
- foundation sprint F1–F9 (brief, wireframes, data model, metric dictionary, API contract, engineering setup,
  roadmap, compliance & trust, CI/CD & automation), with ingestion running in parallel
- F9 CI/CD & automation (added 2026-10-05; pilots platform Stage 3, needs its own ADR). The repo
  `avpgithub-code/pandyahomelab` has no `.github/workflows` yet.
  - CI on every push or PR: lint, unit tests, metric-formula tests, schema tests, Docker image build.
  - CD is **pull-based**: GitHub Actions builds images and pushes them to GHCR; a NAS scheduled job pulls tagged
    images, restarts, smoke-tests **on the NAS** (no-AVX trap) and rolls back on failure. No inbound ports.
    No self-hosted runner, because of the risk from public-repo PRs. A manual approval gate comes first,
    and becomes automatic once proven.
  - Data pipeline: data-quality checks before the atomic DB swap; on failure keep the old DB and send an email alert.
  - Model retraining: backtest, then promote in MLflow only if metrics don't regress.
  - LLM evals: a small subset on PRs, the full set nightly. The API key lives in GitHub Secrets under the same budget cap.
  - Timing: CI and data checks in F6/P0, model gates in P1, eval gate in P3/P4, CD before going public (P5).
- cricstat containers: Nginx serves static pages; always-on `cricstat-api` and `cricstat-agent`; scheduled jobs
  `cricstat-pipeline` and `cricstat-models` (container names follow the folder, like `ml-iris-knn`); reuse the existing MLflow with `cricstat-*` experiment names;
  Phoenix tracing from P4.
- phases P0–P6
- LangGraph agent with typed tools first
- local and Hugging Face model comparison
- WC 2027 predictor as the P1 headline, built as a **measured three-model comparison** (decided 2026-10-05):
  (1) Elo + Monte Carlo baseline (statistics/ML, ships first); (2) gradient-boosting challenger with squad features (ML);
  (3) squad strength from **DL player embeddings** learned by the ball-by-ball sequence model, plus Monte Carlo (DL).
  All three are backtested on WC 2019/2023; the best-calibrated one powers the live forecast, and the comparison is published.
  Why: about 2,600 men's ODIs is too little for DL at match level, but 11.6M deliveries suit DL. The same sequence model
  also gives live in-match win probability. Homepage cards: ML "Elo baseline vs ML and DL challengers";
  DL "Live win probability and player-strength ratings for the predictor".
- API budget (separate Console workspace, prepaid credits with no auto-reload, $1–2/day cap in the app)

## Roadmap
| Step | Deliverable | Status |
|---|---|---|
| F1 | Product brief (`docs/F1-product-brief.md`) | Done 2026-10-05 |
| F2 | Site map + wireframes (https://claude.ai/artifact/B9ge1q8GuwaoyxkL8hhbKz) | Done 2026-10-05 |
| F3 | Data model (`docs/F3-data-model.md`, `sql/serving_schema.sql`) | Done 2026-10-05 |
| F4 | Metric dictionary + formula tests (`docs/F4-metric-dictionary.md`) | Done 2026-10-05 |
| F5 | API contract (`docs/F5-api-contract.md`) | Done 2026-10-05 |
| F6 | Engineering setup (`docs/F6-engineering-setup.md`) + ADR-022 (Accepted) + CI skeleton | Done 2026-10-05; pipeline deployed, DSM tasks live (daily 05:30, monthly day 1 04:00; verified) |
| F7 | Roadmap + decision log | Ongoing in this file (current to 2026-10-09) |
| F8 | Compliance & trust (licences page, privacy update, disclaimers) | Folded into P0 (decided 2026-10-05) |
| F9 | CI/CD & automation (`docs/F9-cicd-automation.md`) | Done 2026-10-05: CI + approval gate + GHCR + NAS cd-pull.sh (DSM daily 05:15); merged to main |
| P0 | Ingestion → serving-DB build → cricstat-api → first live pages (+F8) | **Done; public 2026-10-07.** P0.1 build + register, P0.2 golden figures, P0.3 cricstat-api, P0.3b `/admin/cricket` (2026-10-06); P0.4 pages + F8 texts live and linked from the homepage 2026-10-07 (+ `/cricket/about/` page) |
| P0.6 | Search-engine pages: server-rendered player/team heads, real 404/301, `/cricket/sitemap.xml` | **Done 2026-10-07** (4,840 players + 176 teams indexable; submitted in Search Console) |
| P0.5 | Wikidata enrichment: full names, birth details, Commons photos | **Done 2026-10-08** (7,192 on Wikidata; 1,364 credited photos incl. GODL-India/PDM-owner; weekly `enrich`; search + cards use names/photos) |
| P1 | ODI World Cup 2027 predictor: Elo + Monte Carlo baseline first, then ML and DL challengers, backtests on WC 2019/2023, live win probability | **In progress:** P1.1–P1.5 live (2026-10-08: models + API deployed, champion elo-v2, daily forecast in DSM); **P1.6 partly live 2026-10-09** (world map Countries landing, records API, review tweaks; owner checked the live site); predictor page, methodology page, team-page ratings card, hub teaser and `PREDICTOR_LIVE` **on hold by the owner** on `feat/cricstat-p16-pages` |
| P2–P6 | Tools → test set → agent → public demo → extras | Later |
| Later | Men's T20 World Cup 2028 forecast + T20I team ratings (decided 2026-10-06; shown as "Later" on team pages) | **Not started until the ODI World Cup 2027 is finished** |

Git: one feature branch per sub-phase (e.g. `feat/cricstat-p05-wikidata`), merge to `main` with `--no-ff`, push (ADR-018).

## DSM scheduled tasks (operator creates them in DSM → Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script)
Both run as user **root**. Task Settings → Notification: tick "Send run details by email" and
"Send run details only when the script terminates abnormally". Pipeline exit codes: 0 = ok, 1 = error, 2 = data-quality gate.
| Task name | Schedule | Run command |
|---|---|---|
| cricstat CD pull | Daily, 05:15 | `sh /volume1/pandya-homelab/deployment/cricstat/cd-pull.sh` |
| cricstat daily refresh | Daily, 05:30 | `cd /volume1/pandya-homelab/deployment/cricstat && /usr/local/bin/docker compose run --rm cricstat-pipeline recent && /usr/local/bin/docker compose run --rm cricstat-pipeline build && /usr/local/bin/docker compose run --rm cricstat-models forecast` (forecast added 2026-10-08, verified) |
| cricstat weekly register | Weekly, Sunday 06:00 | `cd /volume1/pandya-homelab/deployment/cricstat && /usr/local/bin/docker compose run --rm cricstat-pipeline register && /usr/local/bin/docker compose run --rm cricstat-pipeline enrich && /usr/local/bin/docker compose run --rm cricstat-pipeline build && /usr/local/bin/docker compose run --rm cricstat-models supplement-check` (enrich + supplement-check added 2026-10-08, verified; exit 3 = Afghanistan rows to review → DSM email) |
| cricstat monthly full | Monthly, day 1, 04:00 | `cd /volume1/pandya-homelab/deployment/cricstat && /usr/local/bin/docker compose run --rm cricstat-pipeline full && /usr/local/bin/docker compose run --rm cricstat-pipeline build --full && /usr/local/bin/docker compose run --rm cricstat-models forecast --force` (forecast added 2026-10-08, verified) |
Build steps added 2026-10-06 (verified with synoschedtask; image 52d427de deployed by cd-pull; a by-hand containerised
`build` returned `unchanged` in 4s, same rules_sha as the host). Model jobs (P1) get appended later (F6 §4).

## P4/P5 security checklist (before the agent goes public)
- [ ] **DSM firewall:** add a deny rule for `172.25.0.0/24` placed **above** the existing `172.16.0.0/12` allow, so
      cricstat containers (which handle visitor input) cannot open connections to DSM/host services. They only need
      each other, Nginx and the internet. Test with the stack running (rule order matters), and record it in F6 §2.
- [ ] Agent safeguards from F5 §5.2: per-IP limits (5/min, 20/day), global daily budget cap, kill switch,
      30-day retention, tool output treated as data.
- [ ] The `run_sql` fallback is read-only, SELECT-only (parsed), LIMIT-wrapped and time-limited, against views only.
- [ ] `deployment/cricstat/.env` is mode 600, and the API key is in a dedicated Console workspace with prepaid credits and no auto-reload.
- [ ] Privacy page updated (Anthropic as a processor, retention, no cookies) before launch (F8).

## P0.1 serving-DB build (done 2026-10-06, branch `feat/cricstat-p0-build`, merged)
- `cricstat-pipeline build [--full|--incremental]` and `register [--people-csv --names-csv]`. Same image, same exit codes.
- **Measured on the NAS (host Python 3.8):** full build 11m50s (load 10m, indexes+marts 80s, checks 30s), peak RSS
  0.87 GB; `cricstat.sqlite` = **1.13 GB** (F3 estimated 1.5–2.5 GB). Incremental 67s (6s file copy); a no-op exits in <1s
  without touching the live file. Rows: 22,983 matches, 11,615,100 deliveries, 436k batting / 301k bowling atoms,
  903k phase rows, 42k player_career rows, 13,705 players, 970 venues (679 canonical).
- Decisions (approved by the user 2026-10-06): register CSVs land in raw.sqlite (migration 0002, `register_people/_names`;
  ingest_runs mode `register`) and every build applies them; `players` = people named in match registries (umpires and
  never-played Register entries are left out); featured leagues are seeded in `reference_data.sql` (event-name variants
  share a slug: t20-blast, the-hundred-men/-women…); scopes = every format key + featured slugs + LEAGUES + ALL;
  `rules_sha` (schema, reference data, transform code) changes force a full build; a failed check keeps the live DB and
  saves `cricstat.sqlite.failed`; `bowling_innings.wides/noballs` count balls, and their runs are extras in the team
  total and also charged to the bowler's runs_conceded (F4 R4); the venue map draft is accepted (France for New Caledonia,
  Colombia for Bogotá).
- **Source issue found:** 10 Cricsheet ids are shared by a man and a woman (Register merges, e.g. 764f35d8 "N Sharma":
  UAE women + Middlesex men). The build gives each id its majority gender and warns. Add these to the Cricsheet email.
- Gotchas: pytest and ruff silently skip any folder named `build/` (tests live in `tests/serving/`); a long reader of
  raw.sqlite blocks the ingest writer in DELETE mode, so build always runs after ingest, never alongside;
  `/var/tmp` is on DSM's 2.3 GB root fs, so the build uses `temp_store=MEMORY`.
- Venue map: `sql/venue_map.csv` (draft, 970 rows, `checked` column for the user). Country = Cricsheet team name of the
  cricket nation (Wales → England, NI → Ireland, Caribbean → West Indies).
- **Image context moved to `cricstat/`** (needs `sql/`); CI/publish/compose updated; publish also triggers on `cricstat/sql/**`.
- DSM commands once the image is published (operator edits the tasks): daily `… run --rm cricstat-pipeline recent && …
  run --rm cricstat-pipeline build`; monthly `… full && … build --full`; new weekly Sunday 06:00 `… register && … build`.

## P0.2 golden-figure set (done 2026-10-06, branch `feat/cricstat-p0-golden`, merged)
- `docs/validation/golden-selection.csv`: 53 players (31 men, 22 women; 13 India men, 9 India women) and 10 teams
  (India men + women, Australia, England men + women, Pakistan, South Africa, New Zealand women, Mumbai Indians).
- `docs/validation/golden-figures.csv`: 1,012 rows (trimmed 2026-10-06: each player's 2 main scopes; batting Mat, Inn,
  NO, Runs, HS, Ave, 100; bowling Mat, Inn, Wkts, BBI, Ave, Econ, 5w; keepers + Ct, St; teams Mat, W, L, T, D, NR, Win %).
  The user fills `reference`, `source`, `checked_on` and, for any difference, `explanation`.
  `cricstat-pipeline golden` (host only; docs/ is not in the image) regenerates `ours` and keeps those columns; an
  unexplained difference exits 2.
- Window rolls forward: teams 2016-01-01..data_as_of; players whole careers. The first run after a reference is entered
  snapshots `ours_at_check` + `mat_at_check`; if that player/team's Mat later changes the row turns `stale` (re-check: type
  the new reference and blank `mat_at_check`), not a failure. A figure that moves while Mat is unchanged = regression → DIFF.
- `coverage_note` hints where a career starts before the data is dense (men's Tests ~2005, ODIs 2003, T20Is 2012;
  women's ODIs 2016, T20Is 2018 — partly real gaps, partly the 2018 T20I-status expansion). Known differences to expect:
  Afghanistan men's matches are withheld (e.g. Kohli's T20I 122* is missing), pre-coverage careers (Tendulkar, Mithali).

## P0.3 cricstat-api (done 2026-10-06, branch `feat/cricstat-p0-api`, merged)
- `cricstat/cricstat-api/`: FastAPI, GET-only, 4 layers, stdlib sqlite3. Endpoints: health, status, meta (scopes,
  competitions, metrics), search, players (profile, career, years, phases, splits, innings), teams (list, identity,
  record, results, head-to-head, home-away, years, top-players). F5 additions: `GET /v1/teams`, `/teams/{slug}/years`.
- Envelope with provenance; problem+json; ETag = build id (304); Cache-Control public 300 s / swr 3600 s.
- DB: `mode=ro&immutable=1` (the pipeline only ever replaces the file), reopen when the inode changes, process-wide
  per-build caches, startup warm-up, background read-through of each new file into the page cache (5 s for 1.13 GB;
  cold random reads on the NAS disks had taken 1–10 s). Query time limit 10 s → 503.
- Measured on the live DB (host, warm): 82 requests p50 12 ms, p95 39 ms, max 131 ms (F5 target p95 < 300 ms).
- Ratios: views where they apply; `metrics.py` mirrors them for years/phases/splits/windows (tests compare).
  `Scopes.clause()` mirrors marts.sql (tests compare every scope).
- Swagger/ReDoc are off (they load scripts from a CDN, against the privacy promise); `/openapi.json` is served.
  A self-hosted docs page belongs to P0.4. Team slug = name + men/women (+ `-club` on a clash).
- Container: 172.25.0.10 → 127.0.0.1:8040, read-only rootfs, cap_drop ALL, no-new-privileges, 512 MB, data/db mounted
  read-only as a directory, one uvicorn worker. `cd-pull.sh` now smoke-tests the API on the NAS against the real DB
  (port 8049), restarts it via compose, health-checks it and rolls back on failure; a service never published yet is
  skipped, not a failure. CI: api-tests (py3.8/3.12) + api-image (non-root, read-only, expects 503 no_db).
  Publish: `cricstat-api-publish.yml` (only `cricstat/cricstat-api/**`, approval gate).
- Decisions (user, 2026-10-06): docs page self-hosted in P0.4 (no CDN); team slug `-club` suffix OK (only Barbados
  women clashes today; slugs are URL labels only, the predictor uses team identity name+gender+type); derived role OK
  to start. Wikidata enrichment (DOB, birthplace, country, and "position played" where present) is an automatic step
  on the weekly register task, not the Verify References button; role = Wikidata when present, else derived, with
  the source stated in the API.

## P0.3b `/admin/cricket` (done 2026-10-06, branch `feat/cricstat-p0-admin`, merged)
- A Cricket section in the existing admin portal (`ml/admin-portal`, Basic Auth): (1) scheduled-job status (CD pull,
  daily, weekly register, monthly full; last run, status, duration, counts, build checks/warnings), (2) data at a glance
  (matches, deliveries, players, data_as_of, size, matches per year by format/gender), (3) golden figures with a manual
  **Verify References** button.
- Data comes through cricstat-api (internal-only admin endpoints, blocked from public `/cricket/api/` by Nginx); the
  admin portal joins cricstat-network. No cricstat file mounts into the admin container, no Docker socket.
- Verify References: manual only; runs inside the admin portal; fetches Wikipedia infoboxes (MediaWiki API, CC BY-SA,
  descriptive User-Agent) for the fixed selection only (no user-supplied URLs); one run at a time (button disabled while
  running, no timer). Wikipedia figures are suggestions; the user accepts or explains each; decisions live in the
  portal's Postgres and `golden` exports them to docs/validation. ESPNcricinfo is never scraped (terms; sources policy).
- Wikipedia covers players' Test/ODI/T20I Mat, Runs, Ave, 100s, HS, Wkts, BBI, Bowl Ave, 5w, Ct/St; IPL/WPL, team
  records, Inn, NO and Econ stay manual. A weekly scheduled golden check moves here too (not a host script).
- Built: cricstat-api `/v1/admin/{jobs,overview,golden}` (no-store; golden selection baked into the API image, so the
  API image builds from `cricstat/`; logs mounted read-only for the CD-pull log); admin portal `app/cricstat/`
  (wiki, golden, store, runner, api_client), `app/cricstat_routes.py`, templates `cricket.html`, `cricket_golden.html`;
  Postgres schema `cricstat`; weekly check loop; cricstat section in the weekly report email; "🏏 Cricket" link on
  `/admin/`. POSTs are same-origin checked (Basic Auth is sent automatically, so CSRF matters).
- Wikipedia pages found via Wikidata P2697 (Cricinfo id): 3/3 on a live test. Infobox quirks handled: women's
  WTest/WODI/WT20I columns, a date without a year.
- **Step 4 must:** block `/cricket/api/v1/admin/` in Nginx (internal only).
- The host `cricstat-pipeline golden` command stays for offline use; the admin page is the main workflow now.

## Golden follow-up (done 2026-10-06, branch `feat/cricstat-golden-followup`, merged)
- First Verify References run: 53/53 Wikipedia articles found, 539 suggestions, 188 equal ours (accepted).
- **F4 R23 (decided):** displayed ratios are cut to 2 decimals, not rounded (published records do this; Warner 44.5989 is
  44.59). API/views stay unrounded; golden formatting (API + pipeline) and the pages apply R23. With R23: 193 agree.
- Admin labels each differing block from the match counts (coverage gap · Wikipedia newer · Wikipedia older/fewer ·
  missing = withheld Afghanistan matches or a Cricsheet gap · same matches, a figure differs). New bulk action
  "Explain coverage gaps" (≈193 rows in 40 blocks): reference = Wikipedia's figure, explanation "career predates dense
  Cricsheet coverage; our data has M of N matches". Coverage hint now also flags careers that start within a year of
  where our data for that format begins (Ponting/Kallis/Muralitharan ODIs).
- Open item: **Ecclestone T20I bowling** — same matches (113), wickets (154) and best (4/18) as Wikipedia, but ~5 more
  runs conceded (2535 vs ~2530 → 16.46 vs 16.43). Candidates: her 5-run wides (e.g. matches 1230855, 1260101, 1289273,
  1343936). Check those scorecards by hand; no rule change on a guess.
- 19 blocks with a few missing matches remain for review (many are India v Afghanistan; e.g. de Villiers Tests 106 v 114,
  Shakib ODIs 211 v 247 look like Cricsheet gaps).

## P0.4 public pages (built 2026-10-06 on `feat/cricstat-p0-web`; public 2026-10-07)
- `cricstat/web/`: hub, players (search + profile), countries, licences (F8 texts). Plain HTML/CSS/JS, no inline scripts,
  system fonts, self-hosted Chart.js, DOM via textContent only, R23 cut-off ratios, `cricstat:follow` in localStorage.
- Predictor, Ask and Methodology appear as "soon" (nav and tiles), not as empty boxes. Hub cards show win % and last 5
  per format for the followed team plus "in form" (top run-scorer/wicket-taker, 12 months to data date).
- Homepage, privacy page and sitemap changes are STAGED in `cricstat/tools/staging/` because `website/` is live
  (bind-mounted): copy them over only after approval. Privacy additions: cricstat mention, search words appear in the
  server log/visit statistics (they are in the URL), `cricstat:follow`. The Anthropic/analyst text waits for P4.
- Preview: `python3 cricstat/tools/web_preview.py` (127.0.0.1:8090, via VS Code port forwarding). Pages were also run
  in jsdom against the live API: no script errors.
- Nginx (repo only until deployed): `cricstat_api` upstream (container name), `cricstat_api` limit zone 10 r/s burst 20,
  `/cricket` → `/cricket/`, `/cricket/api/v1/admin/` → 404, `/cricket/api/` GET/HEAD only + proxy (plain access log only,
  so API calls stay out of visitor analytics), regex routes for player/team pages, static `/cricket/` with `=404`.
  Compose: nginx joins cricstat-network at .20; mount `cricstat/web → /var/www/cricket:ro`.
- Safe deploy order: `docker network connect` the live nginx to cricstat-network → `docker cp` new nginx.conf and
  `nginx -t -c` inside the live container → only then rebuild `--no-cache` and recreate.

### P0.4 redesign (user request 2026-10-06)
- **Theme:** cricstat pages now use the homepage's dark theme (same tokens, nav, hero glow, cards, pills, fade-up),
  with saffron + India blue accents. Hub: count-up counters, "Latest results" score-card strip (default = ICC full
  members + featured leagues; tabs Women / All), followed-team cards with form dots, "<year> leaders" with format tabs
  (ODI/T20I/Test/Leagues; men's + women's runs and wickets), featured-league cards. Players: hero card with avatar and
  headline KPIs. Countries: flag header, format KPI cards, recent results strip. Page shells generated by
  `cricstat/tools/gen_pages.py`.
- **API additions (F5-planned, non-breaking):** `GET /v1/matches` (newest first, both teams' innings scores, filters
  scope/gender/team/from/to) and `GET /v1/leaderboards/{batting|bowling}` (runs / wickets for now); team results carry
  `scores`. Hub leaders use per-format scopes (ALL would mix county and league cricket).
- **Flags — decision changed by the user (2026-10-06):** national flags ARE used, from Wikimedia Commons, only when
  Commons lists them as public domain or CC0 (89 of 90; Oman's OGL-om flag is not used), self-hosted in
  `cricstat/web/flags/`, shown at their true proportions (India 3:2 per its Flag Code), never cropped or stretched.
  Not flagged: West Indies, Ireland (all-island team), composite XIs, club sides (colour badges instead). SVGs are
  checked for active content by `cricstat/tools/fetch_flags.py`; Nginx serves `/cricket/flags/` with a no-script CSP.
  Still no board or franchise logos.
- **Player photos (agreed, next):** Wikidata P18 → Wikimedia Commons, each image with its own licence and credit,
  thumbnails downloaded by the pipeline and self-hosted; initials avatars until then.

### P0.4 review round (user, 2026-10-06) — state at the end of the day
- **Review status:** hub (`/cricket/`), players search, countries list and team pages: approved. Still to review:
  licences page, staged homepage, staged privacy page, admin snapshot (`/admin-preview/cricket/`).
- **Uncommitted** on `feat/cricstat-p0-web`: cricstat/web/, cricstat/tools/ (gen_pages, fetch_flags, web_preview,
  staging/), API (`/v1/matches`, leaderboards, record from/to, source freshness), pipeline (Cricsheet Last-Modified),
  admin portal (source banner, wordmark), nginx (repo only). Tests: API 57, pipeline 81, admin 7 pass; service
  folders lint-clean (CI lints only the service folders; `tools/` has style-only ruff findings).
- **Defaults everywhere:** period **YTD**, format **ODI**; format order ODI, T20I, Test; Latest results = ODI + Men.
  Periods: last 10 / YTD / 1 year / 5 years / all. "In form" follows the period ("Top performers" for 5 years / all).
- **Naming:** always "ODI World Cup 2027" / "ODI WC 2027" (nav "ODI WC 2027 soon"); wordmark cric (white) + **stat**
  (saffron) on every page incl. admin; the homepage hero button was removed.
- **Hub:** "The data behind cricstat" panel (counters with icons + captions, why-volume paragraph, WC teaser "What are
  the chances of India lifting the 2027 ODI World Cup?" with a gold trophy + tricolour ribbon — not the flag merged
  into the trophy, per the Flag Code); each section is a bordered `.section.panel`.
- **Flags & badges:** West Indies keeps the colour badge (its "flag" is a board emblem) — user agreed. Small flags
  (12 px tall, true proportions) before a player's team line, only for teams with a PD/CC0 flag.
- **Players:** "Popular players" is hand-picked (8: four India, four others, men + women) and the caption says it is
  not a ranking; 4-column grid; role icons (bat / ball / bat+ball / glove) from the API's derived role. Known quirk:
  JE Root derives as all-rounder — leave the rule; Wikidata "position played" will take precedence (P0.5/enrichment).
- **Countries:** Recent results has ‹ › arrows (shared `cricstat.carousel()`), format capsules (ODI default; a team
  without ODIs starts on its most-played format), a count/date-span note and the freshness notice
  (`cricstat.freshness()`, shared with the hub). Ratings card depends on format and gender: men ODI = "Ratings & ODI
  World Cup 2027" (Next); men T20I = "T20I ratings & T20 World Cup 2028" (Later, only after the ODI WC 2027 is over —
  see roadmap); everything else "<format> ratings" (Later). Women's pages never mention the men-only 2027 predictor.
- **Source freshness:** the daily check records Cricsheet's Last-Modified (`ingest_runs.notes.source_last_modified`);
  `/v1/status` + `/v1/admin/jobs` carry a `source` block (stale after 14 days); pages show "⏱ Cricsheet's last update
  was …" when it is over 7 days old. Cricsheet's own last update was 2026-09-17 (the pipeline is not stuck).
- **Asset versions:** `V` in `cricstat/tools/gen_pages.py` (now "64") is the `?v=` on every asset; bump it and rerun
  `python3 cricstat/tools/gen_pages.py` after any CSS/JS change. Never edit `web/**/index.html` by hand.
- **Review round 2 (2026-10-06, approved):** licences page adds a Chart.js (MIT) row, "used unaltered … only to
  identify national teams", and a generated per-flag Commons source list (`gen_pages.py` reads flags.js). Admin
  snapshot, privacy and staged homepage approved. Player profile: team chip has the small flag; Leagues tab puts a
  **League** first column in Batting/Bowling/Fielding (one row per league + "All leagues" total); Phase splits on
  Leagues = the main league; renamed franchises merged for display only (`RENAMED` in players.js: RCB, Punjab Kings,
  Delhi Capitals, RPS, St Lucia Kings, TKR, 2026 Hundred renames; Barbados left out) in "Played for" and in opponent
  splits (averages recomputed from summed runs/outs). **venue_map.csv:** 3 punctuation duplicates mapped (M.Chinnaswamy,
  ACA VDCA, Gahanga ". Rwanda"). venue_map.csv is applied on EVERY build (incremental too) and is not part of
  rules_sha, so no full rebuild is needed — verified on deploy 2026-10-07 (build 4, incremental 76 s).
- **Decisions (user, 2026-10-06):** keep the "soon" nav items; corrections contact = privacy@pandyahomelab.com; API
  calls stay out of visitor analytics (nginx plain access log); "Popular players" → "Players to start with";
  "Why I built this" drafted by Claude, user to verify (hub, `gen_pages.py`).
- **About drawer (approved 2026-10-06):** "ⓘ About cricstat" in the nav on every page opens a drawer like the
  homepage's (content `web/about.json`, script `assets/about.js`, Mermaid loaded on first open). Sections: the story
  (2011 Wankhede + Sachin carried — Kohli's words as reported speech; 2023 Ahmedabad final; 2027 hope: Gill's team
  lifting Kohli — a hope, not a claim), the ODI WC 2027 predictor (Elo / ML / DL with transfer learning, backtests,
  calibration), the AI analyst (explains, doesn't predict), how it's built (diagram), honest by design, roadmap, built
  with Claude Code. The hub's bottom "Why I built this"/"How it's built" cards were removed; the hero has a saffron
  capsule "2011 gave us the six. 2023 gave us the heartbreak. 2027 is the question. Read the story →". Teaser line 2:
  "Three models — Elo ratings (statistics), machine learning and deep learning — are about to compete to answer that →".
  "Popular players" → "Players to start with".
- **Review round 3 (2026-10-06, approved):** cricket look = scoreboard digit tiles on the hub counters, a red ball as
  the dot of the "i" in the hub wordmark (dotless ı + SVG; screen readers get "cricstat"), and "The data behind
  cricstat" styled as a stadium board (green-black, metal frame, amber bulb header). Tried and dropped: a top-down
  ground drawing behind the hero (distracting) and a scorebook/bat/ball emblem. Less scrolling: the separate WC 2027
  card and the Explore panel were removed (their content moved into the About drawer: predictor section + roadmap);
  spacing tightened ~25%; hub = hero + 2 boards. **Match centre** board: tabs Latest results (default) · Following ·
  Leaders · Leagues (WAI-ARIA tabs, `cricstat.sectionTabs()`; no remembered tab, to avoid new browser storage).
  One date everywhere = Cricsheet's own last update ("Live data · checked daily · Cricsheet 17 Sept 2026", header
  "Match centre · Cricsheet …"), fallback = newest match. About drawer always opens at the top; the WC teaser and
  highlight open it. **Team pages:** "Form guide · <team>" board with tabs Record by format · Recent results ·
  Results by year (chart re-sizes when its tab opens); "Head to head & top performers" stays a normal panel below.
  Team dropdown lists India first; the plain Countries page always starts on India men (a team's own URL keeps that
  team); selects have autocomplete="off" so browsers don't restore a stale choice. Restore point for the look:
  git tag `cricstat-p04-approved-look`.
- **Open decisions before going public (superseded by the line above):** the "soon" nav items; the "Why I built this" text (placeholder); corrections
  contact (proposed: the existing privacy@ address); API calls kept out of visitor analytics (done in nginx.conf,
  needs OK); optional: "Popular players" → "Players to start with".
- **Deploy order once approved:** commit + `--no-ff` merge + push → user approves the API, pipeline and admin-portal
  publishes → cd-pull → safe nginx deploy (network connect → docker cp + `nginx -t` → rebuild `--no-cache` + recreate)
  → copy staged homepage/privacy/sitemap into `website/` (this is what makes it public).
- **Deploy 2026-10-07 (done):** publishes approved (api 8d1fade0ffba, pipeline c24d9519b6d4,
  via cd-pull by hand); build 4; nginx joined cricstat-network at .20, config tested in place, rebuilt + recreated —
  /cricket/, players, countries, licences, flags, /cricket/api/ live; /cricket/api/v1/admin/ → 404; admin portal
  rebuilt (`-f docker-compose.yml -f docker-compose.dev.yml` in deployment/ml — the dev file alone is invalid).
  Publish workflows used to let an unapproved old run block newer ones; fixed 2026-10-08 (`cancel-in-progress: true`:
  the newest run replaces any older waiting one, so only the newest needs approval).
- **P0.4 public 2026-10-07** (merge 1898a69): staged homepage/privacy/sitemap copied into `website/`.
- **SEO round (2026-10-07, approved, branch `feat/cricstat-seo-about`):** `/cricket/about/` = the About drawer's story as
  a static page, rendered by gen_pages.py from the same about.json (Article JSON-LD, author = homepage Person
  `#archit`; section ids are anchors #story #predictor #analyst #architecture …); hub title "cricstat — cricket stats,
  ODI World Cup 2027 predictor & AI analyst" + WebApplication JSON-LD; nav "About cricstat" and "Read the story" are
  now `<a href="/cricket/about/" data-about>` (JS opens the drawer, crawlers follow the link; on the about page
  itself no drawer); footer links "How cricstat was built" + Archit → /. Homepage: descriptive banner button, "How I
  built it" link, domain cross-link cards → /cricket/about/#predictor|#analyst; knowsAbout + LLMs, Cricket analytics.
  Sitemap + /cricket/about/. Owner: request indexing for /cricket/about/ in Search Console.
  Known SEO gap (next, P0.6): player/team pages share one title and a canonical pointing to the list page → not
  indexable; fix = per-page static shells with own title/canonical/summary/JSON-LD, sitemap for meaningful players.
- **P0.6 SEO pages (2026-10-07, approved, branch `feat/cricstat-p06-seo-pages`):** nginx sends
  /cricket/players|countries/<slug>/ to cricstat-api `/pages/...`, which returns the static shell (cricstat/web
  mounted read-only at /cricstat/web) with the page's own title/description/canonical/robots/JSON-LD and a summary
  table inside #p-profile / #c-body (JS replaces it); 301 to the canonical player slug, real 404s; nginx falls back
  to the plain shell on 502/503/504. Index bar: 10 official internationals or 20 featured-league matches
  (`CRICSTAT_INDEX_MIN_INTL/_LEAGUE`) → 4,840 players + 176 international teams in `/cricket/sitemap.xml`
  (API `/pages/sitemap.xml`, listed in robots.txt); clubs noindex for now. Profile API gains `full_name`
  (Register variant). Scripts keep the server's title (`cricstat.serverHead`). **Gap:** 2,643 of 4,840 indexed
  players (55%; ~72% of women, e.g. "S Mandhana") have no full-name variant → fix with Wikidata labels in P0.5.
  Dev: run the branch API on 8048 with CRICSTAT_WEB_DIR=cricstat/tools/staging/web and the preview with
  CRICSTAT_API=http://127.0.0.1:8048.
- **P0.5 Wikidata enrichment (2026-10-07, approved, branch `feat/cricstat-p05-wikidata`):** pipeline `enrich`
  (weekly after register: `register && enrich && build`) looks up every player's ESPNcricinfo id on Wikidata (P2697;
  never by name; 200 ids/query, 1 req/s, UA with privacy@ contact) → raw `wikidata_people` (label, birth date by
  precision, birthplace, country for sport, P18 file); Commons API → `commons_images` (licence, author, file page) +
  one ~330 px thumbnail in data/photos/<sha1[:16]>.<ext>. Licences: PD, CC0, CC BY, CC BY-SA only (NC/ND/GFDL-only
  rejected). Under-18 (year-only → latest birthday): no photo download; build drops birth details + photo.
  Failed photos retry next run; others refresh after 28 days; ≤1,500 photos per run. Build: `bio_store.py` (NOT in
  rules_sha) refills player_bio every build; enrich run id + blocklist are in inputs_sha. `sql/photo_blocklist.csv`
  (qid or image_file) for removal requests (needs a pipeline publish). API: full_name = Wikidata label (same surname)
  → Register variant → scorecard; profile `bio` + `photo`; pages: Born line, photo + credit, og:image, JSON-LD.
  Web: photo replaces the initials avatar, credit line, licences rows. nginx `/cricket/photos/` (hash names only,
  no-script CSP) from data/photos mounted ro. Trial: 7,192/13,754 on Wikidata; indexed full names 45% → 74%.
- **P0.5 deployed 2026-10-08 (UTC):** pipeline 1a0aaf5848ce first (cd-pull `CRICSTAT_SERVICES=cricstat-pipeline`),
  enrich 36 min (7,192 on Wikidata; 1,315 photos ok, 47 rejected, 2 minors; 56 MB), full build 5 (10m42s; 7,186 bios,
  1,319 with photo, 7 minors), then API 59cd5470fea0, then nginx with the photos mount. Rejected licences: GODL-India
  35 (most Indian stars' PIB photos: Kohli, Mandhana, Bumrah), PDM-owner 10, GFDL 1.2 2. Decided 2026-10-08: allow
  GODL-India (credit adds "No endorsement by the Government of India is implied." + licence link) and PDM-owner; GFDL
  stays out. enrich re-fetches previously rejected photos once their licence is allowed.
  DSM weekly register task now runs `register && enrich && build` (edited + verified 2026-10-08). After the licence
  change: 45 more photos (Kohli, Mandhana, Bumrah…), build 6 → 1,364 players with a photo.
- **Hub wordmark on a pitch (2026-10-08, approved):** option C (dusty strip, mowing stripes, creases + stumps, green
  square; inline SVG in gen_pages HUB). The "i" ball arrives on each load from a random end (hub.js sets
  `data-ball` rb|rt|lb|lt; CSS §7 keyframes with custom props), bails + splinters burst on landing (CSS §8).
  Sound only on click (browsers block autoplay): synthesised Web Audio "tock" + bail clicks; hover hint on the ball.
  Reduced motion → static ball, no burst.
- **`cricstat/web/` is LIVE** (bind mount). `gen_pages.py` writes to `cricstat/tools/staging/web/` by default
  (gitignored, created from cricstat/web; web_preview.py serves it). Edit CSS/JS there too. Go live after approval:
  `rsync -a cricstat/tools/staging/web/ cricstat/web/` (assets first), then delete the staging copy.
- **P0.5 player photos** (own branch, after the deploy): Wikidata P18 → Commons thumbnails fetched by the pipeline,
  self-hosted, per-image licence + author credit (CC BY-SA needs attribution) on the profile and the licences page.

## P1.6 pages (in progress, branch `feat/cricstat-p16-pages`; state at end of the 2026-10-09 evening session, V=88)
- **Predictor page `/cricket/predictor/`** built in STAGING (not live), V=79. Hero: our own gold trophy icon (the official
  2027 logo is non-free/ICC trademark: never use), stamp, "Following" strip, **donut** (top 5 + "all other teams", ≤ 6
  slices, centre = followed team). Board tabs: 🏆 Title odds (direct qualifiers + Qualifier candidates tables) · 📈 Odds
  over time · 📅 **Fixtures** (57 matches by day, filters, chances bar for the 20 fixed group games, ▲/▼ "last moved"
  per card, slots in words, 🌙 day/night) · 🏟️ **Venues** (12 cards: capacity, role, 2027 matches, live history from
  the serving DB, photo + credit) · ⚖️ Ratings · 🗺️ Format · ✅ How good is it? Plus the "Read this first" limits panel.
  Nav "ODI WC 2027" is a live link; "Methodology" still "soon". Licences page: Wikipedia (CC BY-SA 4.0) row, venue photo
  sources, Afghanistan note (Cricsheet's protest + predictor results list), forecast disclaimer.
- **Partial P1.6 deploy LIVE (2026-10-09 23:20 UTC, owner-approved):** merge 9c2b32c → API f974fb246adb (cd-pull,
  API only; `cricstat-models-publish` run 38003122609 left unapproved on purpose) → staging copied to cricstat/web
  WITHOUT predictor/, venues/, assets/predictor.js (commit 54ce200). Live: Countries = world map (win % + matches only),
  hub Following Men/Women + Manhattan, team-page H2H/top-performers tabs, Natural Earth licence row, nav "ODI WC 2027
  soon". Switch: `PREDICTOR_LIVE = False` in gen_pages.py (owner chose: no model numbers — ratings, WC chances — on
  the map until the predictor page and its disclosures launch). **Full P1.6 deploy later:** set PREDICTOR_LIVE = True,
  regenerate (map `data-model="on"`, nav link, predictor page, predictor licence rows), approve models publish,
  cd-pull models → `forecast --force` → copy predictor/, venues/, predictor.js too.
- **ON HOLD by the owner (2026-10-09 evening):** predictor-page approval, methodology page (`/cricket/methodology/`,
  data from `/v1/models/predictor/backtest`), live "Ratings & ODI World Cup 2027" card on men's team pages (countries.js
  `ratingsCard`), hub teaser with the real number, and the P1.6 deploy. Don't start them until the owner says so.
  Approved this session: Title odds tabs, hub Following Men/Women, team-page H2H/top-performers tabs, the world map as
  the Countries landing (+ head to head v followed team, win % for men and women), hub "stat" Manhattan (faint).
- **Staged work is gitignored:** `cricstat/tools/staging/web/` holds predictor.js, worldmap.js, world-map.json, the
  edited hub.js/countries.js, the CSS additions, venues/*.jpg. Tracked snapshot: `cricstat/tools/staging-snapshot/p16/`
  (README lists each file; delete at deploy). Tarball (latest): `cricstat/data/models/backups/p16-staging-web-20261009b.tar.gz`.
- **Code on the branch, not deployed:** models (fixtures time/daynight; forecast stores venues/fixtures meta and the
  `forecast_fixtures` table, schema v2; `venues.csv` reviewed facts + photo credits), API (`/v1/forecasts/{t}/fixtures`
  with venues, fixtures, `last_change`; `GET /v1/records/teams`; pages.py landing/team-header swap), `tools/fetch_venue_photos.py`, `tools/fetch_world_map.py` (reviewed Commons files only; hand-added Flickr
  photo kept), gen_pages (predictor shell, trophy, licences, Countries map landing, hub Manhattan). Tests: models 64, API 79.
- **Preview in a new session:** (if staging is missing: `python3 cricstat/tools/gen_pages.py`, copy the snapshot files,
  `python3 cricstat/tools/fetch_world_map.py`) live forecast.sqlite lacks the new meta until models deploy, so make a dev copy:
  `cp cricstat/data/db/forecast.sqlite cricstat/data/models/dev-forecast.sqlite`; from cricstat-models:
  `CRICSTAT_FORECAST_DB=$PWD/../data/models/dev-forecast.sqlite CRICSTAT_MLFLOW_URI=http://127.0.0.1:9 python3 -m presentation_logic.cli forecast --force`
  (absolute path: relative paths resolve against CRICSTAT_HOME = cricstat/, not the cwd; ~90 s);
  dev API from cricstat-api: `CRICSTAT_HOME=.. CRICSTAT_WEB_DIR=$PWD/../tools/staging/web CRICSTAT_FORECAST_DB=$PWD/../data/models/dev-forecast.sqlite python3 -m uvicorn presentation_logic.api.main:app --host 127.0.0.1 --port 8048`;
  preview: `CRICSTAT_API=http://127.0.0.1:8048 python3 cricstat/tools/web_preview.py` (8090). jsdom checks need
  `npm install jsdom` in a scratch dir and `window.fetch` set in beforeParse.
- **Deploy order for P1.6:** merge → publishes (models, API; pipeline too if the Korogi venue row is added) → cd-pull
  models → `docker compose run --rm cricstat-models forecast --force` (writes venues/fixtures meta) → cd-pull API →
  rsync staging/web → cricstat/web (assets first) → delete staging + snapshot → sitemap: add /cricket/predictor/ (and
  methodology) → check public pages. Licences page: add a Natural Earth (public domain, India's point of view) row for the
  map before deploy. Run `pytest tests/test_pages.py` with `CRICSTAT_TEST_WEB=<staging/web>` before the rsync.
- **Photo rules learned:** only PD/CC0/CC BY/CC BY-SA (+ Public Domain Mark) with credit; look at every photo before use
  (an automatic Wikidata lookup once returned Zimbabwe in Dhaka for "Victoria Falls"); Tripadvisor and Facebook photos
  are not usable (no licence; terms forbid reuse); Openverse/Flickr licence filters are the search route. 8 of 12 grounds
  have photos; Harare, Bulawayo, KuGompo City, Victoria Falls have none (owner: fine to leave missing).
- **Fixture chances** move only when one of the two teams plays; `last_change` = the most recent move.
- **Review round 2026-10-09 (owner):** Title odds = two small tabs (direct qualifiers / Qualifier); hub "Following" =
  Men/Women pill + names-only list; team pages' "By format" = Head to head / Top performers tabs. **Countries landing =
  cricket world map** (`/cricket/countries/`; `assets/worldmap.js`, `assets/world-map.json` built by
  `tools/fetch_world_map.py` from Natural Earth 1:10m **India's point of view** borders + UK map units, public domain;
  team pages keep their URL, get a "🌍 World map" link; `pages.py` hides the landing and shows the team header on
  server-rendered team pages). Map colours: ODI rating / WC 2027 title chance (men), ODI + T20I win % last 2 yrs
  (min 5 matches) and matches (both); hover card + panel: rating/rank, WC title/final/semi + status, 2-yr W–L, head to
  head v the followed team (ODI/T20I, same gender), matches + last played. New API `GET /v1/records/teams` (one call for
  every team's record). Hub pitch: the "stat" half is a **Manhattan of India's 2011 World Cup final chase** (real
  Cricsheet data, match 433606, captioned; last bar = the six; faint by owner request). V=88. **Predictor page approval: paused by the owner;
  methodology page not started.** Women's team ratings = a later step with its own backtest (not in P1.6).

## Next up and open TODOs (updated 2026-10-09, after the partial P1.6 deploy)
- **State (2026-10-09):** P0, P0.5, P0.6 and P1.1–P1.5 live; **partial P1.6 live** (world map Countries landing with
  win %/matches, Following Men/Women, team-page tabs, hub Manhattan; API f974fb246adb; web commit 54ce200; owner
  checked it). Everything is merged to `main` and pushed. **On hold until the owner says so:** predictor page,
  methodology, team-page ratings card, hub teaser, `PREDICTOR_LIVE = True`, models publish (run 38003122609 waiting).
  LinkedIn follow-up post published 2026-10-08.
- **Next: P1, the ODI World Cup 2027 predictor** (plan in "Plan" above): (1) Elo team ratings + Monte Carlo tournament
  simulation as the baseline (ships first), backtested on WC 2019 and 2023 with calibration; (2) gradient-boosting
  challenger with squad features; (3) DL player embeddings from a ball-by-ball sequence model (also live win
  probability). The best-calibrated model powers the live forecast; the comparison is published. Model jobs run as
  `cricstat-models` (scheduled), MLflow experiments `cricstat-*`, promotion only when backtests don't regress (F9).
  The forecast is identical for every team; disclose withheld Afghanistan men's matches.
  **Plan approved 2026-10-08** on branch `feat/cricstat-p1-elo`: `docs/P1-predictor-plan.md` + `docs/P1-afghanistan-audit.md`.
  Steps P1.1 data layer -> P1.2 Elo + tuning -> P1.3 simulator + backtests -> P1.4 `cricstat-models` service/CI/CD ->
  P1.5 API -> P1.6 pages; stop for review after each. Locked: **the 2027 format changed** (ICC 15 Jul 2026: Super Series
  of 3 -> 2 groups of 6 -> Super 7 -> semis 1v4/2v3 -> final 21 Nov); D1 = S1, an Afghanistan results-only supplement
  from Wikipedia (188 ODIs 2009-2026) used only for ratings/predictor/backtests, outside the serving DB, reviewed before
  use (Wikipedia can be vandalised); D2 associates start lower by one rule; D3 simulate the Qualifier; D4 publish bar
  §3.3; D5 `models forecast` chained onto the 05:30 task. **Key gotcha:** serving `team_key`/`match_key`/`player_key`
  are load-order rowids and can renumber on a full build, so anything outside the serving DB keys on `match_id`,
  (name, gender, team_type) and `player_id`. Exclude composite XIs from Elo. Never join players by name (two Rashid Khans).
- **2027 venues (2026-10-08, live):** venue_map merges sponsor renames (Mangaung Oval = Goodyear/Chevrolet/
  OUTsurance; Wanderers = New Wanderers; Boland Park = Boland Bank Park; Diamond Oval = De Beers Diamond Oval);
  pipeline 176a2d29e92e, build 9. Pages V=73: "★ WC 2027" on match cards at the 2027 grounds and ★ in player
  "Most-played venues" (list `WC2027_VENUES` in assets/cricstat.js, matched on name + city). cd-pull from a
  shell needs `DOCKER="sudo -n docker"` (without it, it wrongly reports "not published yet").
- **Small open items:** New venue Korogi Sports Park, Nisshin (Japan) has no country in venue_map.csv: add it with the
  next pipeline publish. Later (P1b): Wikidata bowling style coverage check for squad features. Ecclestone T20I runs-conceded check (see Golden follow-up); 19 golden blocks with a few missing
  matches to review.
- **Workflow:** feature branch per sub-phase, `--no-ff` merge, push, user approves publishes on GitHub, then
  `cd-pull.sh` (schema changes: `CRICSTAT_SERVICES=cricstat-pipeline` first, build, then the API). Docker via
  `sudo -n docker`. Never `docker compose build` the cricstat images on the NAS. Page work goes in
  `cricstat/tools/staging/web/` (cricstat/web is live) and `website/` changes are staged in `cricstat/tools/staging/`.
- **Owner TODOs:** (1) email Cricsheet to confirm the match-file licence (mention the `playeer_out` typo in match
  1410291 and the 10 man/woman shared Register ids under P0.1) and file the reply in `docs/`; (2) set up a Console
  API workspace with prepaid credits and no auto-reload before P4; (3) watch Search Console (Pages, Sitemaps, Queries).
- Wireframe source is copied in `docs/wireframes/`. The canvas at the F2 link is the editable master.
