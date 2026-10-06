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
- Gaps: Afghanistan men's & Afghanistan Premier League matches withheld (377); completed matches only (~1 day lag); no player bio data.
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
| F7 | Roadmap + decision log | Ongoing in this file (current to 2026-10-05) |
| F8 | Compliance & trust (licences page, privacy update, disclaimers) | Folded into P0 (decided 2026-10-05) |
| F9 | CI/CD & automation (`docs/F9-cicd-automation.md`) | Done 2026-10-05: CI + approval gate + GHCR + NAS cd-pull.sh (DSM daily 05:15); merged to main |
| P0 | Ingestion → serving-DB build → cricstat-api → first live pages (+F8) | Ingestion done and deployed with CI/CD; **build step is next** |
| P1–P6 | Predictor + win prob → tools → test set → agent → public demo → extras | Later |

Git: work on branch `feat/cricstat-foundation`, merge to `main` with `--no-ff` (platform workflow, ADR-018).

## DSM scheduled tasks (operator creates them in DSM → Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script)
Both run as user **root**. Task Settings → Notification: tick "Send run details by email" and
"Send run details only when the script terminates abnormally". Pipeline exit codes: 0 = ok, 1 = error, 2 = data-quality gate.
| Task name | Schedule | Run command |
|---|---|---|
| cricstat CD pull | Daily, 05:15 | `sh /volume1/pandya-homelab/deployment/cricstat/cd-pull.sh` |
| cricstat daily refresh | Daily, 05:30 | `cd /volume1/pandya-homelab/deployment/cricstat && /usr/local/bin/docker compose run --rm cricstat-pipeline recent` |
| cricstat monthly full | Monthly, day 1, 04:00 | `cd /volume1/pandya-homelab/deployment/cricstat && /usr/local/bin/docker compose run --rm cricstat-pipeline full` |
The `build` step (P0) and model jobs (P1) are appended to these commands when they exist (F6 §4).

## P4/P5 security checklist (before the agent goes public)
- [ ] **DSM firewall:** add a deny rule for `172.25.0.0/24` placed **above** the existing `172.16.0.0/12` allow, so
      cricstat containers (which handle visitor input) cannot open connections to DSM/host services. They only need
      each other, Nginx and the internet. Test with the stack running (rule order matters), and record it in F6 §2.
- [ ] Agent safeguards from F5 §5.2: per-IP limits (5/min, 20/day), global daily budget cap, kill switch,
      30-day retention, tool output treated as data.
- [ ] The `run_sql` fallback is read-only, SELECT-only (parsed), LIMIT-wrapped and time-limited, against views only.
- [ ] `deployment/cricstat/.env` is mode 600, and the API key is in a dedicated Console workspace with prepaid credits and no auto-reload.
- [ ] Privacy page updated (Anthropic as a processor, retention, no cookies) before launch (F8).

## Next up and open TODOs (as of 2026-10-05, end of the foundation sprint)
- **Decided next step: P0.** F8's texts (Data & Licences page, privacy-page additions, disclaimers) are written inside P0,
  because P0 is the first time pages go public. P0 scope, in order:
  1. `cricstat-pipeline build`: raw → serving DB (`sql/serving_schema.sql` + `reference_data.sql` + `semantic_views.sql`),
     full and incremental modes, F4 fixture tests, data-quality checks, atomic swap. Includes the Register download
     (people.csv, names.csv) and the venue → country map draft (F3 decision 2).
  2. `cricstat-api` (FastAPI, GET-only, F5 contract) for the Players and Countries endpoints first, plus its publish
     workflow, NAS smoke test and health check in `cd-pull.sh`.
  3. First live `/cricket/` pages: hub, players, countries, licences (static `cricstat/web/`, Nginx changes from F6 §2).
  4. F8 texts + the golden-figure set (about 50 players and 10 teams incl. India; the user reviews them).
- **State:** everything is merged to `main` (merge `2e5cddc`). The image is on GHCR (public). The NAS runs DSM tasks
  05:15 CD pull, 05:30 daily refresh, and monthly full on day 1 at 04:00.
  Publishing (`cricstat-publish.yml`) needs the user's approval and runs only when `cricstat/cricstat-pipeline/**` changes.
- **Workflow:** feature branch per sub-phase (e.g. `feat/cricstat-p0-build`), `--no-ff` merge, push. Docker calls via
  `sudo -n docker` (each one is gated by an ask rule). Never `docker compose build` on the NAS now that CD is live.
- **Owner TODOs:** (1) email Cricsheet to confirm the match-file licence (and mention the `playeer_out` typo in match
  1410291), and file the reply in `docs/`; (2) write the "Why I built this" story (placeholder on the hub wireframe);
  (3) set up a Console API workspace with prepaid credits before P4.
- Wireframe source is copied in `docs/wireframes/`. The canvas at the F2 link is the editable master.
