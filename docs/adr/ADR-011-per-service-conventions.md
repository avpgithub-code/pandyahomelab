# ADR-011: Per-service conventions

**Status:** Accepted
**Date:** May 2026
**Stage:** 2 (Synology Implementation)

## Context

ADR-007 established the repository layout. ADR-008 established that the layout lives in a single monorepo. ADR-009 established the runtime filesystem and permissions. ADR-010 established secrets management. Each of these answered a structural question, but they were silent on a different category: *what does a demo itself owe the platform, and what does the platform owe each demo?*

This is the per-service contract. Every demo under `services/<domain>/<technique>/<dataset>-<algorithm>/` is an independent piece of code, written by an operator who chose their own framework. But independent does not mean unconstrained. The platform requires certain things of each demo so that observability works, errors are consistent, requests can be traced, and operations are predictable. Without those constraints, every demo would be its own special case — Loki could not parse logs uniformly, error responses would vary by framework, request tracing would be guesswork.

The challenge is to specify enough convention that the platform works coherently, but not so much that the framework-agnostic principle (ADR-007) becomes hollow. A demo author choosing Streamlit, Reflex, or FastAPI must be able to honor every part of this contract without abandoning their framework's idioms.

The contract has two halves, conceptually:

- **The runtime contract** — how the demo speaks to the platform (logs, errors, requests, HTTP behavior). Framework-agnostic; every framework can satisfy it.
- **The implementation contract** — how the demo is built (folder layout, Dockerfile pattern, tests). Framework-aware; the implementation differs per framework, but the structure is uniform.

Several constraints carry forward from earlier decisions:

- **Framework-agnostic at the demo level** (ADR-007). The contract must work across Flask, FastAPI, Streamlit, Gradio, Reflex, and frameworks not yet conceived.
- **Containers run as the operator's UID** (ADR-009). Dockerfile patterns must support this without per-NAS hardcoding.
- **All config via environment variables** (ADR-010). Demos read env vars; they do not hardcode environment-specific values.
- **Demos live at deep URL prefixes** (ADR-005). HTTP behavior must work under path-based routing.
- **Cookie collisions are foreseen** (ADR-005). Per-demo cookie naming must prevent collisions on the shared `pandyahomelab.com` origin.

This ADR resolves the contract end-to-end. It is the largest ADR in Stage 2 because the scope is the largest — twelve distinct decisions across runtime contract, implementation conventions, and detail items.

## Decision

**Every demo under `services/<domain>/<technique>/<dataset>-<algorithm>/` must honor the contract specified below. The contract is invariant across frameworks; the implementation that satisfies it is the demo author's choice.**

The contract is organized in three parts: the runtime contract (how the demo speaks), the implementation conventions (how the demo is built), and detail items (cookie naming, health checks, configuration consumption).

### Part 1 — The runtime contract

#### 1.1 Logging

Every demo emits **structured JSON logs to stdout**. No log files are written inside containers. Docker captures stdout; the platform's observability stack (Loki, when present) ingests from there.

Every log line carries the following fields:

| Field | Status | Source |
|---|---|---|
| `timestamp` | Mandatory | Auto-injected by the demo's logger |
| `level` | Mandatory | Set by the demo (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `service` | Mandatory | Read from `SERVICE_NAME` env var |
| `request_id` | Mandatory when in request context | Propagated per request (see 1.2) |
| `message` | Mandatory | Set by the demo |
| `extra` | Optional | Demo-specific structured fields |

The `extra` field is a free-form object the demo may use for any structured data relevant to the log line (prediction values, model versions, latency, etc.). The four mandatory fields ensure the platform can parse, filter, and correlate logs from any demo regardless of framework.

#### 1.2 Request ID propagation

Each incoming HTTP request carries a unique `request_id` that flows through logs, errors, and any internal tracing.

The propagation pattern: **Nginx generates the request_id as primary; demos honor it or fall back to generating their own.**

- **Nginx** sets the `X-Request-ID` header on every incoming request (using its built-in `$request_id` variable).
- **Demos** read the `X-Request-ID` header on every request. If the header is present, the demo uses that value throughout the request's logging and any error responses. If the header is absent (e.g., a request that bypassed Nginx during dev or testing), the demo generates a UUIDv4 and uses that.

This pattern makes the platform robust without requiring every demo to know whether Nginx is in front of it. The same code path works in production behind Nginx and in isolated unit-test contexts.

#### 1.3 Exception handling and error response

Every demo installs a **global last-resort exception handler** that catches any unhandled exception, logs it with full traceback (as a structured log line per 1.1), and returns a sanitized error response.

The error response shape, returned by the global handler and recommended for explicit error responses too:

```json
{
  "error": {
    "code": "MODEL_NOT_LOADED",
    "message": "The model is currently being initialized. Try again in 10 seconds.",
    "request_id": "abc-123-def-456",
    "timestamp": "2026-05-04T14:30:00Z"
  }
}
```

The four fields are mandatory:
- `code` — short uppercase string identifying the error class (the demo author's choice of vocabulary)
- `message` — human-readable description, safe to display to end users (no stack traces, no internal paths, no secrets)
- `request_id` — matches the `request_id` from the request's logs
- `timestamp` — ISO 8601 UTC

The `request_id` matching is the operationally important property: a user reporting "I got error abc-123-def-456" gives the operator a string they can grep Loki for, immediately surfacing the full request's log trail.

HTTP status codes follow conventional semantics: **4xx for client errors** (bad input, validation failure, auth required), **5xx for server errors** (model crashed, dependency unreachable, unexpected internal state). Specific code choices within these ranges are at the demo author's discretion.

#### 1.4 HTTP behavior under path-based routing

ADR-005 mounts demos at deep URL prefixes (`/ml/classification/iris-knn/`). Demos must work correctly when served at any prefix.

The platform supplies the necessary information: **Nginx sets `X-Forwarded-Prefix` on every forwarded request**, and demos can use this to construct correct absolute URLs if their framework needs them.

The contract:
- **All internal links and asset references must be relative** (`./image.png`, not `/image.png`), **OR**
- The demo honors `X-Forwarded-Prefix` and prepends the prefix to absolute paths

The mechanism is the demo author's choice. Most modern frameworks support `X-Forwarded-Prefix` natively (FastAPI's `root_path`, Flask's `APPLICATION_ROOT`). Some frameworks (Streamlit historically) work better with relative paths everywhere. Either approach satisfies the contract; the platform supplies the header on every request and the demo author picks the mechanism that fits their framework.

### Part 2 — Implementation conventions

#### 2.1 Framework choice

**Each demo chooses its own framework.** The platform records no default. The framework choice is documented in the demo's `README.md` and reflected in the demo's dependencies file.

The Stage 2 Consolidation Memo (Section 3) records non-binding guidance for which frameworks fit which domain types. That guidance is suggestion, not contract.

The framework-agnostic principle from ADR-007 is reaffirmed here: the runtime contract above is what each demo must satisfy; how it satisfies the contract is the framework's job, and any framework that can satisfy it is valid.

#### 2.2 Internal layout of `app/`

The platform mandates a **minimum** structure inside each demo's `app/` folder. Beyond the minimum, organization is the demo author's choice.

Mandatory files in every demo:

- **An entry file** — the file the Dockerfile's `CMD` runs. The name varies per framework (`main.py` for FastAPI/Flask, `streamlit_app.py` for Streamlit, etc.). The file must exist; its name is flexible.
- **A dependencies file** — `requirements.txt` for Python, `package.json` for Node, equivalent for other languages. The file lists exact (pinned) versions of all dependencies.
- **A README.md** — documents what the demo does, what framework it uses, what env vars it requires, and how to run it locally.

Beyond these three required files, internal layout is flexible. A demo may organize its source as `main.py` only, or as `main.py` + `routes/` + `models/` + `tests/`, or any other arrangement that suits its framework and complexity.

#### 2.3 Dockerfile pattern

Every demo's Dockerfile must satisfy three properties:

**Multi-stage build.** A build stage installs dependencies and (optionally) compiles assets; a runtime stage copies only what's needed to run. The runtime image excludes build tools, package caches, and intermediate files. Result: smaller images, faster ECR pushes, faster AWS pulls.

**Non-root user matching the operator UID.** Per ADR-009, containers run as the operator's UID. The Dockerfile reads the UID from the `HOST_UID` build arg (or accepts it as runtime env via compose `user:` directive), creates the user, and drops privileges before running the entry point.

A typical pattern for Python demos:

```dockerfile
# Build stage
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.12-slim
ARG HOST_UID=1026
ARG HOST_GID=100
RUN groupadd -g ${HOST_GID} app && useradd -m -u ${HOST_UID} -g app app
COPY --from=builder /root/.local /home/app/.local
COPY --chown=app:app app /app
USER app
WORKDIR /app
ENV PATH=/home/app/.local/bin:$PATH
CMD ["python", "main.py"]
```

(Adapted per framework; the pattern is the contract, not the literal lines.)

**Specific base image tag, not `latest`.** Every base image reference uses an explicit tag (`python:3.12-slim`, `node:20-alpine`, etc.). Use of `latest` is forbidden because it makes builds non-reproducible — the same Dockerfile built six months apart could produce different images.

A fourth property is recommended but not mandated: **minimum-viable base image** (prefer `slim` and `alpine` variants over full base images). This reduces image size and attack surface. It is recommendation, not enforcement, because some demos legitimately need full base images (e.g., a CUDA-based deep learning demo).

#### 2.4 Testing conventions

Tests for each demo live **inside that demo's folder**, typically under `services/<demo>/tests/`. Each demo is self-contained; its tests come along when the demo is templated, copied, or extracted.

Every demo must include **at least one smoke test** — a test that confirms the demo's container starts successfully and responds to its `/health` endpoint (see 3.2 below). The smoke test is the minimum signal that the demo is not broken; it is what CI/CD will run on every commit (Stage 3 concern).

Comprehensive coverage is encouraged but not mandated. A learning-phase demo where the model itself is the experiment may legitimately have only the smoke test. A mature demo that has been in production for months should have richer tests. The platform sets the floor (smoke test); the demo author sets the ceiling.

### Part 3 — Detail items

#### 3.1 Cookie naming

Demos that set cookies must use a **container-name-prefixed cookie name** to prevent collisions on the shared `pandyahomelab.com` origin.

The prefix follows ADR-004's container naming convention. Examples:

- `iris-knn`'s session cookie: `mlirisknn_session` (or `ml_iris_knn_session` if the framework prefers explicit separation)
- `housing-linear`'s auth token: `mlhousinglinear_auth`

The exact separator (none, underscore, or hyphen) is at the demo author's discretion, but underscore is recommended because some HTTP libraries handle cookie names with hyphens awkwardly.

Demos that set no cookies are unaffected by this rule. Most stateless inference demos will not set cookies at all.

#### 3.2 Health check endpoint

Every demo exposes a **GET `/health` endpoint** (relative to its own root) that returns 200 OK with a small JSON body indicating health.

The minimal implementation:

```json
{"status": "ok"}
```

The endpoint may include richer information at the demo author's discretion (model load status, dependency health, version info), but must minimally:
- Respond at the path `/health` relative to the demo's mount point
- Return 200 OK when the demo is healthy
- Return 503 Service Unavailable when the demo is unhealthy (e.g., model failed to load)
- Return JSON content

The health endpoint is consumed by:
- The demo's own smoke test (Part 2.4)
- Docker's `HEALTHCHECK` directive when configured
- Future Stage 4 AWS health checks if applicable
- Operators manually verifying demo state

The endpoint must not require authentication, must not perform heavy operations, and must respond quickly (under 1 second under normal conditions).

#### 3.3 Environment variable consumption

Every demo consumes its configuration via **environment variables only**. Demos do not read environment-specific config files. Demos do not hardcode values that differ between dev-nas and prod-nas.

Specifically:

- Database connection strings → from env vars (e.g., `DATABASE_URL`)
- Service endpoints (MLflow URL, MinIO endpoint) → from env vars
- Any value that differs across environments → from env vars
- Any secret value → from env vars (per ADR-010)

This contract follows the [Twelve-Factor App](https://12factor.net/config) configuration principle and mirrors the ADR-010 secrets pattern. Demos that read configuration from a YAML or JSON file inside the image violate this contract — the file would be baked at build time and could not vary across environments.

The demo's `README.md` (mandated in Part 2.2) must list every environment variable the demo reads, with placeholder values, so a future operator can construct the correct `.env` entries.

## Alternatives considered

**No contract at all (rejected).** Each demo organizes itself, logs in its own format, returns errors however it likes, and exposes whatever endpoints it wants. This is the framework-agnostic principle taken to extremes. Rejected because it makes platform observability and operational consistency impossible. Loki cannot parse logs uniformly; users see inconsistent error pages; tracing is guesswork. The framework-agnostic principle is preserved by the contract being invariant; the contract itself is non-negotiable.

**Mandate a specific framework (rejected).** Pick FastAPI (or Streamlit, or anything else) as the platform default and require every demo to use it. Rejected for reasons documented extensively in earlier conversations: it would prevent the platform from absorbing the framework variety that is part of its educational and demonstration value. The framework-agnostic principle is preserved precisely by *not* mandating a default.

**Logs to file with rotation (rejected).** Each container writes logs to a file inside its volume; a rotation policy archives them. Rejected because it violates the Twelve-Factor App "logs as event streams" principle, requires per-demo log management, complicates Loki ingestion, and produces logs only the operator can see (vs. Docker's stdout capture which is universally accessible).

**Per-demo unique error response shapes (rejected).** Allow each demo to define its own error response format. Rejected because it forces the apex landing page (and any future error-aggregating UI) to handle N different shapes. Standard four-field shape is small enough to be unburdensome and large enough to carry the diagnostic value (`request_id`).

**Single mandated entry file name (rejected).** Mandate that every demo's entry file is named `main.py` (or any single name). Rejected because Streamlit's natural entry point is `streamlit_app.py`, Reflex's is its module's `app.py`, and forcing a uniform name would be hostile to framework idioms. The entry file's existence is mandatory; its name is per-framework.

**Comprehensive testing mandated (rejected).** Require every demo to ship with a test suite covering at least the major code paths. Rejected for learning-phase demos where the model is the experiment — premature investment in testing is worse than no testing at all. Smoke test as the floor allows learning-phase demos to ship cheaply while ensuring CI/CD has something meaningful to run.

**Cookie naming as recommendation, not mandate (rejected).** Document the prefixed-cookie convention but not enforce. Rejected because cookie collisions in production are a particularly painful debugging scenario. The cost of mandating prefixed cookies is one config line per demo that uses cookies; the cost of a collision is hours of confused debugging. Mandate is cheap.

**Per-demo database design specified now (rejected).** Decide whether each demo gets its own Postgres database or its own schema in a shared Postgres. Rejected as premature — most ML inference demos don't use Postgres at runtime, and the question is hypothetical until a stateful demo is on the horizon. A future ADR can address this when concrete need arises. The Stage 2 Consolidation Memo records this as deferred.

## Consequences

**Positive:**

- Loki (and any future log aggregation) can parse logs from any demo uniformly. The mandatory four fields make demos interchangeable from an observability standpoint.
- Errors are consistent across the platform. A user reporting an error code gets the same kind of response from every demo, with the `request_id` always available for operator-side correlation.
- Request tracing across demos is mechanical, not heroic. The `request_id` flows from Nginx through every demo's logs and errors. Loki queries on a single ID surface the entire request's trail.
- Adding a new demo is mechanical because the contract is clear. Author opens the folder, satisfies the dozen items in the contract, and the demo plugs into the platform without integration work.
- The framework-agnostic principle is preserved end-to-end. Streamlit, FastAPI, Reflex, Gradio, and Flask demos can all coexist on the platform and all satisfy the contract.
- Smoke tests provide a structural safety net. Every demo, no matter how learning-phase, has at least one signal that catches "the container won't start" failures before they reach production.
- The Dockerfile pattern produces small, reproducible, secure-by-default images. Multi-stage builds minimize size; specific tags ensure reproducibility; non-root execution reduces attack surface.

**Negative (trade-offs accepted):**

- The contract has twelve items. A demo author opening their first folder must internalize all of them or miss something. Mitigated by the demo template (a future deliverable extracted from the first stable demo per the consolidation memo) which encodes the contract by example.
- Some frameworks require more wiring to satisfy the contract than others. FastAPI honors `X-Forwarded-Prefix` natively; Streamlit is more painful. Demos using awkward-fit frameworks have higher implementation cost. This is the trade-off for framework-agnosticism — the platform doesn't pick favorites, so some frameworks are more work.
- The mandatory `/health` endpoint, mandatory `request_id` propagation, and mandatory error response shape collectively require a small middleware or wiring layer in every demo. This is unavoidable given the contract; the cost is small per demo but real.
- Strict avoidance of `latest` tags means demos require periodic base-image updates. A demo built once and forgotten will eventually run on a stale base image. Mitigated by Stage 3 CI/CD which can flag stale base images automatically.
- The cookie naming mandate is enforceable only by convention, not by structural property. A demo author who forgets the prefix may not notice until a collision occurs. Mitigated by code review on first demos and template-based scaffolding for later ones.
- Some standard error patterns (e.g., FastAPI's default validation error format, which is detailed and structured but doesn't match the four-field shape) require the demo author to customize them. This is friction with framework defaults.

**Forecloses:**

- Free-form per-demo logging formats. Once this ADR is locked, all demos use the structured JSON four-field format. Unstructured prose logs are foreclosed.
- Free-form per-demo error response shapes. Same reason.
- Hardcoded environment-specific configuration in source. Foreclosed by the env-var-only rule.
- `latest` base image tags. Foreclosed by the specific-tag rule.
- Demos without smoke tests. Foreclosed by the testing mandate.
- Demos without health endpoints. Foreclosed by the health-check mandate.
- Cookie names without container prefixes. Foreclosed by the cookie naming rule.

## Implementation reference

This ADR is the contract that every demo honors. Concrete actions during implementation:

**For the first demo (the Stage 2 definition-of-done demo):**

1. Implement the demo in the chosen framework, satisfying every item in the contract above.
2. Verify each contract item explicitly:
   - Logs are JSON, four fields present
   - `X-Request-ID` honored, fallback generation works
   - Global exception handler installed, four-field error response
   - Internal links work at the deep URL prefix
   - Entry file, dependencies file, README present
   - Dockerfile is multi-stage, runs as `HOST_UID`, specific base tag
   - Smoke test exists and passes
   - Cookies (if any) prefixed with container name
   - `/health` returns 200 OK with `{"status": "ok"}`
   - All config from env vars
3. Document the demo's specific implementation choices in its README (framework, entry file name, env vars consumed).

**After the first demo is stable:**

4. Extract a per-framework template at `docs/templates/<framework>-demo/`, containing the structural skeleton with the contract pre-implemented. New demos in that framework start from the template and only add their domain-specific code.

**For each subsequent demo:**

5. Copy the appropriate framework template; replace placeholder content with the new demo's specifics; verify the contract is still satisfied (the template makes most items automatic).

**For the platform itself:**

6. Configure Nginx to set `X-Request-ID` (using `$request_id` variable) and `X-Forwarded-Prefix` on every forwarded request.
7. Configure Loki (when introduced) with parsers for the four-field JSON log structure.
8. Document the contract prominently in the repo's main README so that demo authors (including future-self) discover it before writing their first demo.

## Related ADRs

- **ADR-004** — establishes the container naming convention used by the cookie naming rule
- **ADR-005** — establishes path-based routing that the HTTP behavior contract honors; foreshadows the cookie collision issue this ADR addresses
- **ADR-006** — establishes Nginx as the reverse proxy that supplies `X-Request-ID` and `X-Forwarded-Prefix`
- **ADR-007** — establishes the framework-agnostic principle that this ADR preserves
- **ADR-009** — establishes the operator-UID convention that the Dockerfile pattern implements
- **ADR-010** — establishes the env-var secrets pattern that this ADR's configuration rule extends
- **ADR-012** (queued) — authentication strategy; auth credentials and patterns will integrate with this ADR's contract

## Related working memos

- **Stage 2 Working Environment Memo** — implementation conventions support the dev-nas/prod-nas working model and the AWS deployment pattern
- **Stage 2 Consolidation Memo** — Section 3 (framework guidance) records non-binding recommendations that complement this ADR's framework-agnostic mandate; deferred items (per-demo database schemas) noted explicitly
- **Stage 2 Security Map** — concern #7 (data security) is partially addressed by this ADR's input-validation expectations and env-var-only config rule
- **Stage 2 Transition Plan** — Phase 8 (implementation begins) is when this ADR becomes operational; the first demo is the proving ground for every contract item
