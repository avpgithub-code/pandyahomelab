# ADR-008: Repository packaging is a single monorepo

**Status:** Accepted
**Date:** May 2026
**Stage:** 2 (Synology Implementation)

## Context

ADR-007 established the repository *layout* (3-tier multi-service shape: `platform/`, `site/`, `services/`, `compose/`, `docs/`). It deliberately deferred the *packaging* question — how that layout distributes across one or more Git repositories — because the layout works under any packaging choice and locking layout first kept the decisions clean.

This ADR resolves the packaging question.

The packaging decision is not made in a vacuum. Since ADR-007 locked, the architecture has accumulated several constraints that bear directly on packaging:

- **Mode B-prime working environment.** Development happens via VS Code Remote-SSH directly on the NAS, with a single source tree at `/volume1/pandya-homelab/` shared by both `dev-nas` and `prod-nas` stacks (the B1 source tree pattern). This is documented in the Stage 2 Working Environment memo.
- **Cross-environment content discipline.** L1–L3 static content (apex landing, domain pages, technique pages) deploys to both NAS and AWS environments and must stay in sync.
- **AWS deploys a subset of NAS code, not separate code.** The same container images built on NAS are pushed to ECR and pulled by AWS EC2. There is no AWS-specific source tree.
- **Single operator.** No team boundaries, no permission separation requirements, no parallel contributors that would benefit from per-component repo isolation.
- **The live site is the portfolio.** `pandyahomelab.com` is the audience-facing artifact. Individual demo repositories are not part of the portfolio strategy.

These constraints, taken together, do not leave packaging fully open. They strongly favor consolidation. This ADR recognizes that and locks accordingly.

A repository is **not** a folder of related stuff. It is a coordination boundary defining what gets versioned together, what shares a release lifecycle, what shares CI/CD scope, and what shares dependency boundaries. Splitting the repository along anything other than these properties creates ongoing friction with no compensating benefit. For pandyaHomeLab, the components inside ADR-007's layout share *all* of these properties: same author, same release cadence at scale, same deployment lifecycle, same dependency surface.

The honest framing of this ADR is: **the working model already implies monorepo. This ADR locks that recognition rather than picking from neutral options.**

## Decision

**The pandyaHomeLab repository is a single Git monorepo at `pandyahomelab` containing the entire layout established by ADR-007 — `platform/`, `site/`, `services/`, `compose/`, `docs/` — along with all subordinate content.**

```
pandyahomelab/                         # ← one Git repository
├── platform/
│   ├── proxy/
│   ├── data/
│   └── mlops/
├── site/
├── services/
│   ├── ml/
│   ├── dl/
│   ├── nlp/
│   └── agentic/
├── compose/
├── docs/
└── README.md
```

The repository is hosted on GitHub at a public URL determined by Stage 2 implementation. Visibility (public from start vs. private until polished) is an operational decision, not architectural; this ADR does not lock it.

The repository is cloned to **one** location on the NAS — `/volume1/pandya-homelab/` — per the working environment memo. Both `dev-nas` and `prod-nas` stacks read from this single source tree (the B1 pattern). This is structurally enforced: a polyrepo or hybrid would require multiple clones and break the B1 model.

The repository is the build source for both NAS deployment and AWS deployment. Container images are built locally on the NAS, then either deployed directly to NAS stacks or pushed to ECR for AWS consumption. There is no separate AWS source tree.

Three principles govern this packaging decision:

1. **One source tree, one repository.** The B1 source tree pattern requires a single source location. The repository is that source. Multiple repositories would force multiple clones, which would defeat the working environment model.
2. **Versioning is unified.** A single `git log` shows the entire platform's history. A single `git tag` represents a coherent platform state. A single rollback restores a coherent past. Splitting into multiple repositories would distribute history across repos, requiring cross-repo coordination for any meaningful rollback or audit.
3. **CI/CD complexity is centralized, not distributed.** Path-filtered GitHub Actions workflows (Stage 3 concern) handle the "don't rebuild everything when one file changes" concern within a monorepo. The complexity exists somewhere regardless of packaging — monorepo concentrates it in one workflow file rather than distributing it across multiple repos that must coordinate.

Two subordinate clarifications follow from these principles:

- **Demos are not standalone repositories.** Each demo under `services/<domain>/<technique>/<dataset>-<algorithm>/` is a folder, not a separate repository. The framework-agnostic principle from ADR-007 still applies — demos can use any framework — but the framework choice is per-folder, not per-repository.
- **The repository is the deployment artifact.** When the platform is deployed to a new environment (laptop, future cloud, etc.), the operation is "clone the monorepo and bring up the appropriate stack." There is no "fetch multiple repos and integrate" step.

## Alternatives considered

**Polyrepo (rejected).** Multiple repositories along some boundary — per-domain (`pandyahomelab-ml`, `pandyahomelab-dl`, etc.), per-tier (platform vs. services), or per-demo (each demo as its own repo). Polyrepo's classical pitch is "independent lifecycles per component," which earns its complexity when components have genuinely different release cadences, contributor populations, or permission scopes. None of these apply to pandyaHomeLab — it has a single operator, a unified release lifecycle, and no permission boundaries to enforce.

More substantively, polyrepo would *fight* the working model established in the Stage 2 Working Environment memo:

- The B1 source tree pattern requires one source tree shared by both NAS stacks. Polyrepo means multiple trees, requiring coordination on every operation.
- Cross-environment L1–L3 content sync becomes a multi-repo coordination problem rather than a single-source operation.
- The contingency-clone pattern would require cloning multiple repos before going offline, increasing pre-trip overhead.
- Adding a new demo would require creating a new repository, configuring access, wiring CI/CD — all bureaucratic overhead per demo, repeated for every new addition.

Polyrepo is not architecturally wrong in the abstract. It is wrong for *this* architecture, given *this* operator, given *these* surrounding decisions.

**Hybrid (rejected).** Two or three repositories along the platform/services boundary (e.g., `pandyahomelab-platform` for `platform/`, `site/`, `compose/`, `docs/`; `pandyahomelab-services` for the demos). Hybrid mirrors the trust boundary established by ADR-001 (platform networks vs. domain networks) at the repository layer.

This is more defensible than full polyrepo, but still adds friction without commensurate benefit:

- Two `git pull` cycles per session instead of one
- Cross-repo references when a demo needs a platform service interface (Postgres connection conventions, MLflow tracking patterns, etc.)
- Two CI/CD pipelines to maintain instead of one
- Promotion (`dev-nas` → `prod-nas`) happens at the platform level — but with a hybrid, you'd merge changes in one repo and promote in the other, two related actions on two repositories

Hybrid would earn its complexity if platform and services genuinely had different release cadences. They don't, at this stage. They might, eventually — at which point a future ADR can split this monorepo. The cost of splitting later is bounded (`git filter-repo` or similar); the cost of merging multiple repos back is unbounded. Reversibility favors starting consolidated.

**Per-demo repositories as portfolio artifacts (rejected).** A specific case for polyrepo, where each demo is a standalone GitHub repository so that recruiters or reviewers can star, fork, and reference individual demos. This was the strongest argument for polyrepo and deserves explicit treatment.

The position taken by this project is that **the live site (`pandyahomelab.com`) is the portfolio**, not individual repositories. Visitors interact with running demos, not with READMEs. The infrastructure-and-platform story is more compelling shown as a coherent system than as a constellation of small repositories. Individual demo repositories would also fragment the architectural narrative — the story is "I built a platform that hosts these demos," not "I built these demos."

If portfolio strategy ever shifts to individual-demos-as-artifacts, the recourse is to extract specific demos into their own public-facing repositories at that time, while keeping the canonical source in the monorepo. That option remains available without compromising the current architecture.

**Submodules or subtrees (rejected).** Git submodules and subtrees offer a middle path: a single "super-repo" composed of multiple "child-repos." For a single-operator project, this introduces real complexity (submodule update commands, detached HEAD states, subtree merge conflicts) for no benefit beyond what a plain monorepo already provides. Submodules earn their place in projects with genuinely independent vendored components. pandyaHomeLab has no such components.

## Consequences

**Positive:**

- The working model from the Stage 2 Working Environment memo is structurally enforceable. The B1 source tree pattern is impossible to violate by accident — there is only one tree because there is only one repo.
- A single `git log`, single `git tag`, single rollback target. Platform history is unified and auditable.
- Adding a new demo is mechanical and lightweight — create a folder, register in `docker-compose.yml`, commit. No new repository to provision.
- Cross-environment content sync (L1–L3 across NAS and AWS) operates from a single source. Drift between environments is structurally prevented.
- The contingency-clone pattern remains simple — one `git clone` before going offline, one `git push` on return. Multi-repo would require remembering which repos are needed for which work.
- Stage 3 CI/CD design is straightforward — one workflow file with path filters, rather than orchestrating multiple repos with cross-triggers.
- Onboarding a future contributor (if ever) is one clone instead of N. Documentation lives next to the code it documents.
- The architecture diagrams from this stage (deployment view, source-flow view) match the repository structure 1:1 — one source tree box, one source of truth.

**Negative (trade-offs accepted):**

- Individual demo repositories do not exist as standalone GitHub artifacts. If portfolio strategy shifts, demos must be extracted manually. This was discussed and accepted; the live site is the portfolio.
- CI/CD pipeline complexity is concentrated in one workflow file. Path filters become essential to avoid rebuilding the entire platform on every commit. Stage 3 work must address this explicitly.
- The repository will grow over time as demos accumulate. Cloning eventually takes longer; some operations (full repo `grep`, `git log --all`) get slower at scale. For a portfolio platform with hobbyist commit velocity, this is unlikely to bite within Stage 2 or Stage 3 timeframes.
- All folders share GitHub permissions. If pandyaHomeLab ever has multiple contributors with different access levels, monorepo cannot grant per-folder permissions natively (GitHub's CODEOWNERS provides advisory rules but not enforcement). Single-operator scope makes this irrelevant for now.
- The repository becomes a single point of access. If the GitHub remote is unavailable, all components are unavailable. Mitigated by having the cloned working tree on NAS as a usable secondary source.

**Forecloses:**

- Per-demo independent versioning (e.g., "iris-knn v1.2.0" as a Git tag separate from the platform). Demo versioning, if ever needed, must be handled through other mechanisms (image tags, in-folder version files, or a future ADR superseding this one).
- Per-component release cadence. All components release at the same Git history granularity. Different cadences require different deployment strategies, not different repositories.
- Permission-isolated contributions. A future contributor cannot be granted access to one folder without access to all folders. This is acceptable for the foreseeable future given single-operator reality.
- Polyrepo or hybrid as alternative architectures are foreclosed by this ADR. They are not deleted as concepts — a future ADR could supersede this one — but they are foreclosed as the *current* architecture.

## Implementation reference

This ADR governs the repository creation step in the Stage 2 → Implementation Transition Plan (Phase 5). At transition time:

1. Initialize a single Git repository at `/volume1/pandya-homelab/` (`git init`)
2. Configure remote `origin` to a GitHub repository named `pandyahomelab` (or similar — operational naming choice)
3. Make the first commit capturing the seeded structure (ADRs, memos, empty scaffolding per ADR-007)
4. Push to GitHub
5. Tag this commit as the Stage 2 architectural baseline (e.g., `stage-2-baseline`)

Stage 3 (CI/CD) work will then build on this single repo with path-filtered GitHub Actions workflows.

## Related ADRs

- **ADR-001** — establishes the trust boundaries that some readers might use to argue for hybrid; this ADR explicitly accepts that the boundaries don't justify a repository split for single-operator scope
- **ADR-002** — establishes deployment-platform-agnosticism; the same monorepo serves NAS and AWS, consistent with this principle
- **ADR-003** — establishes the URL hierarchy that the layout (and therefore the repo structure) mirrors
- **ADR-007** — establishes the layout that this ADR packages into a single repository
- **ADR-009** (queued) — runtime filesystem layout on Synology (where the repo is cloned and how it's permissioned)
- **ADR-010** (queued) — secrets management (the repo's `.gitignore` rules for secret files)
- **ADR-011** (queued) — per-service conventions (per-folder discipline within the single repo)
- **ADR-012** (queued) — authentication strategy

## Related working memos

- **Stage 2 Consolidation Memo** — context on the deliberation that led here
- **Stage 2 Security Map** — repository as a security boundary (it is a single one)
- **Stage 2 Transition Plan** — Phase 5 (Git initialization) is parameterized by this ADR; with monorepo locked, Phase 5 is now concrete
- **Stage 2 Working Environment Memo** — the operational model this ADR makes structurally enforceable
