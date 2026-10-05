# cricstat — LLM strategy research (2026-10-05)

Status: **proposal, not yet decided**. Approved decisions move into CLAUDE.md.

## Hardware constraints (checked)
- NAS: Intel Celeron J3455 (4 cores, 1.5 GHz, **no AVX**), 16 GB RAM, ~7 GB available,
  22 containers already running. No GPU.
- Host Python 3.8.15 (EOL). LangGraph/LangChain need Python >= 3.10, so the LLM app runs in Docker
  (python:3.12-slim).
- Consequences: no local LLM serving; local embedding models only for small corpora, and
  ONNX/AVX compatibility must be tested first; no heavy self-hosted stacks (Langfuse v3 wants 16 GiB).

## Key findings
### Text-to-SQL
- The BIRD leaderboard (SQLite) top is ~83% execution accuracy; humans score ~93%. Top systems use
  value retrieval, schema linking, multiple candidates, execution-guided repair and a selector.
- **CricBench** (arXiv 2512.21877, Dec 2025, built on Cricsheet SQLite): execution success >95%,
  but answer correctness <29% (Claude Sonnet 4 got 23.8% on IPL). Main failures are cricket metric
  formulas (averages, strike rate, economy, credited dismissals) and entity resolution.
  So naive text-to-SQL on cricket is bad. Measuring and beating that baseline is the story.
- Semantic layer and typed tools beat free SQL. dbt measured 98% vs 90%; Cube measured +17 to +23
  points. Both are vendor benchmarks, so treat them as directional. Free SQL fails silently and
  plausibly; typed tools fail explicitly.
- Multi-turn ("contextual") queries are still hard. On BIRD-Interact, frontier models
  score far lower on follow-ups. A practical pattern: **structured conversation state**
  (resolved player IDs, format, date range, last intent), which the model updates with a delta each turn.
  Show "Interpreted as: …" in the UI.
- Entity resolution: Cricsheet `people.csv` + `names.csv` → alias table → fuzzy match, ranked by
  career volume and recency → ask a clarifying question when ambiguous. Tools take player IDs, never raw names.

### Frameworks
- LangGraph 1.2.x (1.0 since Oct 2025, MIT, Py >= 3.10) supports StateGraph, checkpointers
  (`langgraph-checkpoint-sqlite`, fine at demo scale), streaming and human-in-the-loop.
- LangChain 1.4.x now builds on LangGraph (`create_agent` + middleware); legacy chains have moved to
  `langchain-classic`. `langchain-anthropic` 1.7.x supports tool calling and prompt caching middleware.
- LangChain `SQLDatabaseToolkit` is documented as "demonstration only, not secure". Write our own SQL tool.
- Job signal (a single job board, Apr 2026): LangChain/LangGraph appear in ~40% of agentic job listings,
  LlamaIndex in ~14%, Pydantic AI in ~2%.
- Skip: Vanna (repo archived Mar 2026), Claude Agent SDK (wrong shape for a multi-user chat app),
  CrewAI. DSPy GEPA could be a later prompt-optimisation add-on.

### Observability and evals
- **Arize Phoenix**: one container on SQLite, OpenTelemetry-native, with evals and experiments. Best fit for the NAS.
  Self-hosted Langfuse v3 is too heavy. LangSmith self-hosting is Enterprise-only, though its free cloud tier works for development.
- Evals: golden set scored on **execution/result-set accuracy** (not SQL string matching), plus refusal and
  clarification cases. Run with pytest or promptfoo in CI and log results to Phoenix experiments.

### RAG / contextual retrieval
- Anthropic Contextual Retrieval: contextual embeddings + contextual BM25 + rerank cuts retrieval
  failures by 67%. It only makes sense for **free-text** data. Stats belong in SQL and tools.
- Licences: Wikidata is CC0 (fine). Wikipedia is CC BY-SA 4.0 (fine with attribution and share-alike).
  **MCC Laws of Cricket: all rights reserved, so do not index them without permission.**
  ICC playing conditions are unclear, so avoid them.
- If we build RAG: sqlite-vec + SQLite FTS5 (BM25) + bge-small (local) or Voyage (200M free tokens),
  compared against a long-context + prompt-cache baseline.

### Match reports (data-to-text)
- JSON fact sheet from the DB → LLM report → atomic claim extraction → **deterministic SQL check of
  every numeric or entity claim** → LLM/MiniCheck-style judge for the rest → "verified claims" badge.
  Generate offline with the Batch API (50% off).

### Cost and guardrails
- Prices still to check on the pricing page. The research reported Haiku 4.5 at $1/$5 and
  Sonnet 5.5 at $2/$10 per million tokens; the Sonnet figure is unverified.
- Estimate: $10–50/month at 50–200 questions/day. Agent loops multiply the calls per question.
- Guardrails:
  - a dedicated Console workspace with a monthly limit
  - **an in-app daily token ledger** (Console limits are monthly only)
  - per-IP rate limits and Cloudflare Turnstile
  - input length and turn caps
  - read-only SQLite (`mode=ro`, `query_only`, `set_authorizer`, progress-handler timeout, SELECT-only
    parsed with sqlglot, LIMIT wrapper)
  - tool output treated as data
  - a kill-switch env var

## Proposed phased strategy
| Phase | Deliverable | Skill shown |
|---|---|---|
| P0 | Ingestion → SQLite; Register + Wikidata players; derived stats with cricket-correct formulas, checked against known career figures; **semantic layer** (views + column descriptions) | Data engineering |
| P1 | Win-probability model (MLflow, like the other demos); optional sequence model on deliveries | ML / DL |
| P2 | Typed tool layer in plain Python: `resolve_player`, `batting_stats`, `bowling_stats` (by phase), `leaderboard`, `head_to_head`, `team_record`, `win_probability`, and a guarded `run_sql` | API / tool design |
| P3 | **Eval harness before the agent**: ~150 single-turn + ~30 multi-turn golden cases + refusals; baseline = naive text-to-SQL (the CricBench-style failure) | LLM evaluation |
| P4 | **LangGraph** agent: explicit StateGraph (rewrite/resolve → route → tool / SQL fallback → validate → answer), structured conversation state, SQLite checkpointer, Haiku first with Sonnet fallback, prompt caching, Phoenix tracing. Optional plain-SDK baseline for comparison | LLM agents |
| P5 | Public demo page: FastAPI + streaming, provenance panel (tool/SQL, filters, formula, data-as-of date), guardrails, published eval scores | Productionisation |
| P6 (extras) | Verified match reports; MCP server over the same tools; small Wikipedia RAG with a contextual-retrieval benchmark; DSPy prompt optimisation | NLP / RAG / MCP |

Added later the same day:
- **F9 CI/CD & automation.** CI on every push; pull-based CD (GHCR → NAS pull → smoke test → rollback);
  data-quality gates; MLflow promotion gates; an LLM eval gate. Details are in CLAUDE.md.
- **WC 2027 predictor** (Elo + Monte Carlo, backtested on 2019/2023) as the P1 headline.
- **Hosting:** `/cricket/` hub inside the monorepo.

Principle: tools are plain functions with no framework dependency. LangGraph, MCP and the eval harness all reuse them.
