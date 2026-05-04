# ADR-010: Synology secrets management

**Status:** Accepted
**Date:** May 2026
**Stage:** 2 (Synology Implementation)

## Context

Containers running in pandyaHomeLab need credentials to function — Postgres database passwords, MinIO root credentials, MLflow tokens (if applicable), API keys for external services, and similar values that must be available at runtime but cannot be committed to Git. ADR-009 settled where the platform lives on disk and excluded `.env` from Git, but stopped short of specifying *how* the .env mechanism is structured, *how* secret values are generated, and *how* they are protected against NAS loss.

This ADR resolves those three questions for the NAS side. AWS-side secrets management is a Stage 4 concern, deliberately deferred.

A secret is any value that, if exposed, would compromise either the platform's integrity or the privacy of any data flowing through it. The canonical examples for pandyaHomeLab:

- **Postgres database passwords** — both for `dev-nas` and `prod-nas` databases
- **MinIO root credentials** — for the artifact store, both stacks
- **MLflow basic auth credentials** — if MLflow's authentication is enabled
- **External API keys** — model APIs, monitoring services, future integrations
- **GitHub deploy tokens** — when CI/CD eventually pushes images (Stage 3 concern but worth anticipating)

The decision is not made in a vacuum. Several constraints carry forward:

- **`.env` is not committed to Git** (ADR-009) — secrets live in `.env`, not in source files.
- **`dev-nas` and `prod-nas` run as separate stacks** (Working Environment memo) — their secrets must not be reusable across stacks (a leaked dev password should not unlock prod).
- **Mode B-prime: operator manages everything via SSH** (Working Environment memo) — secret operations happen at the NAS shell, not via external tooling that requires network calls or vault auth.
- **Single operator** — no team-secret-sharing problem to solve. The operator's own discipline is the security boundary.
- **Containers run as the operator's UID** (ADR-009) — the operator can read and write `.env` files directly, with no permission friction.
- **AWS deploys a subset, with its own secret model** (Working Environment memo) — AWS Secrets Manager handles AWS-side secrets, and the NAS-side mechanism does not need to be AWS-compatible.

The decision must address two competing concerns. Secrets are valuable enough that they warrant careful handling — encryption at rest, controlled access, no leakage via Git or logs. They are also operational reality that must not become so cumbersome that the operator works around them. The right level is "appropriate for a single-operator portfolio platform with public exposure," which is more than "plain text passwords in source files" but considerably less than "HashiCorp Vault with audit logs."

The principle that resolves this scope: **secrets are values, not code. They are environment-specific, not platform-specific. They flow through environment variables, never through committed files.** This is the [Twelve-Factor App](https://12factor.net/config) configuration principle applied specifically to credentials — the same code, the same images, the same deployment artifacts; only the values injected at runtime differ.

## Decision

**pandyaHomeLab uses two `.env` files on the NAS — one per stack — to hold environment-specific secret values. Secrets are generated manually by the operator using a password manager as the canonical store, with the `.env` files acting as the deployed copies. The mechanism is loaded by docker-compose via `--env-file`, and AWS-side secret management is deferred to Stage 4.**

### File structure and locations

```
/volume1/pandya-homelab/
├── (cloned monorepo per ADR-007 and ADR-008)
├── data-dev-nas/
├── data-prod-nas/
├── .env.dev-nas              # secrets for dev-nas stack (NOT committed)
└── .env.prod-nas             # secrets for prod-nas stack (NOT committed)
```

Both files live as siblings to the data folders per ADR-009's filesystem layout. Each file is owned by the operator's user with permissions `600` (owner read/write only — stricter than the parent folder's `750`, because secrets warrant their own access boundary).

The repository contains a third file — `compose/.env.example` — which is **committed to Git** and documents every required environment variable with placeholder values. It serves as the contract: any developer or future-self looking at the repo can see what variables must be defined, even though the actual values are never present.

### Variable naming convention

The two `.env` files use **identical variable names** within their respective stacks. There is no `DEV_` or `PROD_` prefix. A `POSTGRES_PASSWORD` in `.env.dev-nas` and a `POSTGRES_PASSWORD` in `.env.prod-nas` are different values, but both inject as `POSTGRES_PASSWORD` into their respective stacks.

This is deliberate. Compose semantics flow naturally: `docker compose --env-file .env.dev-nas ...` injects dev-nas values; the same compose file with `--env-file .env.prod-nas` injects prod-nas values. Application code, Dockerfiles, and compose declarations need not know which stack they are running in — they simply consume `POSTGRES_PASSWORD` from their environment.

A prefixed-key alternative was considered and rejected (see Alternatives).

### Compose loading mechanism

Compose commands explicitly specify the env file:

```bash
# Bring up dev-nas
docker compose \
    --env-file /volume1/pandya-homelab/.env.dev-nas \
    -p homelab-dev-nas \
    -f compose/docker-compose.platform.yml \
    -f compose/docker-compose.yml \
    -f compose/docker-compose.dev-nas.yml \
    up -d

# Bring up prod-nas
docker compose \
    --env-file /volume1/pandya-homelab/.env.prod-nas \
    -p homelab-prod-nas \
    -f compose/docker-compose.platform.yml \
    -f compose/docker-compose.yml \
    -f compose/docker-compose.prod-nas.yml \
    up -d
```

This verbosity is absorbed by wrapper scripts (`make up-dev-nas`, `make up-prod-nas`) per the working environment memo. The operator does not type the long form interactively; they invoke wrappers that select the correct env file along with the correct overlay.

### Secret generation

Secret values are generated **manually by the operator** using whichever password generator the operator prefers (`openssl rand -base64 32`, `pwgen`, the password manager's built-in generator). Generation happens once per secret at the time the operator first stands up the corresponding service.

The choice of manual generation is deliberate. Auto-generation at first container start was considered but rejected because:
- It complicates the bootstrap sequence (a container that owns its own password can be hard to recover credentials from later)
- The operator must capture the auto-generated value somewhere anyway, defeating the supposed simplicity
- For a single-operator platform with at most ~15-20 secrets across both stacks, manual generation is an afternoon's work, total

Each secret is generated at sufficient strength for its role:
- Database and service passwords: at least 32 characters, mixed case, digits, symbols
- API tokens: per the issuing service's recommended length

### Canonical storage and backup

The **password manager** (Bitwarden, 1Password, Apple Keychain, or equivalent) is the canonical store for every secret. Each secret has an entry in the password manager, organized by stack:

```
pandyahomelab/dev-nas/postgres-password
pandyahomelab/dev-nas/minio-root-password
...
pandyahomelab/prod-nas/postgres-password
pandyahomelab/prod-nas/minio-root-password
...
```

The `.env.dev-nas` and `.env.prod-nas` files on the NAS are **deployed copies** of these canonical values. They exist on the NAS so that compose can read them; they are not the source of truth.

This means:
- **Disaster recovery from NAS failure** is straightforward: provision a new NAS, recreate the .env files by copying values from the password manager.
- **Backup discipline does not apply to .env files.** Hyper Backup explicitly excludes them. Backing up .env files would put plaintext secrets in backup destinations (USB drive, cloud) — an unnecessary expansion of the secrets' attack surface.
- **Secret rotation has a clean workflow:** update the canonical entry in the password manager, regenerate the .env file by copying values, restart the affected stack to pick up new values.

### Secret rotation

Rotation is operator-initiated and follows a fixed sequence:

1. Generate new value in password manager
2. Update canonical entry there
3. Update the corresponding line in the relevant `.env.<stack>-nas` file
4. Restart the affected service (`docker compose ... up -d <service>` is enough; full stack restart is not required)
5. Verify the service is healthy with the new credential

There is no automated rotation cadence. Rotation is reactive (suspected compromise, departing collaborator, etc.) rather than scheduled. For a single-operator portfolio platform, scheduled rotation is more risk-introducing than risk-mitigating.

### AWS-side handling

AWS deployments do not read `.env` files. The Stage 4 ADR will specify AWS Secrets Manager (or AWS Systems Manager Parameter Store) as the canonical mechanism for AWS-side credentials. The NAS-side mechanism in this ADR does not need to be compatible with AWS-side mechanisms — they serve different runtime environments with different credential models.

A single secret may exist in both worlds (e.g., a `pandyahomelab.com` TLS certificate that protects both NAS and AWS Nginx deployments). In that case, the password manager remains the canonical store; both AWS Secrets Manager and the NAS `.env` file receive copies. This forward-references Stage 4 work without locking it.

## Alternatives considered

**Single `.env` file with prefixed keys (rejected).** A single `/volume1/pandya-homelab/.env` containing both stacks' secrets, distinguished by `DEV_` and `PROD_` prefixes (e.g., `DEV_POSTGRES_PASSWORD` and `PROD_POSTGRES_PASSWORD`). Compose overlays would map them: `dev-nas.yml` references `${DEV_POSTGRES_PASSWORD}` and uses it as `POSTGRES_PASSWORD` inside the container.

Rejected for three reasons:

- **Mental overhead.** Every variable carries a stack prefix that has nothing to do with the variable's actual purpose. Reading the file means constantly translating "DEV_POSTGRES_PASSWORD" to "the dev-nas Postgres password" rather than seeing it directly.
- **Larger blast radius.** A leak or an inadvertent screen-share of the single .env file leaks both stacks' secrets simultaneously.
- **Compose ergonomics.** Compose's native `--env-file` flag is designed for one file per environment. Working with prefixed keys in a single file requires more careful overlay structure.

The two-files approach is genuinely cleaner at single-operator scale.

**Docker compose secrets (rejected).** Compose has a built-in `secrets:` mechanism: secrets are declared as files, mounted into containers at `/run/secrets/<name>`, and read by application code from there. This is a "more proper" secret-handling pattern than env vars.

Rejected because:
- Most container images expect credentials via environment variables, not via files at `/run/secrets/`. Adopting the secrets pattern would require either custom entry-point scripts or modifying upstream images.
- The security benefit (env vars are visible in `docker inspect`; files at `/run/secrets/` are not) is real but small for a single-operator platform with no shared admin access.
- Operational complexity is higher — every service needs explicit `secrets:` declarations in compose, plus a startup pattern that reads from the file.

The pattern earns its place in multi-tenant production deployments where multiple admins might inspect running containers. For pandyaHomeLab, env vars are sufficient.

**External vault (HashiCorp Vault or similar) (rejected).** Run a Vault container as part of the platform; all other containers fetch secrets from Vault at startup using short-lived tokens. Industry-standard for production-scale deployments with audit and rotation requirements.

Rejected as massive overkill for a single-operator portfolio platform. Vault setup, unsealing rituals, token management, and the Vault container's own secrets bootstrapping problem (how does Vault itself get unlocked at startup?) all add complexity without delivering value at this scale. If pandyaHomeLab ever grows to require multi-user secret access with audit trails, a future ADR can introduce Vault by superseding this one.

**Auto-generated secrets at first container start (rejected).** The container itself runs `pwgen` or equivalent on first boot, stores the generated password somewhere, and uses it. Removes the operator from the secret-generation step.

Rejected because:
- The operator must still capture the auto-generated value somewhere (to reach the database via psql, to recover after a container restart, etc.). The "automation" is illusory — it shifts work from generation to recovery.
- Auto-generation hides the bootstrap timing. If a container regenerates its password on every restart (a common bug), persistent state breaks.
- The pattern requires Dockerfile customization for every service that uses a database or credential, increasing per-service complexity.

Manual generation at the operator's password manager keeps the canonical store and the deployed copy synchronized by the operator's own care.

**Backing up `.env` files via Hyper Backup (rejected).** Including `.env.dev-nas` and `.env.prod-nas` in the regular NAS backup means backup destinations (USB drive, cloud storage) end up with plaintext secrets.

Rejected because:
- Backup destinations have a different (often weaker) security posture than the NAS itself. A USB drive in a desk drawer is not as protected as the NAS sitting behind firewall and DSM authentication.
- Cloud backup destinations introduce additional attack surface (the cloud provider's credentials, transport encryption, etc.).
- The password manager already serves as the canonical store and is itself backed up by its provider with hardened security. Duplicating secrets into NAS backups is redundant for recovery while expanding leak surface.

The clean separation is: NAS holds operational copies, password manager holds canonical values. Backups treat the platform's `.env` files as recreatable from the password manager, not as data to preserve.

## Consequences

**Positive:**

- The two-file structure makes stack isolation tangible. There is no point at which a `dev-nas` secret accidentally flows into `prod-nas`, because the file paths are different and compose loads them explicitly.
- The password manager as canonical store solves disaster recovery cleanly. Even total NAS loss does not lose secrets — they live in an independent system already designed for credential durability.
- Variable naming is uncluttered. `POSTGRES_PASSWORD` means what it says inside any container; the stack context comes from the file that was loaded, not from a prefix on the variable.
- Compose semantics flow naturally with `--env-file`. No custom scripting required to wire stacks to their secrets.
- The `.env.example` file in the repo serves as living documentation. Anyone (including future-self) can see what variables must be defined to run the platform, without ever seeing real values.
- Permission scoping (`600` on the .env files, owned by operator) means even other processes running as the operator's user cannot read .env files unless they explicitly open those files (no broad readability).
- Forward compatibility with AWS Secrets Manager is clean. The Stage 4 work for AWS adds a new mechanism for that environment without requiring changes to NAS-side handling.

**Negative (trade-offs accepted):**

- The operator must maintain discipline. Two files to keep current with the password manager. A drift between password-manager state and .env state is possible if the operator forgets to update one after rotating the other.
- Wrapper scripts become essential. The compose commands with `--env-file` are too long for routine typing. If wrapper scripts (`make up-dev-nas`) drift out of sync with the actual file paths, operations get awkward.
- No automatic rotation. Secrets can sit unchanged for years if the operator does not actively rotate them. For a portfolio platform with no compliance requirements, this is acceptable; for a regulated environment it would not be.
- No audit trail of secret access. There is no log of "this container read this secret at this time." Vault offers this; .env files do not. Acceptable for single-operator scope; unacceptable for multi-user.
- Secrets are visible to any process running as the operator's user via `cat /volume1/pandya-homelab/.env.prod-nas`. This is the same threat model as files written under any user account on any Unix system; operator discipline is the boundary.
- Compose `docker inspect` exposes injected env vars on running containers to anyone with Docker socket access. Mitigated because Docker socket access is gated by the operator's user, but worth knowing.

**Forecloses:**

- Per-service unique secret rotation cadences. All services using a given .env file rotate together (because rotation rewrites the file). Different cadences would require different mechanisms.
- Secret access by non-operator processes. A backup agent cannot read .env without being granted access to the operator's group or user. This is by design; expanding access is a future ADR.
- Compose-mode secrets (the `secrets:` directive in compose files). This ADR locks env-var-based injection. Adopting compose secrets would supersede this ADR.

## Implementation reference

This ADR governs secret-related setup steps in the Stage 2 → Implementation Transition Plan and ongoing operational discipline. Concrete actions:

1. **In the password manager**, create entries organized by stack:
   ```
   pandyahomelab/dev-nas/postgres-password
   pandyahomelab/dev-nas/minio-root-password
   pandyahomelab/dev-nas/minio-root-user
   pandyahomelab/dev-nas/mlflow-tracking-username
   pandyahomelab/dev-nas/mlflow-tracking-password
   pandyahomelab/prod-nas/postgres-password
   pandyahomelab/prod-nas/minio-root-password
   pandyahomelab/prod-nas/minio-root-user
   pandyahomelab/prod-nas/mlflow-tracking-username
   pandyahomelab/prod-nas/mlflow-tracking-password
   ```
   (Adjust as services are added.)

2. **Generate strong values for each entry.** A 32-character base64 string is sufficient for most: `openssl rand -base64 32`. Use the password manager's generator if preferred.

3. **On the NAS, create the .env files:**
   ```bash
   touch /volume1/pandya-homelab/.env.dev-nas
   touch /volume1/pandya-homelab/.env.prod-nas
   chmod 600 /volume1/pandya-homelab/.env.dev-nas
   chmod 600 /volume1/pandya-homelab/.env.prod-nas
   ```

4. **Populate each .env file** by copying values from the password manager:
   ```
   # /volume1/pandya-homelab/.env.dev-nas
   POSTGRES_PASSWORD=<value-from-password-manager>
   MINIO_ROOT_USER=<value-from-password-manager>
   MINIO_ROOT_PASSWORD=<value-from-password-manager>
   ...
   HOST_UID=1026
   HOST_GID=100
   ```
   (HOST_UID/GID per ADR-009, repeating in both .env files because they are environment values, not secrets.)

5. **In the repo, commit `compose/.env.example`** documenting every required variable with placeholder values:
   ```
   # compose/.env.example — committed to Git
   POSTGRES_PASSWORD=replace-with-strong-password
   MINIO_ROOT_USER=replace-with-username
   MINIO_ROOT_PASSWORD=replace-with-strong-password
   ...
   HOST_UID=
   HOST_GID=
   ```

6. **Add wrapper scripts (in the repo)** that load the right env file for the right stack:
   ```bash
   # scripts/up-dev-nas.sh — committed to Git
   docker compose \
       --env-file /volume1/pandya-homelab/.env.dev-nas \
       -p homelab-dev-nas \
       -f compose/docker-compose.platform.yml \
       -f compose/docker-compose.yml \
       -f compose/docker-compose.dev-nas.yml \
       up -d "$@"
   ```
   (Equivalent for prod-nas. Or a single `Makefile` with `up-dev-nas` and `up-prod-nas` targets.)

7. **In Hyper Backup configuration**, exclude `.env*` files from the backup destination. Verify with a test backup that .env files do not appear in the backup target.

8. **In `.gitignore`** (per ADR-009), ensure these patterns are present:
   ```
   .env
   .env.dev-nas
   .env.prod-nas
   ```

These actions complete the secrets infrastructure for both stacks.

## Related ADRs

- **ADR-001** — establishes trust boundaries that this ADR enforces by forbidding cross-stack secret reuse
- **ADR-007** — establishes the layout that this ADR's `compose/.env.example` documentation slots into
- **ADR-008** — establishes the single repo where `.env.example` lives and `.env` files are gitignored
- **ADR-009** — establishes the filesystem location where .env files live, plus the operator-UID convention that lets containers consume secrets without permission friction
- **ADR-011** (queued) — per-service conventions; should require Dockerfiles and compose entries to consume credentials via environment variables exclusively
- **ADR-012** (queued) — authentication strategy; the auth credentials it establishes will be stored per this ADR's mechanism

## Related working memos

- **Stage 2 Working Environment Memo** — establishes the dev-nas/prod-nas stack model that this ADR's two-file approach implements; specifies wrapper scripts as the operational interface
- **Stage 2 Security Map** — concern #6 (secrets management) is fully addressed by this ADR
- **Stage 2 Transition Plan** — Phase 4 (seed platform repo) and Phase 8 (implementation begins) reference the secret setup steps locked here
- **Stage 2 Consolidation Memo** — context on the deliberation that led here
