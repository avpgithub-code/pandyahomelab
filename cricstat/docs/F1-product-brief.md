# F1 — cricstat product brief

Status: **approved** (2026-10-05) · Owner: Archit Pandya · Lives at `pandyahomelab.com/cricket/`

## 1. Why this exists
cricstat is the flagship project on pandyaHomeLab. The existing demos each show one technique.
cricstat shows **one product built end to end**: a data pipeline, ML/DL models, an LLM agent,
evaluation, CI/CD and operations. The main aim is to show recruiters and hiring managers how I
engineer real systems. Cricket fans are a second audience and keep the product honest. If fans
wouldn't use it, it isn't a real product.

## 2. Audiences and what each needs
| Audience | Visit | Needs to come away with |
|---|---|---|
| Recruiter / hiring manager | 30 seconds on the homepage banner + hub | "End-to-end ML + LLM engineer, ships real things." Clear skill keywords, live and working |
| Technical reviewer | 3–10 min on Methodology & Evals, GitHub, ADRs | Sound methods, published scores, honest limitations, clean architecture |
| Cricket fan | Search → player or country page; World Cup predictor | Correct stats, fast pages, a predictor worth checking back on |

## 3. Products (v1 scope)
| Product | v1 includes | Deferred |
|---|---|---|
| **Players** | Search with name resolution ("did you mean"). Profile: identity (country, DOB, birthplace via Wikidata), career batting, bowling and fielding by format, year-by-year trend, T20 phase splits, top opponents and venues | Photos (each needs per-image licence credit), pace/spin role badge (P1 classifier), comparisons |
| **Countries** | Team record by format and year, head-to-head grid, top players, home/away split | Venue deep-dives |
| **WC 2027 Predictor** | Each team's chances to reach the semis/final and to win, a ratings-history chart, a "last updated" stamp, methodology + backtest scores (2019, 2023), disclosure of the Afghanistan data gap, a not-betting-advice note | Live ball-by-ball odds (needs a live API), match-by-match fixture view until the fixtures are published |
| **Ask the Analyst** | Chat over the stats with an "Interpreted as" line, provenance (tool/SQL, filters, formula, data date), clarification questions, honest refusals for out-of-scope questions | Match-report generation, model switcher (Claude vs open models) |
| **Methodology & Evals** | Metric definitions, architecture diagram, data refresh status, predictor backtest, agent eval scores vs the naive baseline, model comparison table | Fine-tuned model card (P6) |
| **Data & Licences** | Cricsheet ODC-BY attribution, Wikidata credit, open-model licences, privacy summary, disclaimers, a contact for corrections | — |

Releases (see the roadmap in CLAUDE.md): Players + Countries **Dec 2026** → Predictor beta **Q1 2027** →
Ask the Analyst **Q2 2027** → live tracker **Oct–Nov 2027**.

## 4. Success measures
| Area | Target |
|---|---|
| **Stats correctness** | A validation set of ~50 players and ~10 teams matches published reference figures (checked manually) within an agreed tolerance. Any differences are explained, e.g. by Cricsheet coverage gaps |
| **Predictor quality** | Backtest Brier score / log-loss better than a simple ranking-based baseline. Calibration chart published |
| **Agent quality** | Execution accuracy on the test set (~150 single-turn + ~30 multi-turn) clearly above the naive text-to-SQL baseline. Refusal and clarification cases handled |
| **Performance** | Stats pages p95 < 1 s. First chat token < 3 s |
| **Cost** | Within the API budget (prepaid, $1–2/day app cap) |
| **Reliability** | Daily refresh succeeds or alerts. Deployments roll back automatically on a failed smoke test |
| **Reach** | Real visitors to `/cricket/` pages, measured with the site's existing first-party beacon analytics |

## 5. Principles
- **Correct before clever.** Every number comes from one stats API with tested formulas.
- **Show your work.** Provenance on answers, published evals, and stated limitations.
- **Legally clean.** Cricsheet, Wikidata and Wikipedia only (with attribution). No scraping of avoided sources.
- **Privacy promise kept.** No cookies, nothing loaded from third parties. Server-side processors are disclosed.
- **Fits the platform.** Monorepo, ADRs, 4-layer services, same Nginx/tunnel, CI/CD.

## 6. Non-goals (v1)
Betting or odds products · user accounts or saved chats · live ball-by-ball coverage before the World Cup ·
domestic first-class depth · full Afghanistan men's coverage (Cricsheet withholds it; disclosed) ·
native mobile app (the pages are responsive instead) · scraped commentary or images.

## 7. Constraints and risks
| Risk | Mitigation |
|---|---|
| Cricket metric conventions are subtle (not-outs, wides/no-balls, credited dismissals) | F4 metric dictionary + formula tests against reference figures |
| Afghanistan gap distorts the predictor | Disclosed manual starting rating; sensitivity shown |
| NAS capacity (no AVX, ~7 GB RAM free) | 2 always-on containers; batch jobs run and exit; no local LLM on the NAS |
| LLM cost or abuse on a public endpoint | Prepaid credits, daily cap, server-side rate limits, read-only DB, kill switch |
| Cricsheet match-file licence not explicit | Email Cricsheet (owner TODO) before publishing any dataset |
| World Cup format/fixtures may differ from assumptions | Simulator reads the format from config; verify when the ICC publishes |

## 8. Review decisions (2026-10-05)
1. **Women's cricket: included** in Players and Countries from v1. The WC 2027 predictor is men's only.
2. **Naming:** brand "cricstat", folder `cricstat/` (no rename), containers `cricstat-*`. URL **`/cricket/`** (confirmed).
3. **Formats: all** of Tests, ODIs, T20Is + major leagues in v1.
