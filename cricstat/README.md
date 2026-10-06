# cricstat

Cricket statistics, a 2027 ODI World Cup winner predictor, and an LLM "Ask the Analyst" agent, built end to end
on open ball-by-ball data. cricstat is the flagship cross-domain project of [pandyaHomeLab](../README.md) and will
be served at `pandyahomelab.com/cricket/`.

**Status:** in development. The foundation sprint (F1–F6, F9) finished on 2026-10-05. The Cricsheet pipeline runs daily on the
NAS with CI/CD (GitHub Actions → GHCR → pull-based deploy). Next: P0, the serving database, the stats API and the first live pages.

| Path | What it is |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Decisions, plan and roadmap (the project's source of truth) |
| [docs/F1-product-brief.md](docs/F1-product-brief.md) … [F9](docs/F9-cicd-automation.md) | Brief, data model (F3), metric rules (F4), API contract (F5), engineering setup (F6), CI/CD (F9) |
| [sql/](sql/) | Serving-DB schema, reference rules, semantic views |
| [docs/wireframes/](docs/wireframes/) | F2 wireframe sources (eight pages) |
| [docs/llm-strategy-research-2026-10-05.md](docs/llm-strategy-research-2026-10-05.md) | Research behind the LLM strategy |
| [cricstat-pipeline/](cricstat-pipeline/) | Scheduled Cricsheet ingester (raw layer) |

## Data and attribution

Match data from Cricsheet (cricsheet.org), used under the Open Data Commons Attribution License 1.0.
Player metadata from Wikidata (CC0). cricstat is an independent project and is not affiliated with or endorsed by
Cricsheet, the ICC or any cricket board.
