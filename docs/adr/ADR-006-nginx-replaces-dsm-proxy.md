# ADR-006: Custom Nginx replaces DSM reverse proxy on host ports

**Status:** Accepted
**Date:** April 2026
**Stage:** 1 (Conceptual Design)

## Context

The Synology NAS that hosts pandyaHomeLab (192.168.1.152) ships with DSM (DiskStation Manager), which includes its own built-in reverse proxy. The Fios router currently forwards public ports `80` and `443` to NAS host ports `8080` and `8443` respectively (DSM holds 5000/5001 for its own web UI).

Stage 1 introduces a custom Nginx container as the application reverse proxy. This created a question that needed an explicit answer: **how does the custom Nginx coexist with DSM's reverse proxy?**

Two viable paths emerged:

- **Path A — Replace:** Custom Nginx binds to host ports 8080/8443. DSM's reverse proxy is moved aside or disabled. One reverse proxy in the path.
- **Path B — Chain:** DSM's reverse proxy holds 8080/8443 and forwards specific hostnames to the custom Nginx on different host ports (e.g., 18080/18443). Two reverse proxies in series.

## Decision

**The custom Nginx container binds directly to host ports 8080 and 8443. DSM's reverse proxy is left out of the request path for `pandyahomelab.com`.**

DSM's web interface remains on its default ports (5000/5001) and is reachable on the LAN. The custom Nginx becomes the sole reverse proxy in the public traffic path. The Fios port forward continues to send public 80/443 to NAS 8080/8443; the only change is what listens on 8080/8443.

## Alternatives considered

**Path B — chain DSM in front of custom Nginx (rejected).** Two reverse proxies in series double the configuration surface, double the failure modes, and introduce an extra hop for every request. The arrangement only exists in real shops because nobody wanted to migrate, not because anyone designed it. Choosing Path A from day one avoids ever inheriting that complexity.

**Single reverse proxy = DSM only (rejected).** DSM's reverse proxy is a managed UI on top of Apache/Nginx with limited configurability. It cannot easily express the path-based routing patterns ADR-003 requires (deep prefixes, prefix stripping, per-container upstreams). The platform needs a fully programmable Nginx.

**Run Nginx on the host directly (not containerized) (rejected).** Defeats the goal of treating every component as a container. Host-level binaries break the IaC parity story between Synology and AWS — on AWS, the equivalent is an ECS task or Fargate service, which is containerized. Keeping Nginx in a container preserves the symmetry.

## Consequences

**Positive:**

- One reverse proxy in the path. Configuration lives entirely in `nginx.conf` files mounted into the container. Greppable, version-controlled, testable.
- The custom Nginx can be upgraded, restarted, or replaced without touching DSM. DSM updates do not affect the public traffic path.
- The architecture mirrors AWS cleanly — on AWS the equivalent is an ALB or a Fargate-hosted Nginx, both also single-layer.
- Configuration is portable: the same Nginx config works on Synology and on AWS with only the upstream addresses changing.

**Negative:**

- DSM's built-in reverse proxy UI features (visual rule editor, GUI for hostname rules) are unavailable for `pandyahomelab.com` traffic. All configuration is text-based. Acceptable trade-off for a platform engineering project.
- If Nginx misconfiguration breaks the public site, recovery requires SSH access to the NAS or DSM File Station to fix the config — there is no UI fallback. Mitigation: keep a known-good `nginx.conf` snapshot before every change; Stage 4 will add CI validation of Nginx configs before deployment.
- DSM's automatic Let's Encrypt cert management does not extend to the custom Nginx. TLS certificate automation must be implemented separately (Stage 5).

**Forecloses:**

- Using DSM's reverse proxy as a fallback when the custom Nginx is down is no longer trivial — they cannot both bind to 8080/8443 simultaneously. Mitigation: high availability is out of scope for a single-NAS Stage 1; the multi-AZ AWS deployment provides that property when needed.

## Implementation notes

- DSM web UI: continues to run on `https://192.168.1.152:5001`. Used for NAS admin only, not for `pandyahomelab.com` traffic.
- Custom Nginx container: binds host ports 8080 (HTTP) and 8443 (HTTPS). Listens for `pandyahomelab.com` and serves the four-level URL hierarchy from ADR-003.
- Fios port forwards: unchanged (`80 → 192.168.1.152:8080`, `443 → 192.168.1.152:8443`).
- DSM's built-in reverse proxy entries: leave configured but unused for `pandyahomelab.com`. Do not delete them — they may serve other internal NAS purposes.
