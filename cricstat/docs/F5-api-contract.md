# F5 — cricstat API contract

Status: **approved** (2026-10-05). Builds on F3 (tables) and F4 (metric rules and views).
This is the **one interface** for every consumer: the web pages, the Ask agent's tools, the MCP server, the
golden-set checks and the eval harness. If a number appears on the site, it came through this API.

## 1. Services and routing
| Public path | Nginx → container | Service | Methods |
|---|---|---|---|
| `/cricket/` | static files (like the homepage) | — | GET |
| `/cricket/api/` | `proxy_pass http://cricstat_api/` (prefix stripped, platform pattern) | `cricstat-api` (FastAPI) | **GET only** |
| `/cricket/ask/api/` | `proxy_pass http://cricstat_agent/`, `proxy_buffering off` (streaming) | `cricstat-agent` (FastAPI + LangGraph) | GET, POST |

- `cricstat-api` opens the serving DB **read-only**. When `build_info` changes, it reopens so it picks up the newly
  swapped file (F3 §8).
- The agent never touches the DB directly. Its tools call `cricstat-api` over the internal Docker network.
  The one exception is the guarded SQL fallback (§6).
- Containers answer at their own root (`/v1/...`), so they don't know their public URL (ADR-003).

## 2. Conventions
- **Versioning:** `/v1/…`. Adding fields or endpoints is non-breaking. Renaming or removing anything means `/v2`.
- **Public identifiers only:** surrogate `*_key` values change between full rebuilds, so they are never exposed.
  | Thing | Public id | Example |
  |---|---|---|
  | Player | Cricsheet `player_id` (8 hex) | `ba607b88` |
  | Match | `match_id` (text) | `1384392`, `wi_201706` |
  | Team | slug of name + gender (+ "club" for leagues) | `india-men`, `india-women`, `mumbai-indians-men` |
  | Competition | `competition_slug` | `ipl`, `icc-cricket-world-cup` |
  | Venue | canonical venue slug | `wankhede-stadium-mumbai` |

  Page URLs add a readable slug for search engines: `/cricket/players/virat-kohli-ba607b88/`. Only the id is used for lookups.
- **Common filters** (any endpoint they make sense for):
  | Filter | Values |
  |---|---|
  | `scope` | `ALL` · `TEST` · `ODI` · `T20I` · `LEAGUES` · a competition slug (F4 R21/R22) |
  | `gender` | `male` · `female` |
  | `from`, `to` | ISO dates, or a season such as `2023` / `2023-24` |
  | `opponent` | team slug |
  | `venue` | venue slug |
  | `phase` | `powerplay` · `middle` · `death` |
  | `min_innings`, `min_balls`, `min_wickets` | qualification thresholds |
  | `limit`, `offset` | `limit` ≤ 100, default 20 |
- **Numbers:** returned unrounded. Undefined values (e.g. an average with no dismissals) are `null`.
  The page shows "—". Display is the page's job: ratios are cut to 2 decimals, not rounded (F4 R23).
- **Every response uses one envelope**, which also carries the provenance the Ask page shows:
  ```json
  {
    "data": { "...": "..." },
    "meta": {
      "data_as_of": "2026-10-04", "build_id": 412,
      "filters": { "scope": "ODI", "gender": "male" },
      "metrics": { "average": "runs ÷ dismissals (retired hurt is not out)", "strike_rate": "runs × 100 ÷ balls faced (wides excluded)" },
      "coverage": "Cricsheet ball-by-ball, 2001–present; Afghanistan men's matches not included",
      "attribution": "Match data from Cricsheet (cricsheet.org), used under the Open Data Commons Attribution License 1.0.",
      "next": "/v1/…?offset=20"
    }
  }
  ```
  `meta.metrics` comes from `semantic_catalog` (F4 §4), so every number travels with its formula.
- **Errors:** `application/problem+json` (RFC 9457): `{type, title, status, detail}`.
  | Status | Meaning |
  |---|---|
  | 400 | Bad filter |
  | 404 | Unknown id |
  | 422 | Filters that can't combine (e.g. `phase` with `TEST`) |
  | 429 | Rate limited |
  | 503 | Kill switch on (agent only) |
- **Caching:** the data changes about once a day. Responses carry `ETag: "<build_id>"` and
  `Cache-Control: public, max-age=300, stale-while-revalidate=3600`. Cloudflare can cache GETs.
- **Rate limits** (Nginx, keyed on `CF-Connecting-IP` like the existing CSP zone): API about 10 req/s per IP (burst 20).
  Agent limits are in §5.
- **Security:** GET-only stats API, no cookies, no auth, read-only DB, and no CORS (same origin).
  Request size and time limits apply.
- **Performance targets:** API p95 < 300 ms on the NAS. Stats pages p95 < 1 s (F1).

## 3. Endpoints — `cricstat-api`
### Meta and status
| Endpoint | Returns | Used by |
|---|---|---|
| `GET /v1/health` | `{status}` (for Nginx and the deploy smoke test) | ops, CD |
| `GET /v1/status` | Latest build (`build_info`), last ingest runs (added / updated / unchanged), match count, data-as-of | Hub data strip, Methodology "Pipeline status" |
| `GET /v1/meta/scopes` | Scopes and formats, with labels | page filters, agent |
| `GET /v1/meta/competitions?featured=true` | Competitions (slug, name, gender, seasons) | Leagues tab, IPL card |
| `GET /v1/meta/metrics` | Every metric: name, definition, unit (from `semantic_catalog`) | Methodology "Metric definitions", agent prompt |

### Search and identity
| Endpoint | Returns | Used by |
|---|---|---|
| `GET /v1/search?q=&type=player\|team\|competition` | Ranked candidates, each with disambiguation info (country, gender, years active, matches) | search boxes, "Did you mean…", agent `resolve_player` |
| `GET /v1/players/{player_id}` | Identity, Wikidata bio (nullable), teams represented (`player_teams`), formats played | Player header card |

### Players
| Endpoint | Returns | Used by |
|---|---|---|
| `GET /v1/players/{id}/career?scope=` | Batting, bowling and fielding (`v_player_*` views), including run-out involvements, labelled (F4 R12) | Player tables (Test / ODI / T20I / Leagues / All buttons) |
| `GET /v1/players/{id}/years?scope=` | One row per year | Year-by-year chart |
| `GET /v1/players/{id}/phases?scope=&competition=` | Phase splits with labels (`v_player_phase`) | T20 phase splits |
| `GET /v1/players/{id}/splits?by=opponent\|venue\|season&scope=` | Grouped totals and ratios | Top opponents and venues |
| `GET /v1/players/{id}/innings?scope=&from=&to=&limit=` | Innings-by-innings list (the atoms) | Form, agent follow-ups |

### Teams
| Endpoint | Returns | Used by |
|---|---|---|
| `GET /v1/teams/{slug}` | Identity, current ratings by format | Country header |
| `GET /v1/teams/{slug}/record?scope=` | `v_team_record` by format | Record by format |
| `GET /v1/teams/{slug}/results?scope=&from=&to=&limit=` | Recent results | Last 5 (Hub India cards), results by year |
| `GET /v1/teams/{slug}/head-to-head?scope=&opponent=` | `v_head_to_head` | H2H table |
| `GET /v1/teams/{slug}/home-away?scope=` | Home / away / neutral split | Home vs away |
| `GET /v1/teams/{slug}/top-players?scope=&metric=runs\|wickets&limit=` | Leaders for that team | Most runs and most wickets |
| `GET /v1/records/teams?scope=&gender=&type=&from=&to=` (P1.6) | Every team's record in one scope + window, one row per team (W/L/T/D/NR, win %, last date); scope required | World map win % (one call instead of one per team) |

### Matches and competitions
| Endpoint | Returns | Used by |
|---|---|---|
| `GET /v1/matches?team=&scope=&competition=&from=&to=` | Match list | India at World Cups, fixtures and results |
| `GET /v1/matches/{match_id}` | Summary scorecard: innings totals, top batters and bowlers, result, method | Match links, agent |
| `GET /v1/competitions/{slug}/seasons` | Seasons, with winners where known | IPL feature |

### Leaderboards (the agent's workhorse)
| Endpoint | Returns |
|---|---|
| `GET /v1/leaderboards/batting?metric=runs\|average\|strike_rate\|hundreds\|sixes&…filters` | Ranked players, values, qualification used |
| `GET /v1/leaderboards/bowling?metric=wickets\|economy\|average\|strike_rate\|dots&…filters` | Same, for bowlers |

Example: "best death-overs economy in IPL since 2020, min 30 overs" becomes
`/v1/leaderboards/bowling?metric=economy&scope=ipl&from=2020&phase=death&min_balls=180&sort=asc`.

### Predictor (data written by `cricstat-models`, P1)
| Endpoint | Returns | Used by |
|---|---|---|
| `GET /v1/forecasts/wc-2027/latest` | Per team: probability of each stage; `n_simulations`, `model_version`, `data_as_of`, `mlflow_run_id` | Predictor table, Hub headline and India card |
| `GET /v1/forecasts/wc-2027/history?team=` | Title chance over time, with the match that moved it | Odds-over-time chart, "why did it change?" |
| `GET /v1/ratings?scope=ODI&gender=male` | Current ratings and rank | Country rating card |
| `GET /v1/ratings/{team_slug}/history?scope=` | Rating after each match | Charts |
| `GET /v1/models/predictor/backtest` | The three-model comparison (Elo vs ML vs DL): Brier, log-loss, calibration bins for WC 2019/2023 | Predictor and Methodology backtest |

**As built (P1.5, 2026-10-08).** Data comes from `data/db/forecast.sqlite` (written by cricstat-models,
same atomic-swap contract as the serving DB); if it's missing only these endpoints answer 503
"Forecast unavailable". ETag = `"<build_id>-f<forecast_id>"`. `meta.coverage` adds the Afghanistan
results-list note. Team ids are the API team slugs (`india-men`); Afghanistan men has `slug: null`
(no team page) but a `team_uid`.
- `latest`: `tournament` (dates, hosts, groups), `forecast` (id, created_at, data_as_of, n_simulations,
  model_version, mlflow_run_id, days_to_start, rating_uncertainty_sd), `stages`, `teams[]`
  (rating, group, direct_qualifier, `probabilities` per stage: qualified, super_series, group, super7,
  semi, final, champion), `model`, `assumptions` (the format's TBC rules), `disclosures` (model, not
  advice, not used, Afghanistan, data, qualifier).
- `history?team=`: one entry per forecast with that team's champion/final/semi/super7 chances and
  `moved_by` (the men's ODIs new since the previous forecast); without `team`, every team's champion
  chance per forecast.
- `ratings?scope=ODI&gender=male` (other scopes → 400): rating, matches, last_match, `active` (an ODI in
  the last two years) and `rank` among active teams. `ratings/{slug}/history`: rating after each match.
- `models/predictor/backtest`: champion (version, MLflow run, Elo parameters, drift, no-result rates),
  metrics, gates, `backtest` (tests A/B/C per tournament, reliability, drift, replay), the `comparison`
  table (Elo live; win-rate reference; ML and DL "planned"), all `versions`, `disclosures`.
- `/v1/admin/jobs` gains a `forecast` block (last forecast + model).
| `GET /v1/models/agent/evals` | Latest eval run per system (accuracy, latency, cost) | Methodology "Analyst evaluation" |

## 4. Response example — `GET /v1/players/{id}/career?scope=ODI`
```json
{
  "data": {
    "player": {"player_id": "ba607b88", "name": "[Player]", "gender": "male"},
    "scope": "ODI",
    "batting": {"matches": 0, "innings": 0, "not_outs": 0, "runs": 0, "balls_faced": 0, "high_score": 0,
                "high_score_not_out": false, "average": null, "strike_rate": null,
                "hundreds": 0, "fifties": 0, "ducks": 0, "fours": 0, "sixes": 0},
    "bowling": {"innings": 0, "legal_balls": 0, "overs_display": "0.0", "maidens": 0, "runs_conceded": 0,
                "wickets": 0, "average": null, "economy": null, "strike_rate": null, "best": {"wickets": 0, "runs": 0}},
    "fielding": {"catches": 0, "stumpings": 0, "run_out_involvements": 0,
                 "notes": {"run_out_involvements": "Not an official statistic: counts each fielder listed in a run-out."}}
  },
  "meta": {"data_as_of": "…", "build_id": 0, "filters": {"scope": "ODI"}, "metrics": {"…": "…"}, "attribution": "…"}
}
```
The values shown are placeholders; the shape is the contract.

## 5. Endpoints — `cricstat-agent`
| Endpoint | Purpose |
|---|---|
| `POST /v1/chat` | Body `{thread_id?, message}` (message ≤ 500 chars). Response is a **Server-Sent Events** stream (§5.1) |
| `GET /v1/quota` | `{remaining_today, limit_today, resets_at}`, for the "[n] of [N] questions left today" line |
| `GET /v1/health` | Status, including whether the kill switch is on |

### 5.1 Stream events (what the Ask page renders)
| Event | Payload | UI |
|---|---|---|
| `interpreted` | `{filters: {competition, from, phase, min_overs, sort}, entities: [{type, id, name}]}` | "Interpreted as" chips |
| `clarify` | `{question, options: [{id, label}]}` | "Which player do you mean?" buttons, then the stream ends |
| `tool_call` | `{tool, args}` | "How this was computed": tool line |
| `tool_result` | `{tool, rows, meta}`, where `meta` is the API envelope's meta (formula, data_as_of) | Result table + formula line |
| `token` | `{text}` | Streaming answer text |
| `final` | `{answer, provenance: [tool_result.meta…], model, usage: {input_tokens, output_tokens}}` | Done |
| `refusal` | `{reason}`, e.g. out of scope, or the question needs data we don't have | Honest refusal |
| `error` | Problem object | Error message |

### 5.2 Agent limits and privacy
- **Per IP:** 5 questions a minute and **20 a day**. A global daily token budget (the $1–2/day ledger) returns 429,
  and the kill switch returns 503.
- **Threads:** conversation state (structured filters + messages) is kept in the LangGraph SQLite checkpointer,
  keyed by a random `thread_id` held only in the page's memory. **No cookies.** Threads and logs are deleted after
  **30 days** (privacy page). IPs are used only for rate limiting.
- **Untrusted data:** tool results are treated as data, never as instructions.

## 6. Agent tools ↔ API (and MCP)
| Tool | Calls | Notes |
|---|---|---|
| `resolve_player(name, context)` | `/v1/search?type=player` | Ambiguous → `clarify` event |
| `resolve_team(name, gender)` | `/v1/search?type=team` | |
| `player_stats(player_id, scope, filters)` | `/v1/players/{id}/career`, `/years`, `/phases`, `/splits` | |
| `leaderboard(kind, metric, filters)` | `/v1/leaderboards/batting\|bowling` | |
| `team_record(team, scope, filters)` | `/v1/teams/{slug}/record`, `/head-to-head`, `/results` | |
| `match_summary(match_id)` | `/v1/matches/{match_id}` | |
| `forecast(team?)` | `/v1/forecasts/wc-2027/latest`, `/history` | |
| `run_sql(query)` (fallback) | **Internal only:** a read-only connection to the semantic views, SELECT-only (parsed), LIMIT-wrapped, time-limited | Never exposed through the public API |

The **MCP server** (P6) exposes the same tools, except `run_sql`, by calling the same endpoints. The **eval harness**
(P3) and the **golden-set check** (F4 §3) also call the API, so they test exactly what visitors see.

## 7. Review decisions (2026-10-05)
1. **API docs published:** FastAPI's OpenAPI docs go public and read-only at `/cricket/api/docs`, rate-limited.
2. **Agent limits:** **20 questions per IP per day** (under the global daily budget cap); threads and chat logs are
   **deleted after 30 days**. These values replace `[N]` in §5.2 and go on the privacy page (F8).
3. **Streaming: Server-Sent Events.** One request per question; it works with the existing Nginx per-IP limits and logs,
   and Cloudflare passes it through. WebSockets were rejected (more code and config for two-way traffic we don't need).
   The live World Cup tracker polls every few minutes instead.

## 8. Implementation notes (P0.3, 2026-10-06)
- **Additions** (non-breaking): `GET /v1/teams?gender=&type=` (team picker) and `GET /v1/teams/{slug}/years`
  (Countries "Results by year").
- **Dates:** `from`/`to` accept `YYYY-MM-DD`, a year (`2023`) or a season (`2023-24` = 1 Jul 2023 – 30 Jun 2024).
- **Scopes** accepted everywhere: `ALL`, `LEAGUES`, any format key (`TEST`, `ODI`, `T20I`, `HUNDRED`…) and featured
  league slugs (`ipl`, `wpl`, `bbl`…). `phases` with `ALL`, `LEAGUES` or a multi-day format → 422.
- **Docs:** decision 7.1 is pending a self-hosted docs page (P0.4): Swagger/ReDoc load scripts from a CDN, which the
  privacy promise rules out, so only `/openapi.json` is served for now.
- **Time limit:** a query over 10 s is interrupted → 503 "Query took too long".

## 9. Additions (2026-10-10)
- `GET /pages/predictor/` (not part of `/v1`, like the P0.6 player/team pages): the predictor's static shell with
  the live forecast written in — search title, description with the top-3 chances, "The forecast in words"
  (4 Q&A + every team's chances), WebPage `dateModified` + FAQPage JSON-LD, own og:image. Nginx `location =
  /cricket/predictor/` proxies it and serves the static page on 502/503/504. ETag = forecast id + shell mtime.
- `GET /pages/sitemap.xml` also lists `/cricket/predictor/` and `/cricket/methodology/`, dated by the latest forecast.
- **HEAD** is answered like GET without a body on every route (`HeadAsGet` middleware); before, HEAD got 405.
