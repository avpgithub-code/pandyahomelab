# Stage 2 Closure Summary

**Date:** May 2026
**Status:** Stage 2 architectural deliberation complete
**Next stage:** Stage 2 Implementation (Transition Plan Phase 3 onward)

---

## What Stage 2 produced

After many sessions of architectural deliberation, Stage 2 of pandyaHomeLab is now fully specified in writing. The artifacts below are the durable outputs — every architectural decision the platform stands on is recorded, with reasoning, alternatives considered, and trade-offs accepted.

### Six Accepted ADRs

| ADR | Title | What it locks |
|---|---|---|
| **007** | Repository layout | 3-tier multi-service shape: `platform/`, `site/`, `services/`, `compose/`, `docs/`. Network→folder 1:1; URL hierarchy→folder 1:1. Platform-agnostic. |
| **008** | Repository packaging | Single Git monorepo at `pandyahomelab`. Polyrepo and hybrid rejected because they fight the working model. |
| **009** | Runtime filesystem and permissions | Repo + sibling data folders under `/volume1/pandya-homelab/`. Owned by operator + `homelab` group, 750 perms. Containers run as operator's UID. Source mounts read-only; data mounts read-write per-container. |
| **010** | Secrets management | Two `.env` files (one per stack), identical variable names, manual generation, password-manager-canonical, .env files chmod 600 and excluded from Git AND backup. |
| **011** | Per-service conventions | Twelve decisions across runtime contract (logging, request_id, errors, HTTP), implementation (framework-agnostic, minimum layout mandate, Dockerfile pattern, smoke tests), and details (cookie naming, /health endpoint, env-var-only config). |
| **012** | Authentication strategy | Operational UIs (MLflow, Grafana, MinIO console) LAN-only. HTTP Basic Auth at Nginx as the available mechanism for any future authenticated resource. Per-demo auth pattern documented but deferred. |

### Four Working Memos

| Memo | What it captures |
|---|---|
| **Consolidation memo** | Reasoning that didn't fit any single ADR — two-axis "agnostic" framing, Pattern A/B for multi-container demos, framework-fit guidance per domain, known constraints, deferred questions. |
| **Security map** | Index of seven security concerns with status (Locked/Resolved/Partial/Deferred). After ADRs 009/010/012, three concerns moved from Queued to Resolved. |
| **Transition plan** | Eight phases for the deliberation→implementation handoff. Phase 5 (Git initialization) is now concrete with monorepo decision. |
| **Working environment** | Operational reference: Mode B-prime (VS Code Remote-SSH), B1 source tree pattern, two stacks (`dev-nas` + `prod-nas`), promotion mechanism, AWS deployment model (minimal serving layer, Nginx-on-EC2, Terraform-as-recovery), DNS structure, apex landing page Pattern Z, demo selection per environment. |

### Two Architecture Diagrams (preview status)

| Diagram | What it shows |
|---|---|
| **Cross-platform deployment view** | Visitor → apex landing → Pattern Z toggle → NAS (full state, MLflow/MinIO/Postgres/Grafana) OR AWS (minimal serving, Nginx + demos only). |
| **Source-flow view** | GitHub upstream → NAS source tree (B1) → dev-nas (any branch, eager) and prod-nas (main only, explicit) → ECR → AWS EC2. Laptop clone shown as contingency. |

Both diagrams are marked as previews; will be redrawn for portfolio polish after implementation.

---

## What Stage 2 deliberately did NOT lock

Decisions intentionally deferred to later stages or future ADRs:

- **TLS automation** — deferred to Stage 5
- **CI/CD specifics** — deferred to Stage 3 (the next architectural horizon)
- **AWS Secrets Manager integration** — deferred to Stage 4
- **Per-demo database schemas vs separate databases** — premature; future ADR when first stateful demo is on the horizon
- **OAuth, MFA, audit logging, rate limiting** — deferred per ADR-012; not relevant at single-operator scope
- **Authorization (multi-user)** — deferred until a second user is added
- **Nginx tooling specifics for AWS** — Stage 4 concern

These omissions are intentional. Each is recorded in the relevant ADR or memo with the trigger that would surface them.

---

## Key architectural principles locked

These principles cut across multiple ADRs and define the platform's character:

1. **Two-axis "agnostic"** — deployment-platform-agnostic (NAS/AWS/laptop) AND framework-agnostic (Flask/FastAPI/Streamlit/Reflex/Gradio). Both required; both distinct.

2. **AWS as minimal serving layer** — NAS is canonical with full state; AWS deploys subset (Nginx + demos only). ADR-002's mirror principle holds for the parts that exist on both platforms.

3. **Terraform-as-recovery posture** — AWS reliability via fast rebuild (`terraform apply`), not via preventing failure. Requires Terraform code that is current, tested, with remote backend state.

4. **Live site is the portfolio** — `pandyahomelab.com` is the audience-facing artifact. Individual demo repos are NOT part of portfolio strategy. The story is "I built a platform that hosts these demos," not "I built these demos."

5. **B1 source tree pattern** — One source tree on NAS, shared by both dev-nas and prod-nas stacks. Enabled by monorepo. Enforced by filesystem layout.

6. **Mode B-prime working environment** — Development happens via VS Code Remote-SSH directly on the NAS. No "works on my machine" because there is no separate "my machine" for development.

7. **Contract over framework** — The platform mandates a runtime contract (logs, errors, request_id, HTTP behavior); the framework that satisfies the contract is per-demo choice.

---

## What changed in the final housekeeping turn

For the record, three small but important corrections were made:

1. **ADR-007 status corrected** — was found at "Proposed" despite earlier verbal acceptance; flipped to Accepted in outputs
2. **ADR-008 status corrected** — drafted but never formally accepted; flipped to Accepted in outputs
3. **ADR-009 status corrected** — same situation as ADR-007; flipped to Accepted in outputs
4. **Security Map updated** — concerns #3, #5, #6 marked Resolved with summaries
5. **Transition Plan Phase 5 made concrete** — Git initialization steps now specify exact commands

These corrections matter operationally: the ADR documents you file should match the locked state. Re-download ADR-007 and ADR-009 from outputs if your locally-filed versions still show "Proposed."

---

## Next stage horizon

**Stage 2 Implementation begins now.** The Transition Plan (Phase 3 onward) is the operational handoff:

- **Phase 3** — Scaffold platform repo at `/volume1/pandya-homelab/` per ADR-007
- **Phase 4** — Seed ADRs and memos into `docs/adr/`
- **Phase 5** — Initialize Git, push to GitHub, tag `stage-2-baseline`
- **Phase 6** — Archive deliberation workspace (`/volume1/pandyaHomeLab-Roadmap/` → `pandyaHomeLab-Roadmap-archive/`)
- **Phase 7** — Build platform services in order: proxy → data → mlops → site
- **Phase 8** — First demo: `iris-knn` at `/ml/classification/iris-knn`

**Stage 2 definition of done:** `iris-knn` reachable at `pandyahomelab.com/ml/classification/iris-knn` through TLS, with predictions tracked in MLflow, artifacts in MinIO, and logs flowing through Loki.

After Stage 2 implementation completes, **Stage 3 (CI/CD) becomes the next architectural deliberation horizon.** The deliberation arc resumes there.

---

## Operational reference for next session

If a future Claude session continues this work:

- **Read this closure summary first** to understand the current milestone
- **The six ADRs are the locked architecture** — do not re-deliberate without explicit reason
- **The four memos are operational guidance** — living documents, can be updated as implementation reveals corrections
- **The two diagrams are previews** — will be redrawn for portfolio polish; don't treat as final
- **Stage 2 implementation is the active work** — Transition Plan Phase 3 onward is the active backlog

The deliberation is done. The building begins.
