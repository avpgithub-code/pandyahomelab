# Stage 2 Consolidation Memo — April 2026

**Status:** Working memo (living document)
**Stage:** 2 (Synology Implementation)
**Purpose:** Captures architectural reasoning and conventions that emerged during Stage 2 deliberation but are not (yet) formalized in ADRs.

## Why this document exists

Stage 2 deliberation has been spread across multiple working sessions. ADR-007 was locked successfully, but the path to it surfaced several pieces of substantive reasoning that don't fit cleanly into any single ADR — vocabulary disambiguations, candidate patterns, predictive linkages, and known constraints.

This memo is the home for that reasoning. It is **not** an ADR — its contents are not immutable, and may be edited as understanding sharpens or as items graduate into formal ADRs. When an item here is absorbed into a future ADR, the entry should be marked *(absorbed into ADR-XXX)* rather than deleted, so the trail of thought stays visible.

The memo is organized by category, not chronology.

---

## 1. Vocabulary: the two-axis "agnostic" framing

The platform is **agnostic on two distinct axes**. Both have been called "platform-agnostic" in casual conversation, which has caused confusion. Going forward, the two axes are named separately:

- **Deployment-platform-agnostic.** The platform runs identically on Synology NAS, AWS, or a developer laptop. Locked by ADR-002 (Synology/AWS mirror principle) and reinforced by ADR-007 (repository layout makes no reference to Synology, AWS, or any specific runtime).
- **Framework-agnostic.** Each demo under `services/<domain>/<technique>/<dataset>-<algorithm>/` chooses its own application framework (FastAPI, Flask, Streamlit, Gradio, Reflex, or any other). Locked in passing by ADR-007's "per-demo internals are out of scope" paragraph; will be elaborated in ADR-011.

Neither axis subsumes the other. A demo can be framework-agnostic but deployment-platform-specific (e.g., uses an AWS-only library), or framework-specific but deployment-platform-agnostic (e.g., a Reflex-only demo that runs anywhere). pandyaHomeLab requires both axes to hold.

When writing future ADRs, prefer the specific term over the bare word "agnostic."

---

## 2. Multi-container demo patterns

ADR-007 hand-waves at "single-container vs frontend+API split" without documenting concrete patterns. Two patterns have been worked out informally and are recorded here for reference.

### Pattern A — Single container, Python serves compiled frontend

The demo folder contains both backend and frontend source. The build step compiles the frontend (e.g., React) into static assets, and the Python container serves both the API and the static assets at the demo's mount point.

```
services/ml/classification/iris-knn/
├── app/
│   ├── main.py              # FastAPI/Flask, serves API + static
│   ├── frontend/            # React/Vue source
│   └── static/              # Compiled output (built at image creation)
├── Dockerfile               # Multi-stage: build frontend, copy into Python image
├── requirements.txt
└── README.md
```

Properties: one container, one port, one Nginx route. Same-origin everything. Simplest deployment, cleanest fit with ADR-005's path-based routing.

Suitable for: demos with a modest UI that doesn't need an independent frontend dev loop.

### Pattern B — Two sibling containers, frontend + API split

The demo folder contains two subdirectories, each producing its own container. The frontend container serves the UI; the API container serves predictions. Both share the demo's URL prefix but listen on different ports internally.

```
services/ml/classification/iris-knn/
├── frontend/
│   ├── app/                 # React/Reflex source
│   ├── Dockerfile           # Builds and serves frontend
│   └── package.json
├── api/
│   ├── app/                 # FastAPI/Flask source
│   ├── Dockerfile           # Builds API
│   └── requirements.txt
└── README.md
```

Properties: two containers, two ports, two Nginx routes (or one route with a sub-prefix split). Independent dev loops for frontend and API.

Suitable for: demos where the frontend is sophisticated enough to warrant its own dev workflow, or where the team wants to demonstrate full-stack separation.

### Pattern B — predictive linkage to ADR-005

Pattern B is **the supersession trigger named in ADR-005**. ADR-005 (path-based routing) defers the subdomain-hybrid hybrid model and lists three triggers that would fire it; the second trigger is *"a frontend application is added that is not co-located with the API."* Pattern B is exactly that scenario.

Implication: if pandyaHomeLab adopts Pattern B for any demo, ADR-005 should be revisited at that moment. The fix may be a superseding ADR that promotes the API to its own subdomain (e.g., `api.pandyahomelab.com/ml/classification/iris-knn`), or a per-demo Nginx workaround that keeps everything path-based. Either way, the trigger is *predictable* and shouldn't be discovered painfully.

---

## 3. Framework-fit guidance for ML demos

ADR-007 is silent on framework recommendations, by design. ADR-011 will not mandate a default framework, also by design. But the working consensus from Stage 2 deliberation is worth recording, because new demo authors (including future-self) will benefit from non-binding guidance.

| Domain | Recommended default | Why |
|---|---|---|
| ML (classical) | **FastAPI** for first demo (validates layout + Nginx prefix); **Streamlit** or **Gradio** for subsequent demos with built-in UIs | Forces clean REST contract first, then leverages UI-bundled frameworks for variety |
| DL (vision, audio) | **Gradio** | Multimedia I/O widgets are one-liners; image-upload-and-display in FastAPI+HTML is significantly more code |
| NLP | **Gradio** for short-lived inference; **Streamlit** for richer exploration UIs; **FastAPI** for headless API services | Choice depends on whether the demo is "type and predict" or "explore the model" |
| Agentic AI | **Gradio** (chatbot UI) for conversational; **Streamlit** for agent dashboards with intermediate-state visibility; **FastAPI** for headless agent endpoints | Most diverse UI needs; Gradio's built-in chat UI is the fastest path |

These are recommendations, not constraints. ADR-011 will codify the *contract* every demo must honor; framework choice within the contract remains the demo author's decision.

---

## 4. Known constraints and gotchas

Operational knowledge that has surfaced during deliberation. Not architectural decisions; just things that will bite during implementation if forgotten.

**Deep URL prefix friction.** ADR-003 mounts demos at deep paths (`/ml/classification/iris-knn/`). FastAPI handles this gracefully via `root_path` or `X-Forwarded-Prefix`. Streamlit historically requires extra Nginx config for base paths; Reflex is opinionated about routing and may resist. Per-demo Nginx route blocks may need framework-specific tuning. This is implementation detail, not a layout problem.

**Cookie collisions across demos.** ADR-005 already flagged this. Two demos using the same cookie name (e.g., a default `session` cookie) will collide because all demos share the `pandyahomelab.com` origin. Mitigation: ADR-011 should require per-container cookie name prefixes (e.g., `iris-knn_session` rather than `session`).

**WebSocket-using demos need extra Nginx config.** Streamlit and Reflex use WebSockets internally. Nginx route blocks for these demos need `proxy_http_version 1.1` and `Upgrade`/`Connection` headers, otherwise the demo will silently degrade or fail to connect.

**GPU sharing across demos.** No GPU demos exist yet, but when they arrive, multiple demos competing for the same GPU is an architectural concern (resource limits, scheduling, preemption) that has not been addressed by any ADR. A future ADR will be needed once a second GPU demo is on the roadmap; pre-deciding in the abstract is premature.

**Per-demo database schemas vs per-demo databases.** ADR-001 places Postgres in `data-network` shared across demos. Whether each demo gets its own *schema* in the shared Postgres, or its own *database*, or shares with others, is unaddressed. Likely an ADR-011 sub-concern but flagged here so it doesn't get lost.

**The "first stable demo as template" pattern.** ADR-007's negative consequences mention "treating the first stable demo's Dockerfile as a template." This is implicitly the same pattern proposed for Python/JS layout in ADR-011. The general convention — *build one, then template* — should be stated explicitly in ADR-011 rather than scattered across ADRs.

---

## 5. Items deferred to future ADRs

Items that have been raised but not formalized, with their natural ADR home:

| Item | Natural home | Status |
|---|---|---|
| Per-container cookie name prefixes | ADR-011 (per-service conventions) | Mentioned in ADR-005 |
| make/wrapper-script for split compose commands | Stage 2 runbook (operational) | Mentioned in ADR-007 negatives |
| TLS automation approach | Stage 5 ADR | Mentioned in ADR-006 negatives |
| Nginx config CI validation | Stage 4 ADR (CI/CD) | Mentioned in ADR-006 negatives |
| Logging contract (structured logs, request_id, mandatory fields) | ADR-011 (per-service conventions, expanded scope) | Discussed Stage 2 |
| Exception handling contract (global handler, error response shape) | ADR-011 (per-service conventions, expanded scope) | Discussed Stage 2 |
| Loki as platform log aggregator | Stage 2 implementation (no ADR needed; absorbed by ADR-007's mlops folder convention) | Discussed Stage 2 |
| Authentication strategy | ADR-012 (proposed, queued) | Discussed Stage 2 |
| Filesystem permissions detail | ADR-009 (expanded scope) | Discussed Stage 2 |

---

## 6. Open questions not yet decided

Questions that have been raised but where no decision has been reached. None of these block ADR-008.

- Should ADR-011 fix a default framework, or stay agnostic with conventions only? *Working position: stay agnostic. Recording a default re-creates the FastAPI bias just removed from ADR-007.*
- Should GPU-bound demos get their own ADR before the second GPU demo lands? *Working position: defer until at least one GPU demo has surfaced real constraints.*
- Should a "Stage 2 plan" doc exist as a peer to the ADRs? *Working position: ADR-007's implementation-reference list is currently sufficient; promote to a separate plan doc only if Stage 2 work spans more than a quarter.*
- Should framework-agnosticism be promoted to its own short ADR? *Working position: stays embedded in ADR-007 unless it gets referenced often enough by future ADRs to warrant promotion.*

---

## How to maintain this memo

This memo is **living**. It is updated as Stage 2 deliberation continues. The discipline is:

- New informal reasoning that doesn't yet belong in an ADR is added here.
- When an item graduates into a formal ADR, the entry stays but is marked *(absorbed into ADR-XXX)*, not deleted.
- When Stage 2 locks, this memo is reviewed; surviving items either become Stage 3 inputs or are formally retired.

When this memo and an ADR conflict, the ADR wins. This memo is supplementary, not authoritative.
