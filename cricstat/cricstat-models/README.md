# cricstat-models

The ODI World Cup 2027 predictor (P1). Plan: `../docs/P1-predictor-plan.md`; Afghanistan design:
`../docs/P1-afghanistan-audit.md`.

**P1.1 (this step): the data layer.** Ratings (P1.2), the tournament simulator (P1.3) and the
scheduled job (P1.4) build on it.

## What's here
| Path | What |
|---|---|
| `db-logic/repository/serving_reader.py` | Read-only serving DB access by **stable ids only** (match_id, team name + gender + type) |
| `db-logic/sources/` | MediaWiki client (1 req/s, contact User-Agent, cache) and parsers for season pages and match boxes |
| `application-logic/services/data_service.py` | The rating input: Cricsheet men's ODIs + the reviewed Afghanistan supplement, one home/away rule |
| `application-logic/services/supplement_service.py` | Draft the supplement from Wikipedia; weekly check that only **proposes** changes |
| `application-logic/quality/supplement_checks.py` | The integrity checks every load runs (SQLite can't enforce FKs across files) |
| `application-logic/services/tournament_service.py` | Draft and validate tournament configs |
| `supplement/` | `afg_odi_results.csv` (193 rows, 188 played), `afg_totals.csv` (checksum), `reviews.csv`, crosswalks `team_codes.csv`, `supplement_venues.csv` |
| `tournaments/` | `wc2019`, `wc2023` (48 fixtures + results each), `wc2027` (57 fixtures, assumptions listed), `wcq2027` (field TBC) |

## How the Afghanistan supplement is built
1. **Rows:** Wikipedia's "International cricket in <season>" pages list every ODI with its official
   number and the ESPNcricinfo scorecard id (Cricsheet's id space). Rows with Afghanistan are kept.
2. **Second source:** each row is compared with the match box in its series or tournament article
   (independently edited). Agreeing rows are `confirmed`; the rest need a reviewer to mark them
   `accepted` with a note.
3. **Checksum:** the team article's "ODI record versus other nations" table, per opponent and in total.
4. **Ids:** a row's scorecard id must not belong to any Cricsheet match (Afghan matches can't be
   there). Wikipedia sometimes links the wrong scorecard (about 0.3% of rows when checked against
   1,985 Cricsheet matches), so a clashing id falls back to `odi-<number>`.
5. **Reviews:** `supplement/reviews.csv` holds reviewer decisions (accept a row, or correct one
   field); every draft applies them, so a review is done once.
6. **Updates:** `supplement-check` (weekly) re-drafts into a temp folder and reports a diff. It never
   edits the committed files: a change goes live only through a reviewed commit and a publish.

## Commands
```
python3 -m presentation_logic.cli data-check          # exit 2 if any check fails
python3 -m presentation_logic.cli supplement-check    # weekly proposal (JSON)
python3 -m presentation_logic.cli supplement-draft --out DIR
python3 -m presentation_logic.cli tournament-draft wc2027
python3 -m pytest tests -q && python3 -m ruff check .
```
Exit codes: 0 ok, 1 error, 2 data check failed (nothing downstream runs; the old forecast stays).

## Reloads
The supplement is reviewed data in git, not in raw.sqlite or cricstat.sqlite. Daily, weekly and
monthly pipeline runs, a full rebuild, or deleting the serving DB never touch it, and nothing has to be
scraped again. Only a new Afghanistan ODI needs work: the weekly check proposes it, and you review it.
