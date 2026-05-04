# Stage 2 Working Environment — April 2026

**Status:** Working memo (living document)
**Stage:** 2 (Synology Implementation), with forward references to Stage 4 (AWS)
**Style:** Operational reference (principles + mechanics)
**Purpose:** Defines the working model for pandyaHomeLab — where development happens, where production runs, how AWS fits in, and what discipline keeps everything coherent.

## Why this memo exists

pandyaHomeLab runs primarily on a single Synology NAS (192.168.1.152). Stage 4 will add AWS as a secondary deployment. The architecture in ADR-001 through ADR-007 is silent on several related-but-distinct questions:

- *Where does the operator actually do development work?*
- *How does development coexist with a live production platform on the same hardware?*
- *What does the AWS deployment actually contain, given that AWS is costly and the NAS is the primary platform?*
- *How does the public domain present both deployments to visitors?*

This memo answers those questions. It records the chosen working model and the discipline required to keep it working.

This is **not** an ADR. It's an operational reference. ADRs lock decisions; this memo locks operational practices and the rationale for them. When this memo and an ADR conflict, the ADR wins.

---

## The working environment principle (NAS side)

**One physical machine. Two logical stacks. One source tree. Strict promotion discipline.**

Four parts, each load-bearing:

- **One physical machine** — the NAS at 192.168.1.152 hosts both development and production. There is no separate development hardware.
- **Two logical stacks** — `dev-nas` and `prod-nas` run as separate Docker compose projects, with separate ports, volumes, and networks. They are invisible to each other at runtime.
- **One source tree** — both stacks read from the same cloned repository at `/volume1/pandya-homelab/`. There is no source-code drift between `dev-nas` and `prod-nas`.
- **Strict promotion discipline** — moving changes from `dev-nas` to `prod-nas` is git-based and explicit. No ad-hoc edits to running production. No silent overwrites.

The architecture supports this model because of decisions already locked: ADR-001's network isolation gives each stack its own networks; ADR-007's compose split (platform + demos) becomes the foundation for adding environment overlays; ADR-002's deployment-platform-agnostic principle ensures the same source serves both stacks identically.

---

## Naming convention

Stacks are named with a two-axis convention: **`<lifecycle>-<deployment-target>`**.

Current Stage 2 stacks:

- **`dev-nas`** — development stack on the NAS
- **`prod-nas`** — production stack on the NAS, serving public traffic at `pandyahomelab.com`

Future Stage 4 stacks:

- **`prod-aws`** — production stack on AWS, always-on, serving public traffic at `aws.pandyahomelab.com`

Stacks not currently planned but reserved by the convention:

- `stage-aws` — staging stack on AWS, *not currently used*. AWS deployment validation happens via Stage 3 CI/CD against the actual `prod-aws`, not against a separate staging stack.
- `dev-aws` — only if AWS-specific behavior eventually needs in-cloud testing during development. Not currently planned.

The convention scales as deployment targets multiply. It also makes Compose project names, volume folders, and overlay files self-documenting — the lifecycle-and-target is encoded in every artifact name.

---

## Mode B-prime mechanics (NAS side)

The development environment is the production NAS itself, accessed via VS Code's Remote-SSH extension. VS Code runs locally; files, terminals, and commands all execute on the NAS.

Concretely:
- VS Code on the laptop opens `/volume1/pandya-homelab/` as the workspace, via SSH to 192.168.1.152
- Edits, builds, container starts, log inspection — all happen on the NAS
- The Docker daemon you build against IS the daemon that runs production
- No "works on my machine" — there is no "my machine," only the NAS

This is *Mode B-prime* in pandyaHomeLab vocabulary, distinguishing it from the simpler "edit live production code" pattern (which is unsafe) and from "develop on a separate laptop and sync" (which has parity drift risks).

### Stack isolation

The two stacks are kept independent through three mechanisms:

**Compose project namespacing.**
- `dev-nas`: brought up via `docker compose -p homelab-dev-nas`
- `prod-nas`: brought up via `docker compose -p homelab-prod-nas`

Docker treats each project as a fully separate set of containers, networks, and volumes.

**Port separation.**
- `prod-nas` Nginx binds host ports 8080/8443 (the Fios-forwarded ports for public traffic — see ADR-006)
- `dev-nas` Nginx binds different host ports (e.g., 18080/18443) reachable on the LAN only

A user typing `pandyahomelab.com` always reaches `prod-nas`. The operator testing changes reaches `dev-nas` via `https://192.168.1.152:18443/` from the LAN.

**Volume separation.**
- `prod-nas` volumes mount under `/volume1/pandya-homelab/data-prod-nas/`
- `dev-nas` volumes mount under `/volume1/pandya-homelab/data-dev-nas/`

Each stack has its own Postgres data directory, its own MinIO buckets, its own MLflow tracking database.

---

## The B1 source tree pattern

Both stacks read source code from the **same** cloned repository at `/volume1/pandya-homelab/`. There is exactly one tree.

Specifically:
- `services/ml/classification/iris-knn/app/main.py` is one file
- Both `dev-nas` and `prod-nas` build their `iris-knn` images from it
- An edit to that file is *immediately* visible to both stacks at the source level

What differs between stacks is **when each stack rebuilds and runs the new code**:

- **`dev-nas`** rebuilds eagerly. After saving an edit, `docker compose -p homelab-dev-nas build iris-knn && docker compose -p homelab-dev-nas up -d iris-knn` picks up the change in seconds.
- **`prod-nas`** rebuilds explicitly and rarely. It only rebuilds when the operator decides to promote a change — never as a side effect of editing.

This is the safety property: editing the source tree changes what *would* run if rebuilt, but it does not change what *is* currently running. `prod-nas` continues serving the previously-built image until told otherwise.

### Compose overlay structure

```
compose/
├── docker-compose.platform.yml         # Platform services (env-agnostic base)
├── docker-compose.yml                  # Demo services (env-agnostic base)
├── docker-compose.dev-nas.yml          # dev-nas overlays
├── docker-compose.prod-nas.yml         # prod-nas overlays
└── .env.example                        # Documents required env vars
```

A wrapper script (`make up-prod-nas`, `make up-dev-nas`, etc.) absorbs the verbose compose commands. The wrapper is operational — not architectural — so it lives in the runbook layer.

---

## The promotion mechanism (NAS side)

Moving a change from `dev-nas` to `prod-nas` is **git-based and explicit**.

The discipline:

1. **Always work on a feature branch.** Never commit directly to `main`.
2. **Test the branch in `dev-nas`.** Pull/checkout the branch in `/volume1/pandya-homelab/`, rebuild `dev-nas`, verify it works.
3. **Merge to `main` only when stable.** Through a clean local merge or a GitHub PR.
4. **Promote to `prod-nas` explicitly.** After merging, with `main` checked out, rebuild `prod-nas` containers.
5. **Verify `prod-nas` is healthy.** Smoke-test the public URL after promotion.

Two practical implications:

- **The branch you have checked out matters for `prod-nas`.** Because both stacks share the source tree, switching the working tree to a feature branch and rebuilding `prod-nas` would deploy that feature branch to production. The rule: **`prod-nas` only rebuilds when `main` is checked out.**
- **Long-running feature branches are fine in `dev-nas`.** They affect only `dev-nas` (which can be rebuilt freely) and don't risk prod.

A small wrapper script can enforce the "main-only-for-prod" rule, refusing to rebuild `prod-nas` if `git rev-parse --abbrev-ref HEAD` is not `main`.

---

## The AWS deployment model

`prod-aws` is fundamentally different from `prod-nas` in scope. It is not a mirror of the full platform — it is a **minimal serving layer** that demonstrates cloud-architecture skills while keeping AWS costs bounded.

### What `prod-aws` contains

- **Nginx** as the reverse proxy and TLS terminator (not ALB — see "AWS architecture choices" below)
- **Demo containers** for the demos selected for AWS hosting
- **Static site content** for the L1–L3 pages (per ADR-003)

### What `prod-aws` deliberately does NOT contain

- ❌ MLflow — model *tracking* happens on the NAS during training; only the trained model artifact gets shipped to AWS
- ❌ Prometheus / Grafana / Loki — observability for development; the NAS handles this
- ❌ Postgres — unless a demo specifically writes/reads from a database at runtime
- ❌ MinIO — same reason; trained model files get baked into container images
- ❌ Multi-AZ — single-AZ is sufficient for portfolio-level traffic

This is a deliberate subset of ADR-001's six logical networks. ADR-002's mirror principle holds for *the parts that exist on both platforms*; networks that don't exist on AWS simply aren't deployed there. **AWS deploys what it needs, not what the full architecture defines.**

### AWS architecture choices

**Nginx on EC2, not ALB.**
- ALB costs ~$16/month base + LCU charges, regardless of traffic
- A single t4g.small EC2 running Nginx + demo containers costs ~$15-25/month all-in
- For portfolio traffic, ALB is overkill — Nginx-on-EC2 delivers the same routing capability
- Architectural bonus: Nginx-on-AWS preserves the *same mental model* as Nginx-on-NAS (per ADR-006). One reverse proxy pattern, applied twice.

**Single-AZ deployment.**
- ADR-002 explicitly allows single-AZ as a deployment choice (multi-AZ is design-time, deployment-time can vary)
- For portfolio use, multi-AZ pays for resilience that nobody is depending on
- Cost difference is meaningful: NAT Gateways alone in two AZs would exceed the entire single-AZ deployment cost

**Always-on, with Terraform-as-recovery.**
- `prod-aws` runs continuously to enable a live URL for portfolio review
- Reliability comes not from preventing failure (multi-AZ, ALB auto-replacement) but from *recovering quickly* via Terraform
- See "Terraform-as-recovery posture" below

**Estimated monthly cost: ~$25-50.** Bounded, predictable, justifiable as portfolio investment.

### Storage architecture on AWS

The principle: **stateless containers + one small EBS volume for host-level persistent state**.

| Layer | Storage | Why |
|---|---|---|
| Container images | ECR (managed, S3-backed under the hood) | Deduplication, AWS handles durability |
| Container runtimes | None — ephemeral | They're stateless |
| Static site content | Baked into Nginx image | Source-controlled |
| TLS certificates (Certbot) | Small EBS volume mounted at `/etc/letsencrypt/` | Avoid ACME rate limits during recovery |
| Docker image cache | Same EBS volume at `/var/lib/docker/` | Fast restarts |
| Application logs | Stream to CloudWatch Logs | AWS-managed, queryable |
| Any future stateful demo | S3 via SDK (not Docker volume) | Survives EC2 termination |

**Configuration files (Nginx config, etc.) are baked into container images at build time on the NAS, then pushed to ECR.** They do not need persistent storage — they are part of the container itself and survive every restart for free.

The single EBS volume protects only what is *generated at runtime and expensive to regenerate* (TLS certs hit ACME rate limits if regenerated too often). Everything else is either baked into images or external (S3, CloudWatch).

### Terraform-as-recovery posture

`prod-aws` is described entirely as Terraform code. Recovery from AWS-side failure is **`terraform apply`**, not heroic manual rebuilding.

This works because of the storage architecture above: AWS holds no source-of-truth state. The NAS is canonical; AWS is a render of it. Losing AWS loses nothing important because:
- Container images can be rebuilt from source on the NAS and pushed to ECR
- Models inside images can be retrained or restored from NAS-side MLflow
- Site content is in Git
- TLS certs auto-renew via Certbot

Two disciplines required to make this real:

**Terraform must be current and tested.** Terraform code that's never been re-applied since first deployment has a real chance of failing on the day you need it. Stage 4 work should include at least one deliberate `terraform destroy` and `terraform apply` cycle to validate the recovery story.

**Backend state must be remote.** Terraform's `.tfstate` lives in S3 (with DynamoDB locking), not on a local machine. If the local machine is lost, recovery is still possible from any machine with AWS credentials.

---

## DNS structure

The public domain `pandyahomelab.com` is registered at Hostinger. DNS records resolve as:

| URL | Resolves to | Serves |
|---|---|---|
| `pandyahomelab.com` (apex) | NAS (Fios → NAS Nginx on 8080/8443) | Apex landing page; primary site identity |
| `aws.pandyahomelab.com` | AWS EC2 (Nginx on 80/443) | AWS-deployed serving layer |

**No `nginx.*` subdomain.** Nginx is infrastructure, not an application; it has no public-facing identity to host.

**No `dev.*` subdomain.** `dev-nas` is LAN-only at `192.168.1.152:18443`; public DNS deliberately does not advertise the development environment.

**No subdomains for operational UIs (MLflow, Grafana, MinIO console) yet.** These become relevant when ADR-012 (authentication) is decided. Premature to lock now.

---

## The apex landing page

`pandyahomelab.com` serves a unified landing page that:
- Introduces pandyaHomeLab — what it is, the four AI domains, the philosophy
- Presents the platform as running in two environments (NAS and AWS)
- Provides two prominent navigation options to enter the platform

### The Pattern Z navigation model

The "environment toggle" is implemented as **two clearly-labeled links**, not a JavaScript widget or cookie-based persistence:

```
[ View on NAS → ]   [ View on AWS → ]
```

- **"View on NAS →"** links to `pandyahomelab.com/ml/` (and similar entry points for other domains)
- **"View on AWS →"** links to `aws.pandyahomelab.com/ml/`

Clicking the button takes the visitor to the chosen environment. From there, internal navigation stays within that environment — NAS-served pages link to other NAS-served pages; AWS-served pages link to other AWS-served pages.

**Properties of this pattern:**
- Zero JavaScript required for the toggle
- Zero cookies required
- The URL bar always accurately reflects which environment serves the current page
- Switching environments mid-visit means going back to the apex (or via a prominent footer link on each environment's pages)
- Maximally clear to visitors and to recruiters reviewing the portfolio

### Default environment

A visitor who clicks any link other than the explicit "View on AWS" navigates the NAS-served version. **NAS is the default identity of pandyaHomeLab; AWS is the deliberate alternative.**

This means:
- The platform's primary identity is the homelab
- AWS exists to demonstrate cloud-architecture skills, not to be the platform's main face
- A visitor who never notices the "View on AWS" link still gets the full pandyaHomeLab experience

---

## Cross-environment content discipline

The L1–L3 static content (apex landing, domain pages, technique pages) exists in both NAS and AWS deployments. Visitors switching environments expect consistent content.

The discipline: **L1–L3 content changes are deployed to both environments together, ideally via the same CI/CD pipeline (Stage 3 concern).**

Implication for ADR-008 packaging: the chosen packaging must support "deploy to two environments simultaneously" as a workflow. Monorepo handles this naturally via shared build artifacts; polyrepo would require coordination across multiple repos for every L1–L3 update.

---

## Demo selection per environment

Not every demo will run on both `prod-nas` and `prod-aws`. Honest constraints:

- **GPU-bound demos** (large CNNs, transformer fine-tuning) likely stay NAS-only
- **Memory-heavy demos** that exceed AWS instance sizing stay NAS-only
- **Stateful demos** that require platform services not present on AWS (MLflow, MinIO at runtime) stay NAS-only
- **Stateless inference demos** can run on either; suitable for AWS hosting

The site should gracefully handle the "this demo runs on NAS only" case rather than pretending uniformity. A note like *"This demo runs on NAS only because it requires GPU acceleration"* is *more* informative than hiding the constraint — it shows the visitor that the architecture's limits are deliberate.

---

## The contingency-clone pattern

Mode B-prime requires NAS access to develop. When that's not available — travel, network outage, NAS maintenance — a fallback exists: a laptop clone of the repo.

**When to use:**
- Travel without VPN
- Extended NAS downtime
- Working from a location with unreliable network

**How to maintain:**
- The laptop clone is **not** routine. It exists for contingency.
- Before going offline, `git pull` on the laptop to sync with NAS state.
- Work on the laptop creates feature branches like normal.
- On return, push branches from laptop, pull them on NAS, integrate via the standard promotion mechanism.

**What to avoid:**
- Don't develop simultaneously on laptop and NAS — stick to one at a time.
- Don't run prod-equivalent stacks on the laptop. The laptop is for *editing*; testing happens back on the NAS.
- If laptop work becomes routine, that's a signal Mode A should be considered (and this memo revisited).

---

## Backup discipline

In Mode B-prime, the NAS is the source of truth for the platform. NAS failure without backup means losing not just code (which Git protects) but also runtime state, MLflow tracking history, MinIO artifacts, Postgres data.

**Source code:**
- `git push` to GitHub on every meaningful commit
- Push branches early; don't accumulate local-only work

**Runtime state (NAS):**
- Synology Hyper Backup (or equivalent) configured to back up `/volume1/pandya-homelab/` to either an external USB drive or a cloud destination
- Backup runs at least weekly; daily preferred
- Periodic restore verification — at least once per quarter, restore a backup to a test location and confirm it's intact

**What gets backed up:**
- Source tree (redundant with GitHub, cheap insurance)
- `data-prod-nas/` and `data-dev-nas/` (Postgres, MinIO, MLflow databases — generated state Git doesn't protect)
- `/volume1/pandya-homelab/.env` (real secrets, never in Git per ADR-010)
- Container Manager configurations from DSM

**What does not need backing up:**
- Docker images (rebuilt from source)
- Container logs older than retention window

**AWS side:** No persistent state to back up beyond the small EBS volume holding TLS certs. EBS snapshots are cheap; configure weekly.

---

## Implications for queued ADRs

This memo has ripple effects through several Stage 2 ADRs that are not yet locked. Each ADR should explicitly acknowledge what this memo establishes:

| ADR | Implication |
|---|---|
| **ADR-008** (packaging) | Mode B-prime + B1 + cross-environment deployment workflow strongly favors monorepo. Polyrepo would require multiple clones for B1 and complicate L1–L3 cross-environment deployment. |
| **ADR-009** (filesystem + permissions) | Must address `data-dev-nas/` vs `data-prod-nas/` parent folders, their permissions, and the rule that container user IDs must not break operator (SSH user) write access to source files. |
| **ADR-010** (secrets) | Two `.env` files needed — one per stack on NAS — both outside Git. AWS secrets handled via AWS Secrets Manager (forward reference to Stage 4). |
| **ADR-011** (per-service conventions) | Dockerfile patterns should encourage fast rebuilds (multi-stage, layer caching) for `dev-nas` iteration speed and small image sizes for ECR push speed. |
| **ADR-012** (authentication) | Operational UIs (MLflow/Grafana/MinIO) reachable on `dev-nas` (LAN-only, low risk) and `prod-nas` (publicly reachable, must be authenticated). AWS-side has no operational UIs to authenticate (they don't exist on AWS). |

These aren't blockers for ADR-008 — they're forward references that those ADRs should pick up when drafted.

---

## What this memo deliberately does not specify

- **Specific port numbers for `dev-nas`.** 18080/18443 are illustrative; final values land in implementation.
- **Specific volume folder paths beyond the parent split.** `data-dev-nas/<service>/` structure is implementation detail.
- **Wrapper script syntax.** `make up-dev-nas` etc. are recommendations; final form lands in the runbook.
- **Specific EC2 instance type for AWS.** t4g.small is illustrative; sized at Stage 4 implementation.
- **Specific Terraform module structure for AWS.** Stage 4 concern.
- **Apex landing page visual design.** Content and structure described; visual design is Stage 2 implementation.

These omissions are intentional. The memo defines *what the working model is*, not *every operational nut and bolt*. Implementation detail belongs in runbooks; specific tool choices belong in their relevant ADRs.

---

## How to maintain this memo

This memo is updated when:
- A new lifecycle or deployment target is added (e.g., a third environment beyond NAS and AWS)
- A discipline rule changes based on operational experience
- An ADR locks that resolves one of the implications above (mark the row as resolved)
- The contingency-clone pattern becomes routine (signal that Mode A should be considered)
- AWS architecture changes meaningfully (e.g., adopting ALB if traffic justifies it)

This memo never overrides an ADR. It is operational guidance, not architectural authority.
