# ADR-009: Runtime filesystem layout and permissions on Synology NAS

**Status:** Accepted
**Date:** May 2026
**Stage:** 2 (Synology Implementation)

## Context

ADR-007 established the repository layout in source-code terms (folders within a Git repository). ADR-008 established that this layout lives in a single monorepo. Both ADRs were deliberately silent on a related-but-distinct question: *where on the Synology NAS does the platform physically live, and what filesystem permissions govern who can read or write what?*

This is not a minor implementation detail. Filesystem placement and permissions enforce architectural intent at runtime: which folders containers can write to, which folders the operator owns, where runtime state accumulates separately from source code, and how the cloned repo coexists with other Synology uses of the NAS.

The decision has been deferred until now because earlier ADRs needed to establish their own scope first. With layout (ADR-007) and packaging (ADR-008) locked, plus the working model documented in the Stage 2 Working Environment memo, the runtime filesystem decision can be made with all the relevant constraints in place.

Several constraints carry forward from earlier decisions and bear directly on this ADR:

- **The repository is a single monorepo** (ADR-008), cloned to one location on the NAS.
- **The repository must not contain Synology-specific paths** (ADR-002, ADR-007) — `/volume1/` does not appear in source code.
- **`dev-nas` and `prod-nas` are separately-running stacks** (Working Environment memo) — they need separate volume directories with no cross-contamination.
- **Mode B-prime requires the SSH user to own the source tree** (Working Environment memo) — VS Code Remote-SSH editing must just work.
- **Synology's `/volume1/docker/` convention is reserved for ad-hoc Synology containers** (early Stage 2 deliberation) — pandyaHomeLab does not use it.
- **Containers are mostly stateless** (Working Environment memo, AWS architecture) — most volume mounts are read-only; data directories are deliberate exceptions.

The decision must also address a permissions concern unique to home-lab Docker setups: the friction that arises when containers run as one UID and the operator runs as another. Files written by containers are then owned by an unrelated user, and either the operator or the container is locked out of files the other writes. This is the most common operational pain point in single-operator Docker environments, and a deliberate design choice can prevent it entirely.

This ADR resolves both the filesystem placement question and the permissions question together, because they are inseparable in practice.

## Decision

**The pandyaHomeLab platform lives at `/volume1/pandya-homelab/` on the NAS, with the cloned monorepo and runtime data directories as siblings under that parent. All folders are owned by the operator's SSH user and the dedicated `homelab` group, with `750` permissions. Containers run as the operator's UID. Source code is mounted read-only into containers; data directories are mounted read-write per-container with strict scoping.**

### Filesystem structure

```
/volume1/pandya-homelab/
├── (cloned monorepo per ADR-007 and ADR-008)
│   ├── platform/
│   ├── site/
│   ├── services/
│   ├── compose/
│   ├── docs/
│   └── README.md
├── data-dev-nas/                    # dev-nas runtime state (NOT in repo)
│   ├── postgres/
│   ├── minio/
│   ├── mlflow/
│   └── redis/
├── data-prod-nas/                   # prod-nas runtime state (NOT in repo)
│   ├── postgres/
│   ├── minio/
│   ├── mlflow/
│   └── redis/
└── .env                              # secrets (NOT in repo, see ADR-010)
```

The cloned repo and the runtime data folders are **siblings** under the same parent. The parent (`/volume1/pandya-homelab/`) holds everything related to the platform — code, runtime state, secrets — in one place. Backup, monitoring, and migration are simpler because there is one parent folder to consider.

The Synology default `/volume1/docker/` directory is **not used by pandyaHomeLab**. It remains available for ad-hoc Synology Container Manager projects (such as the existing `my-website`) that are not part of the platform.

### NAS-level ownership and permissions

- **Owner:** the operator's Synology DSM user (the user that SSHs into the NAS for Mode B-prime work)
- **Group:** a dedicated `homelab` group, created on the NAS for forward compatibility (additional users — backup service accounts, future contributors — can be added to this group without changing ownership)
- **Permissions:** `750` on the parent folder and recursively on all subfolders (owner full, group read/execute, world nothing)

The `750` choice is deliberately conservative. World access is forbidden because the NAS hosts public-facing services, and "world" includes any future container user that might run outside the `homelab` group. Group read/execute allows future expansion (a backup process, a monitoring agent) without granting write access.

### Container user-ID convention

Containers run as a non-root user whose UID matches the operator's SSH user UID (typically 1026 on Synology DSM, though the exact value is operator-specific).

This is implemented in two places:

1. **In Dockerfiles**, via `USER <uid>` directives and `RUN useradd -u <uid>` patterns
2. **In compose files**, via `user: "${HOST_UID}:${HOST_GID}"` declarations that read the operator's UID/GID from environment variables

The result: any file a container writes via volume mount is owned by the operator. Edits from VS Code Remote-SSH and writes from running containers are interoperable. The "container wrote a file I can't edit" friction is structurally eliminated.

This convention does not apply to AWS deployments, where the EC2 user model is different and the operator does not typically SSH in for direct file editing. AWS-side container UID conventions are out of scope for this ADR (Stage 4 concern).

### Volume mount rules

Three categories of mounts, each with a rule:

| Category | Mount type | Rationale |
|---|---|---|
| Source code (`platform/`, `services/<demo>/app/`, `site/`) | **Read-only** | Containers should never modify their own source. Read-only mounts make this structurally enforced. |
| Data directories (`data-dev-nas/postgres/`, `data-dev-nas/minio/`, etc.) | **Read-write, scoped per-container** | Stateful services need to write to their data dirs. Each container mounts only its own data subfolder. |
| `.env` file | **Not mounted** | Read by docker-compose at startup; container processes see env *values*, not the file itself |
| `docs/`, `.git/` | **Not mounted** | No runtime relevance |

Two additional rules apply to data directories:

- **Cross-stack writes are forbidden.** A `dev-nas` container must not have any mount that resolves into `data-prod-nas/`, and vice versa. This is enforced via compose configuration — `dev-nas` overlays only reference `data-dev-nas/` paths; `prod-nas` overlays only reference `data-prod-nas/` paths.
- **The operator can read all data directories.** Backup, debugging, and occasional manual inspection require operator access to runtime state. This is automatic given the UID convention above — files written by containers are owned by the operator.

## Alternatives considered

**Repo and runtime state at separate top-level paths (rejected).** An alternative was to put the repo at `/volume1/pandya-homelab/` and runtime state at `/volume1/pandya-homelab-runtime/` (or similar). This achieves stricter visual separation of code from state, but at the cost of two backup targets, two paths to remember, and compose files referencing absolute paths into the runtime folder rather than relative paths. The sibling-folders model keeps everything together while still keeping data outside Git via `.gitignore`. Stricter physical separation does not earn its complexity for single-operator scope.

**Mirroring Synology's `/volume1/docker/` convention (rejected).** Synology's Container Manager defaults to `/volume1/docker/` for project files. Adopting this convention would mean putting the platform at `/volume1/docker/pandya-homelab/`. This was rejected during early Stage 2 deliberation for reasons documented in ADR-007 (platform-agnosticism — the repo layout should not assume Synology), and rejected again here for runtime placement reasons: `/volume1/docker/` is shared with other Synology Docker uses and mixing pandyaHomeLab with `my-website` and similar would conflate distinct lifecycles. Keeping `/volume1/pandya-homelab/` separate preserves clear boundaries.

**Containers run as root (rejected).** The Docker default. Simplest possible setup — no UID configuration in Dockerfiles or compose files. Rejected because root-owned files written by containers via volume mount cannot be edited by the operator without either `sudo` or `chown` after every write. This friction compounds during Mode B-prime iteration, where edit/run cycles happen many times per session. Running as the operator's UID eliminates the friction entirely at trivial setup cost.

**Containers run as their own per-image users (rejected).** A common production pattern: each Dockerfile creates its own `app` user (often UID 1000) and runs as that. Provides strict isolation between containers and host. Rejected because it recreates the very friction this ADR is designed to prevent: container-written files have UID 1000, operator has UID 1026, neither can easily edit the other's files. The isolation benefit is theoretical for single-operator development; the friction is daily and real. For production-scale multi-tenant deployments this pattern is correct; for pandyaHomeLab it is not.

**Default user group instead of dedicated `homelab` group (rejected as default).** Using the operator's primary Synology group (typically `users`) instead of creating a `homelab` group works fine for the single-operator present. Rejected as the default because the dedicated group is forward-compatible at zero present cost. If the platform ever grows to include a backup service account, a monitoring agent, or a future contributor, those additions can be granted access by adding them to the `homelab` group without changing folder ownership. The convention costs one DSM admin action now and saves a refactor later.

**Read-write source code mounts (rejected).** Allowing containers write access to their own source code (e.g., for "live reload" patterns where the container modifies files it serves) was considered. Rejected because the safety property of "containers cannot corrupt their own source" is more valuable than the convenience of in-container edits. The operator edits source via VS Code Remote-SSH; containers consume what the operator writes. This separation is enforced by read-only mounts.

## Consequences

**Positive:**

- The friction of cross-ownership between operator and containers is structurally eliminated. Files written by containers are owned by the operator. Edits via VS Code Remote-SSH and writes from running containers are interoperable.
- Backup is simple: one parent folder (`/volume1/pandya-homelab/`) contains everything that needs backing up. Hyper Backup configuration is straightforward.
- Stack isolation is enforced at the filesystem level. `dev-nas` containers physically cannot write to `data-prod-nas/` because their compose configuration does not reference that path. A bug or a misconfiguration cannot accidentally cross the boundary.
- Read-only source mounts protect against an entire class of bugs (a container corrupting its own source, a compromised container modifying platform code).
- Synology's default `/volume1/docker/` remains untouched, available for non-platform Synology Docker uses without conflict.
- The dedicated `homelab` group provides a clean expansion path. Adding a backup service account or future contributor is a `synogroup --add homelab <user>` operation, not a permissions refactor.
- The filesystem structure visibly mirrors the architecture: code in the repo, state in data folders, secrets in .env, all clearly separated by their location.

**Negative (trade-offs accepted):**

- The platform lives at a non-standard location for Synology Docker users (`/volume1/pandya-homelab/` rather than `/volume1/docker/pandya-homelab/`). Operators familiar with Synology conventions must learn the deliberate departure. Mitigated by documentation in the README.
- Container UIDs are coupled to the operator's specific UID. If the operator's Synology UID changes (e.g., NAS migration to fresh DSM install), Dockerfiles or compose env vars must be updated. Mitigated by reading UID from environment variable (`HOST_UID`) rather than hardcoding it.
- Read-only source mounts prevent some "in-container debugging" patterns where developers might want to `vi` a file inside a running container. Operators must edit source via SSH and rebuild instead. This is the desired discipline (see Working Environment memo), so the constraint is welcome rather than burdensome.
- A dedicated group adds one DSM admin step (creating the group) before first use. One-time cost.
- The sibling-folders model means a `git status` from `/volume1/pandya-homelab/` shows the repo state, but the data folders are invisible (correctly, via `.gitignore`). Operators must remember that runtime state lives adjacent to but outside the repo.

**Forecloses:**

- Per-container UID isolation. If a future demo legitimately needs to run as a different user (e.g., a database container with its own postgres UID by default), the convention must be deliberately overridden, with documentation. The default is uniformity.
- Synology Container Manager GUI workflows that assume `/volume1/docker/`. Manual compose project creation through Container Manager pointing at `/volume1/pandya-homelab/compose/` works; the GUI's default-folder shortcuts do not.
- World-readable platform files. Anyone outside the operator and the `homelab` group cannot read platform code or runtime state on the NAS filesystem. (Public-facing services are still public via Nginx; this is about NAS filesystem access.)

## Implementation reference

This ADR governs the filesystem setup steps in the Stage 2 → Implementation Transition Plan (Phase 3 and Phase 7). Concrete actions:

1. **Create the dedicated group:**
   ```bash
   sudo synogroup --add homelab
   sudo synogroup --member homelab <operator-user>
   ```

2. **Create the parent folder with correct ownership:**
   ```bash
   sudo mkdir -p /volume1/pandya-homelab
   sudo chown <operator-user>:homelab /volume1/pandya-homelab
   sudo chmod 750 /volume1/pandya-homelab
   ```

3. **Clone the monorepo into the parent folder** (per ADR-008 Phase 5 of the Transition Plan).

4. **Create the data folders:**
   ```bash
   mkdir /volume1/pandya-homelab/data-dev-nas
   mkdir /volume1/pandya-homelab/data-prod-nas
   chmod 750 /volume1/pandya-homelab/data-{dev,prod}-nas
   ```

5. **Add data folders and .env to `.gitignore`** in the cloned repo:
   ```
   data-dev-nas/
   data-prod-nas/
   .env
   ```

6. **In compose files**, declare the `user` directive reading from environment:
   ```yaml
   services:
     iris-knn:
       user: "${HOST_UID}:${HOST_GID}"
       volumes:
         - ../services/ml/classification/iris-knn/app:/app:ro    # read-only source
         - ../data-dev-nas/iris-knn:/data:rw                      # read-write data (dev-nas overlay)
   ```

7. **In `.env.example`**, document the required env vars:
   ```
   HOST_UID=1026
   HOST_GID=100
   ```

8. **Operator's actual `.env`** (not committed) sets the values for their specific UID/GID, obtained via `id -u` and `id -g` after SSHing in.

These actions complete the runtime filesystem setup for both `dev-nas` and `prod-nas` stacks.

## Related ADRs

- **ADR-001** — establishes trust boundaries that this ADR enforces at the filesystem level (cross-stack writes forbidden)
- **ADR-002** — establishes platform-agnosticism that explains why `/volume1/` paths do not appear in source code
- **ADR-006** — Nginx config in `platform/proxy/` is read-only mounted, per the rules in this ADR
- **ADR-007** — establishes the layout that this ADR places into a runtime location
- **ADR-008** — establishes that there is one repo to clone, simplifying this ADR's filesystem decisions
- **ADR-010** (queued) — secrets management; specifies what goes in `.env` and how containers consume it
- **ADR-011** (queued) — per-service conventions; should require Dockerfiles to honor the `USER` directive pattern established here
- **ADR-012** (queued) — authentication strategy

## Related working memos

- **Stage 2 Working Environment Memo** — establishes Mode B-prime, the B1 source tree pattern, and the dev-nas/prod-nas stack model that this ADR's filesystem rules implement
- **Stage 2 Security Map** — concern #5 (filesystem permissions) is now fully addressed by this ADR
- **Stage 2 Transition Plan** — Phase 3 (create platform repo) and Phase 7 (archive deliberation workspace) reference the filesystem rules locked here
- **Stage 2 Consolidation Memo** — context on the deliberation that led here
