# Stage 2 → Implementation Transition Plan — April 2026

**Status:** Working memo (living document)
**Stage:** 2 (Synology Implementation) → boundary with implementation phase
**Style:** Operational runbook (numbered phases)
**Purpose:** Defines the handoff sequence between Stage 2 architectural deliberation and Stage 2 implementation. Captures *what to do, in what order*, when ADR-012 locks and architectural work is complete.

## Why this plan exists

There is a specific moment — when the last Stage 2 ADR (ADR-012, Authentication) is accepted — where two transitions happen at once:

- **Workspace transition.** ADRs and memos move from a deliberation workspace (`/volume1/pandyaHomeLab-Roadmap/`) into the platform repository (`/volume1/pandya-homelab/`).
- **Mode transition.** Conversation moves from *deliberation* (discuss, push back, draft, lock) to *implementation* (scaffold, build, verify).

Both transitions are mechanical, but they have ordering dependencies that matter. Doing them in the wrong order — for example, opening VS Code at the platform repo before seeding it with ADRs — means working with incomplete context. Doing them in the right order takes minutes and produces a clean foundation.

This memo records the right order, written down before the transition moment so it can be executed without re-derivation.

This is **not** an ADR. It is an operational runbook. ADRs lock decisions; runbooks lock procedures. Different artifacts, different lifecycles.

---

## Trigger

The plan executes when **ADR-012 is accepted**.

Concretely, that means:
- ADRs 008, 009, 010, 011, and 012 all have status `Accepted`
- Stage 2 architectural deliberation is complete
- No further "what should we decide before building" questions are open

If new architectural concerns surface after this trigger, they are handled either as Stage 2 amendments (rare) or as Stage 3 inputs (typical). The trigger is one-way — once the transition begins, deliberation pauses and implementation takes over.

---

## The eight phases

### Phase 1 — Continue deliberation *(where we are now)*

Until ADR-012 locks, all architectural artifacts live in `/volume1/pandyaHomeLab-Roadmap/Stage-2-Synology-implementation/`:
- ADRs 008 through 012, each filed as they lock
- Consolidation memo (maintained as deliberation continues)
- Security map (updated as ADRs land)
- This transition plan (updated as the trigger approaches)

Both Claude sessions (desktop chat, VS Code) work against this folder during deliberation.

### Phase 2 — Trigger event: ADR-012 locks

ADR-012 (Authentication strategy) reaches `Accepted` status. The Stage 2 ADR queue is exhausted. The transition begins.

No work in this phase — it is the *event* that fires Phase 3.

### Phase 3 — Create the platform repository

Create `/volume1/pandya-homelab/` on the NAS (the location confirmed during ADR-007 deliberation; see ADR-009 once locked for filesystem permissions detail).

Scaffold the empty folder tree per ADR-007:

```
pandya-homelab/
├── platform/
│   ├── proxy/
│   ├── data/
│   └── mlops/
├── site/
├── services/
├── compose/
├── docs/
│   ├── adr/
│   ├── stage-1/
│   └── stage-2/
└── README.md
```

This is empty scaffolding — no code yet. Folders only, with placeholder `.gitkeep` files where appropriate to preserve them under Git.

### Phase 4 — Seed the platform repository with architectural artifacts

Copy every architectural artifact from the deliberation workspace into the platform repo:

**Into `pandya-homelab/docs/adr/`:**
- ADR-001 through ADR-006 (Stage 1)
- ADR-007 through ADR-012 (Stage 2)
- The ADR README

**Into `pandya-homelab/docs/stage-1/`:**
- `pandyaHomeLab-Stage1-ADRs.docx` (bound document)
- `network-plan-v3.xlsx`
- Stage 1 infographic

**Into `pandya-homelab/docs/stage-2/`:**
- Consolidation memo
- Security map
- This transition plan
- Any Stage 2 supporting artifacts (port allocations, secrets inventories — produced during ADRs 009/010)

These are **copies**, not moves. The originals remain in `pandyaHomeLab-Roadmap/` for the moment — they are archived in Phase 7.

### Phase 5 — Initialize Git in the platform repository

Per **ADR-008 (Accepted, May 2026): single monorepo**, Phase 5 is concrete:

1. **Initialize a single Git repository** at `/volume1/pandya-homelab/`:
   ```bash
   cd /volume1/pandya-homelab
   git init
   ```

2. **Configure remote `origin`** to a GitHub repository named `pandyahomelab` (or similar — the operational naming choice is the operator's). Visibility (public from start vs. private until polished) is operational, not architectural.

3. **Verify `.gitignore` is in place** with the patterns established by ADRs 009, 010, and 012:
   ```
   data-dev-nas/
   data-prod-nas/
   .env
   .env.dev-nas
   .env.prod-nas
   .htpasswd
   .htpasswd-*
   ```

4. **Make the first commit** capturing the seeded structure (ADRs, memos, empty scaffolding per ADR-007):
   ```bash
   git add .
   git commit -m "Stage 2 architectural baseline — all ADRs accepted"
   ```

5. **Push to GitHub:**
   ```bash
   git push -u origin main
   ```

6. **Tag this commit** as the Stage 2 architectural baseline:
   ```bash
   git tag stage-2-baseline
   git push origin stage-2-baseline
   ```

This single commit is the permanent reference point: *"this is what we agreed before we started building."*

### Phase 6 — Switch the working environment to the platform repository

VS Code opens `/volume1/pandya-homelab/` as the working folder. The session sees:
- The architectural ADRs in `docs/adr/`
- The working memos in `docs/stage-2/`
- The empty scaffolding it is about to populate

Both Claude sessions (desktop chat, VS Code) reorient to this new location. Any future references to ADRs use relative paths inside the repo (e.g., `docs/adr/ADR-007-repository-layout.md`).

This is the first phase where the implementation environment matches the architecture. Before this phase, ADRs and code-to-be lived in different folders. After this phase, they live together — the configuration in which VS Code Claude is most effective for implementation work.

### Phase 7 — Archive the deliberation workspace

`/volume1/pandyaHomeLab-Roadmap/` is renamed to `/volume1/pandyaHomeLab-Roadmap-archive/` (or similar) to signal its historical status.

A short README is added inside the archive folder:

> *This folder contains the original deliberation workspace for Stage 1 and Stage 2 ADRs of pandyaHomeLab. The live versions are now in `/volume1/pandya-homelab/docs/`. This folder is read-only historical record — do not edit. Preserved as proof of authoring trail.*

The archive is **not deleted**. It is the historical record of where artifacts came from and how they were authored. ADRs are immutable, and so is the trail. Future archaeology (someone six months later asking *"how did we end up with ADR-007's specific shape?"*) is served by this archive.

### Phase 8 — Implementation begins

Per ADR-007's implementation reference, in this order:

1. `platform/proxy/` — Nginx container with TLS-ready config
2. `platform/data/` — Postgres, MinIO, Redis
3. `platform/mlops/` — MLflow first; then Prometheus, Grafana, Loki
4. `site/index.html` and one domain landing page
5. `services/ml/classification/iris-knn/` — first end-to-end demo
6. `compose/docker-compose.platform.yml` and `compose/docker-compose.yml`

Each step references the relevant ADR(s) and produces a Git commit. The first demo's framework choice is open until decided (per the framework-agnostic principle locked in ADR-007); recommendations are in the consolidation memo, section 3.

Stage 2 locks when the first demo is reachable end-to-end through TLS, tracked in MLflow, with artifacts in MinIO.

---

## Open dependencies in this plan

These items are explicitly parameterized and resolved as the relevant ADRs lock:

| Phase | Dependency | Resolved by |
|---|---|---|
| 3 | Filesystem permissions on the new repo folder | ADR-009 |
| 5 | Number of Git repositories to initialize | ADR-008 |
| 5 | GitHub visibility (public vs private) | ADR-008 |
| 8 | First demo's framework choice | Per-demo author decision (consolidation memo, section 3, has guidance) |
| 8 | Authentication for operational UIs (MLflow, Grafana, MinIO) | ADR-012 (folded in by Phase 8 since 012 is locked by trigger) |

When each blocking ADR locks, this memo is updated to make the corresponding phase concrete.

---

## What this plan deliberately does not do

A few things this plan is *silent* on, by design:

- **No specific commit message conventions.** Commit hygiene is a Stage 3 concern (CI/CD) and over-prescribing it now is premature.
- **No specific testing protocol for implementation phases.** Per-service testing conventions are part of ADR-011's expanded scope; the plan assumes those exist by the time Phase 8 begins.
- **No specific rollback plan if implementation fails.** Each commit in Phase 8 is its own checkpoint; rollback is `git revert` to the last good commit. More elaborate rollback is a Stage 3 concern.
- **No specific timeline.** The plan defines order, not duration. Each phase takes as long as it takes.

These omissions are intentional. The plan answers *what and when*, not *how* — that's where ADRs and runbooks live.

---

## How to maintain this memo

This memo is updated when:
- An ADR locks that resolves an open dependency above (especially ADR-008 → Phase 5, ADR-009 → Phase 3)
- The trigger event (ADR-012 lock) is reached and the plan begins executing — then each phase gets marked complete in a status section added at the top
- A new phase becomes necessary (rare; most missing detail belongs in ADRs or runbooks, not here)

This memo never overrides an ADR. ADRs lock decisions; this memo locks the procedure for transitioning between phases. When the platform repo exists and Stage 2 is locked, this memo gets a final status update marking the transition complete, and then it joins the historical archive of Stage 2 artifacts — its work is done.
