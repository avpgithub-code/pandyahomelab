# Stage 2 Security Map — April 2026

**Status:** Working memo (living document)
**Stage:** 2 (Synology Implementation)
**Style:** Index (concern → ADR → status → trigger)
**Purpose:** Single-page reference for which security concerns pandyaHomeLab has addressed, where each is addressed, and what triggers the deferred ones.

## How to use this map

When a question arises in the form *"have we thought about security from angle X?"*, look up the concern below. Each row tells you:

- **What the concern is** (concrete, not abstract)
- **Which ADR addresses it** (or "deferred")
- **The current status** (locked, queued, deferred)
- **The trigger** that fires the deferred ones

This is a *map*, not a *threat model*. It tells you where security thinking lives, not whether it's correct. ADRs are still the source of truth for any specific decision.

## The seven concerns

### 1 — Network security

**What it is:** Who can reach what at the IP/port level. Firewall, Docker networks, AWS security groups, Fios port forwards.

**Where addressed:** **ADR-001** (trust-boundary isolation — six logical networks, no flat network), **ADR-002** (Synology/AWS mirror with multi-AZ), **ADR-006** (Nginx as the sole reverse proxy on host ports 8080/8443).

**Status:** **Locked** (Stage 1).

**Open items:** None. Network boundaries are stable. Future ADRs may add networks (e.g., for GPU isolation), but the current isolation model is sound.

---

### 2 — Transport security (TLS / encryption in flight)

**What it is:** HTTPS for public traffic. Optionally mTLS for internal container-to-container traffic.

**Where addressed:** **ADR-005** (mentions TLS automation), **ADR-006** (Nginx terminates TLS — replacing DSM's automatic Let's Encrypt). TLS automation itself deferred to Stage 5.

**Status:** **Partially addressed; full automation deferred.**

**Trigger for resolution:** Stage 5 — a Stage 5 ADR will specify TLS automation (Let's Encrypt HTTP-01 vs DNS-01, renewal, monitoring). The first demo can ship with a manually-issued cert; automation is not Stage 2 critical-path.

**Open items:** Internal mTLS between containers (currently no encryption inside Docker networks) — likely deferred indefinitely, since trust-boundary isolation already handles the threat model for a single-operator lab.

---

### 3 — Authentication (AuthN — who is this user)

**What it is:** Login flows, API keys, session management. Specifically: which surfaces are public (demos) and which require login (MLflow UI, Grafana, MinIO console).

**Where addressed:** **ADR-005** foreshadowed it. **ADR-012 (Accepted)** specifies the strategy: operational UIs LAN-only; HTTP Basic Auth at Nginx as the available mechanism for any future authenticated resource.

**Status:** **Resolved** (ADR-012, May 2026).

**Resolution summary:** Operational UIs (MLflow, Grafana, MinIO console) are LAN-only and not publicly reachable. HTTP Basic Auth at Nginx is established as the platform's authentication mechanism, available for any future resource (publicly-exposed UI or per-demo authentication) without further architectural deliberation. Demos remain publicly accessible without authentication, preserving the portfolio's frictionless visitor experience.

**Open items:** None at Stage 2 scope. Future authentication needs (OAuth, MFA, audit logging) are explicitly deferred per ADR-012.

---

### 4 — Authorization (AuthZ — what is this user allowed to do)

**What it is:** Role-based access control. Who can see which dashboards, modify which configs, retrain which models.

**Where addressed:** Not yet. No ADR.

**Status:** **Deferred indefinitely.**

**Trigger for resolution:** The platform takes on a second user. As long as pandyaHomeLab has a single operator, AuthZ is degenerate (the operator can do everything). When/if a second user is added (collaborator, demo viewer with restricted access), an ADR is needed.

**Open items:** None until trigger fires.

---

### 5 — Filesystem permissions

**What it is:** Who can read/write/delete what files at three layers — NAS-level (Synology user/group permissions on `/volume1/pandya-homelab/`), container user-ID level (does the container run as root or a non-privileged user), and volume-mount level (read-only vs read-write mounts).

**Where addressed:** **ADR-009 (Accepted)** covers all three layers — NAS-level (operator user owns `/volume1/pandya-homelab/` with `homelab` group, `750` permissions), container user-ID level (containers run as operator's UID via `HOST_UID` env var), and volume-mount level (source code read-only, data dirs read-write per-container).

**Status:** **Resolved** (ADR-009, April 2026).

**Resolution summary:** Platform lives at `/volume1/pandya-homelab/` with code (the cloned monorepo) and runtime data (`data-dev-nas/`, `data-prod-nas/`) as siblings. Owned by the operator's user with the dedicated `homelab` group and `750` permissions. Containers run as the operator's UID (read from `HOST_UID` env), eliminating cross-ownership friction between operator edits and container writes. Source mounts are read-only; data mounts are read-write and scoped per-container with cross-stack writes structurally forbidden.

**Open items:** None at Stage 2 scope.

---

### 6 — Secrets management

**What it is:** How database passwords, API keys, MLflow tokens, and similar credentials are stored, injected, and rotated.

**Where addressed:** **ADR-010 (Accepted)** specifies the strategy.

**Status:** **Resolved** (ADR-010, April 2026).

**Resolution summary:** Two `.env` files on the NAS — `/volume1/pandya-homelab/.env.dev-nas` and `.env.prod-nas` — hold environment-specific secret values. Identical variable names within each file; compose loads the right file via `--env-file`. Secrets are generated manually by the operator and canonical-stored in a password manager (Bitwarden, 1Password, etc.); the .env files are deployed copies. Files are chmod 600, owned by operator, excluded from Git, and excluded from Hyper Backup (canonical store handles disaster recovery). AWS-side secrets are deferred to Stage 4 (AWS Secrets Manager).

**Open items:** None at Stage 2 scope. AWS-side mechanism is a Stage 4 concern.

---

### 7 — Data security (at rest, in queries)

**What it is:** Database encryption at rest, parameterized queries (SQL injection), input validation on demo APIs, MinIO bucket isolation between demos.

**Where addressed:** Partially deferred to **ADR-011** (input validation, framework-level safeguards) and partially uncovered (encryption at rest, MinIO bucket isolation).

**Status:** **Partially deferred; partially uncovered.**

**Trigger for resolution:**
- Input validation and SQL safety: ADR-011 (per-service conventions, expanded scope) — addressed when the first demo is built.
- Database encryption at rest: deferred indefinitely. Not relevant for non-sensitive demo data; becomes relevant if pandyaHomeLab ever hosts user-uploaded data or PII.
- MinIO bucket isolation: needs explicit decision once the second demo writes artifacts to MinIO. Likely a small ADR or an ADR-011 sub-clause.

**Open items:** All of the above. Lowest priority for a portfolio platform with non-sensitive demo data.

---

## At-a-glance summary

| # | Concern | Status | Home ADR | Urgency |
|---|---|---|---|---|
| 1 | Network | Locked | ADR-001/002/006 | — |
| 2 | Transport (TLS) | Partial | ADR-005/006; Stage 5 | Stage 5 |
| 3 | Authentication | **Resolved** | ADR-012 | — |
| 4 | Authorization | Deferred | — | When second user added |
| 5 | Filesystem permissions | **Resolved** | ADR-009 | — |
| 6 | Secrets management | **Resolved** | ADR-010 | — |
| 7 | Data security | Mixed | ADR-011 + uncovered | Per sub-concern |

## Triggers to watch for during Stage 2

In implementation order:
1. First platform service needing a secret → forces **ADR-010**.
2. First Dockerfile / volume-mount written → forces **ADR-009**.
3. First demo being built → forces **ADR-011**.
4. First operational UI (MLflow/Grafana/MinIO) becomes publicly reachable → forces **ADR-012**.

If these triggers fire and no decision is captured, the implementation is making the security decision implicitly. The discipline is: **when a trigger fires, ADR first, code second.**

## How to maintain this map

This memo is updated whenever:
- A new ADR is queued or accepted that touches any of the seven concerns.
- A new security concern surfaces that doesn't fit any existing row.
- A trigger fires and the corresponding ADR is drafted.

This memo never overrides an ADR. It is supplementary navigation, not architectural authority.
