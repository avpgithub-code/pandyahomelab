# cricstat Head to Head — plan

Status (2026-10-26): **H1–H4 built, nothing deployed.** Branch `feat/cricstat-h2h`, draft PR
[#2](https://github.com/avpgithub-code/pandyahomelab/pull/2). The owner is reviewing the private preview (§10). Next
is H5, then one deploy. Plan approved 2026-10-26 (decisions in §9). Built step by step with a review stop after each
step (§8).

## 1. What it is

A **Head to Head** section at `pandyahomelab.com/cricket/h2h/`, with three page types. Each is named in the words
people search for, and every number comes from cricstat's own ball-by-ball data:

| Page type | Example address | What it answers |
|---|---|---|
| **Matchup** (batter v bowler) | `/cricket/h2h/jasprit-bumrah-vs-steve-smith/` | "Bumrah vs Smith": balls, runs, dismissals between them |
| **Player comparison** (same role) | `/cricket/h2h/joe-root-vs-virat-kohli/` | "Kohli vs Root": careers side by side, per format |
| **Country head to head** | `/cricket/h2h/australia-vs-india/` (men; `-women` suffix for women) | "India vs Australia ODI head to head": results, records, recent meetings |

**Why:** "X vs Y" is among the most common cricket searches. ESPNcricinfo has an interactive "Compare Players" tool and
CricStatsHQ has matchups, so this is **competition, not an empty niche**. The opening is a **page per pair that Google
can index**, with a plain-words summary it can quote, built on checked numbers. It also shows recruiters SQL and
data modelling over 11.6M rows and search-ready pages.

**What it isn't:** no new model and no AI. It is statistics, with the same rules and checks as the player pages.

## 2. Facts this plan rests on (measured 2026-10-26 on the live serving DB)

- `deliveries` (11.6M rows) has `batter_key` and `bowler_key` with an index on each, and `dismissals` has
  `bowler_key` + `credited_to_bowler`. Every matchup number can be derived; no new source data is needed.
- **97,484** batter-v-bowler pairs have ≥ 30 balls between them (all formats and competitions).
- A single pair computed live takes **2.3–4.7 s** on the NAS disks (cold). That is too slow for a page, so matchups
  are **precomputed at build time** (§5).
- **H1 trial on a copy of the live DB (2026-10-26):** the mart adds **26 s** to the build and **+26 MB**
  (326,350 pairs, 122,748 dismissal-kind rows). All pairs are kept, with no minimum, so the build checks can prove
  that the sums equal the batting atoms. Both checks were **0** on the full data. T20I has few long duels (197 pairs
  with ≥ 60 balls), so T20I matchups need a lower bar when pairs are chosen (H5).
- Country head to head already exists: `GET /v1/teams/{slug}/head-to-head?scope=&opponent=` (`v_head_to_head`),
  shown as a tab on team pages. Country pages reuse it.

## 3. Which pages are indexed at launch (~150; internationals only)

| Type | How chosen | Count |
|---|---|---|
| **Matchups** | ~20 famous duels hand-picked by you (e.g. Bumrah v Smith, Anderson v Kohli), plus data-driven pairs with ≥ 60 legal balls in **official internationals** between two indexable players, ranked by balls | ~90 |
| **Player comparisons** | Top run-scorers / wicket-takers per format over the last 5 years, paired within the same format and gender, plus hand-picked (Kohli v Root, Mandhana v Lanning) | ~30 |
| **Country head to heads** | ICC full members: the most-played men's pairs (India v Australia, India v Pakistan, the Ashes sides…) + the top women's pairs | ~30 |

Rules:

- **One page per pair:** names in alphabetical order of slug; the reverse order 301-redirects.
- Men and women both; never a man v a woman.
- **Internationals only** at launch (Tests, ODIs, T20Is). League matchups (IPL/WPL) come later.
- Any two players can be compared through a **"Compare with…"** box on player pages. Pairs outside the indexed
  set still work but are `noindex`, so they never become thin pages in search.
- Afghanistan men's matches are withheld by Cricsheet. Pages involving Afghanistan say so plainly; pairs where the
  gap hides most of the history are left out of the indexed set.

## 4. What's on each page

All three types share:

- **"Head to head in words":** 3–4 neutral sentences built from the numbers (the part Google reads and quotes).
  It compares figures and never declares who is "better".
- **Format tabs:** ODI first, as everywhere on cricstat.
- **Coverage note** when history predates dense Cricsheet coverage ("our data has M of N of their ODIs").
- **Share card** (1200 × 627) and links to the player/team pages and related head-to-heads.

Specific parts:

- **Matchup:** balls, runs, dismissals (and how: bowled, caught, lbw…), dot %, 4s/6s, strike rate, average per
  dismissal, first and last meeting, and the matches where it happened.
- **Player comparison:** batting (Mat, Inn, Runs, Ave, SR, 100/50, HS) and bowling (Wkts, Ave, Econ, SR, BBI) side
  by side with the better figure highlighted; their matchup, if one bowled to the other; situations (chasing v
  batting first, home v away, phase).
- **Country:** won/lost/tied/NR per format, home/away/neutral split, last 10 results, top run-scorers and
  wicket-takers in the fixture.

### The landing page: picker + popular head-to-heads (`/cricket/h2h/`, owner's idea, approved 2026-10-26)

```
 Head to Head        [ Players | Countries ]        [ Men | Women ]

 [ Virat Kohli         ▾ ]   vs   [ James Anderson      ▾ ]     [ Compare ]

 ── Popular head-to-heads ─────────────────────────────────────
  Warner v Broad · Stokes v Ashwin · Kohli v Anderson · Root v Bumrah …
  India v Australia · India v Pakistan · The Ashes …
```

- **Picker, for visitors (any pair):**
  - **Players:** two search-as-you-type boxes (4,800+ players, so search rather than a dropdown), reusing the
    Players search. The second box offers only the same gender and ranks first the players the first one actually
    met (most balls between them).
  - **Countries:** two dropdowns; the second lists only opponents the first has played, with the match count.
  - **Compare** opens the pair's own page (`/cricket/h2h/<a>-vs-<b>/`), so every result has a shareable link. The
    page shows a **comparison** always, the **matchup** section when one bowled to the other (both directions when
    both bowl), and the **country** layout for teams.
- **Popular head-to-heads, for search engines:** the curated ~150 pairs are listed under the picker as plain
  links. Only these are indexed; picker-built pairs work for visitors but are `noindex`.
- No-JS fallback: the popular links still work.
- Entry points: a "Head to Head" item in the cricstat nav, and a "Compare with…" button on player and team pages
  that pre-fills the first side.

| | Picker | Popular list |
|---|---|---|
| Serves | fans exploring | search traffic |
| Covers | any pair | ~150 strong pairs |
| Indexed | no | yes |

## 5. How it's built

| Layer | Change |
|---|---|
| **Pipeline (build)** | New mart `matchups(batter_key, bowler_key, scope, balls, runs, dots, fours, sixes, outs, first_match, last_match)` + a small `matchup_outs(…, kind, n)` for dismissal types. Same scopes as `player_career`, international scopes only at first. Every pair is kept (H1 measured +26 s, +26 MB); page thresholds are applied when pairs are chosen. |
| **API** | `GET /v1/h2h/opponents/{player_id}?scope=` (who this player met most, for the picker), `GET /v1/h2h/players/{a}/{b}?scope=` (both careers + matchup both ways + situations), `GET /v1/players/{id}/matchups?as=batter\|bowler&scope=&limit=`, and the existing team head-to-head for countries. Read-only and cached like the rest. |
| **Pages** | Server-rendered heads like the player and predictor pages: title ≤ 60 chars (e.g. "Bumrah vs Smith: Head to Head Stats \| cricstat"), description ≤ 155 with numbers first, canonical, JSON-LD, the words section, and the static shell when the API is down. Templates are built by `gen_pages.py`. |
| **Sitemap** | Indexed pairs only, with the data date as `lastmod`. |
| **Existing pages** | Player pages get a "Head to head" row (top rivals as batter and as bowler) + "Compare with…"; team pages link their head-to-head tab to the new country page. |

## 6. How it's checked

- **Formula tests:** ratios follow F4 (averages, strike rates, the R23 cut-off to 2 decimals).
- **Consistency tests (every build):** a batter's balls summed over all bowlers = balls faced in `batting_innings`;
  the same for runs, and for dismissals credited to bowlers. The build fails rather than publish wrong numbers.
- **Golden head-to-heads:** 15 matchups and 5 country records checked by hand against published figures
  (Wikipedia, articles quoting balls/runs/dismissals). They go into `docs/validation/` like the golden figures; any
  difference is explained (coverage gap, withheld matches) or fixed.
- **Page tests:** title/description lengths, `noindex` outside the set, the reverse-order 301, the static fallback.

## 7. Guardrails

- **Neutral by design:** the same rules for every player and team, and no "better player" verdicts.
- **Honest samples:** under 30 balls is labelled "small sample" and never used as a headline.
- No board, team or league logos. Photos only where the licence allows, with credit (existing rules).
- ESPNcricinfo/Statsguru are not scraped, and its Compare tool's results are not copied; golden checks are manual.

## 8. Steps (branch `feat/cricstat-h2h`; review stop after each)

| Step | Deliverable | Status |
|---|---|---|
| H0 | This plan | Approved 2026-10-26 |
| H1 | `matchups` mart + consistency tests; build time and DB size measured | **Done** 5b5414a: +26 s, +26 MB, checks 0 on live copy |
| H2 | Golden head-to-heads (you check the references) | **List ready** d9bfb9f (`docs/validation/h2h-golden.csv`, 70 rows); **owner filling references** |
| H3 | API endpoints + tests | **Done** 28c232d: 2 endpoints + `opponent` filter on team results; 95 API tests |
| H4 | Landing page (picker + popular list) + result templates (matchup, comparison, country) + nav and "Compare with…" entry points, previewed in staging | **Built** 81816b1, b3f6039 (format tabs in the picker row, owner request), d8b68e4 ("See all N" dismissal list on each matchup, owner idea; liked 2026-10-27); **owner reviewing** |
| H5a | Pair selection: your list `docs/h2h/picked.csv` + data rules → `docs/h2h/pairs.csv` (`tools/h2h_pairs.py`); landing page lists it | **Built** 2026-10-27: 154 pairs (92 matchups, 30 comparisons, 32 countries); **owner editing picks** |
| H5b | Server-rendered pair pages (title, description, canonical, JSON-LD, "in words"), `index` only for `pairs.csv`, sitemap, reverse-order 301, nginx route | Not started |
| H5c | Share cards (1200 × 627) | Not started |
| Deploy | §10 deploy order | Not started |

Runs alongside P1b: it touches the pipeline build and the API, not the models.

## 9. Decisions (owner, 2026-10-26)

1. Name: **Head to Head** at `/cricket/h2h/`, with page titles in search words (matchup / comparison / head to head).
2. Launch: **~150 indexed pages**: ~90 matchups, ~30 player comparisons, ~30 country head-to-heads.
3. Both player and country level (country pages reuse the existing team head-to-head data).
4. **Internationals only** at launch.
5. **Start now**, in parallel with P1b.

## 10. Working notes (for picking this up later)

**Where things are**

| What | Where |
|---|---|
| Matchup marts (H1) | `cricstat/sql/serving_schema.sql` (`matchups`, `matchup_outs`), `cricstat-pipeline/db-logic/marts/marts.sql` (section "Batter v bowler"), checks `matchup_bat_diff` / `matchup_outs_diff` in `serving_store.measure` + `build_checks.py`, tests `tests/serving/test_matchups.py` |
| Golden list (H2) | `cricstat/tools/h2h_golden.py` → `docs/validation/h2h-golden.csv` (re-runs keep the owner's columns; uses the mart when present, else the same rules on deliveries) |
| API (H3) | `cricstat-api/db-logic/repository/h2h_repo.py`, `application-logic/services/h2h_service.py`, routes in `presentation-logic/api/app.py`, tests `tests/test_h2h.py`; documented in `docs/F5-api-contract.md` |
| Pairs (H5a) | `docs/h2h/picked.csv` (owner's list: kind, a, b, note; slugs, never names) → `python3 cricstat/tools/h2h_pairs.py [--db …]` → `docs/h2h/pairs.csv` (the indexed set; prints `NOT USED` lines for picks that fail a rule, exit 1). Rules and quotas are constants at the top of the tool. Re-run, then `gen_pages.py`, after editing picks |
| Pages (H4) | `tools/staging/web/assets/h2h.js` + CSS at the end of `cricstat.css`; shell from `tools/gen_pages.py` (`H2H`, `H2H_POPULAR`, nav item, V=124); "Compare with…" in `players.js`, "⚔ Head to head" in `countries.js`. `tools/staging/` is gitignored, so the tracked copy is `tools/staging-snapshot/h2h/` (README + `changes-to-live-files.diff`). Refresh the snapshot after every staging edit. |

**Private preview (what the owner reviews)**

1. Preview DB (already built at `cricstat/data/h2h-preview/`, gitignored): a copy of the live `cricstat.sqlite`
   with the H1 tables added by running the schema block and the marts.sql matchup section, plus a symlink to the
   live `forecast.sqlite`.
2. API on 8048, from `cricstat-api/`:
   `CRICSTAT_HOME=…/cricstat/data/h2h-preview CRICSTAT_WEB_DIR=…/cricstat/tools/staging/web python3 -m uvicorn presentation_logic.api.main:app --host 127.0.0.1 --port 8048`
3. Site on 8090, from the repo root: `CRICSTAT_API=http://127.0.0.1:8048 python3 cricstat/tools/web_preview.py`
   (it serves `/cricket/h2h/<a>-vs-<b>/` from the `h2h/index.html` shell).
4. The owner opens `http://localhost:8090/cricket/h2h/` through VS Code port forwarding.
5. **Both servers stop when the Claude Code session ends.** Restart them when the page "keeps spinning".
6. Headless checks: jsdom in the scratchpad (`npm install jsdom@24`, set `window.fetch` in `beforeParse`); canvas
   errors on the Players page are jsdom limits, not bugs.

**URLs:** a pair is `/cricket/h2h/<slugA>-vs-<slugB>/` with the slugs in alphabetical order. Player slugs end in the
8-hex Cricsheet id (`v-kohli-ba607b88`), team slugs in `-men` / `-women`; `h2h.js` tells them apart by that.
`?f=TEST` keeps the format tab; `/cricket/h2h/?a=<slug>` pre-fills the picker.

**Deploy order (after the owner approves the preview and the PR)**

1. Merge `feat/cricstat-h2h` to `main` with `--no-ff` and push. The owner approves the **pipeline** and **API**
   publishes on GitHub.
2. `CRICSTAT_SERVICES=cricstat-pipeline DOCKER="sudo -n docker" sh deployment/cricstat/cd-pull.sh`, then a
   **full** build (the schema changed, so rules_sha forces it; ~12 min; the live site keeps the old DB until the
   swap).
3. `CRICSTAT_SERVICES=cricstat-api … cd-pull.sh`. The API answers 503 on `/v1/h2h/*` until the marts exist, so
   this order is safe either way.
4. Nginx: add the `/cricket/h2h/<pair>/` route (H5), test it in the live container, then reload.
5. Copy the changed staging files into `cricstat/web/` (assets first), delete `tools/staging-snapshot/h2h/`, and
   merge `main` into every open branch (the branch-switch trap in CLAUDE.md).

