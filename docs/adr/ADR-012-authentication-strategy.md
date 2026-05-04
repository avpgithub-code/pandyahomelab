# ADR-012: Authentication strategy

**Status:** Accepted
**Date:** May 2026
**Stage:** 2 (Synology Implementation)

## Context

ADR-005 (path-based routing) foreshadowed authentication as a future concern, listing "a demo requires authentication beyond Basic Auth" as one of three triggers that would supersede the path-based routing model. The Stage 2 Security Map names authentication as concern #3 with the trigger note: *"becomes urgent in mid-Stage-2 when MLflow/Grafana/MinIO need public exposure."* That trigger is now being addressed.

The decision answers three questions:

1. *Which platform resources are publicly reachable at all?*
2. *For those that are, what authentication mechanism guards them?*
3. *Is there a pattern for per-demo authentication, even if no current demo uses it?*

The architectural context that bears on these questions:

- **`prod-nas` Nginx serves the public domain at `pandyahomelab.com`** (per ADR-006). Every public URL is mediated by this Nginx.
- **Operational UIs (MLflow, Grafana, MinIO console) run on the `mlops-network` and `data-network`** (per ADR-001). They have no inherent public exposure unless explicitly proxied by Nginx.
- **Demos run on per-domain networks and are publicly exposed via path-based routing** (per ADR-003 and ADR-005). They are designed to be reached without friction.
- **`dev-nas` is LAN-only** (per the Working Environment memo). Authentication concerns there are reduced because LAN presence already gates access.
- **AWS deployment is a minimal serving layer** (per the Working Environment memo). It contains no operational UIs — no MLflow, no Grafana, no MinIO console — so AWS-side authentication concerns are limited to demos.
- **The site is the portfolio** (per ADR-008's framing). Visitor friction at the demo level reduces portfolio value.
- **Cookies on `pandyahomelab.com` are scoped to the entire origin** (per ADR-005). Authentication cookies must follow the per-container prefix rule from ADR-011.

Two distinct audiences need different treatment:

- **Visitors** (recruiters, curious people, fellow learners) interact with demos. They should reach them with zero friction. Authentication on demos defeats the portfolio's primary value.
- **The operator** (just me, in single-operator scope) manages the platform and consumes operational UIs. These should be inaccessible to anyone else — not because they reveal sensitive data, but because operational UIs at unauthenticated public endpoints are an open invitation to scanners and bots.

The principle that resolves this scope: **authentication exists to protect specific resources, not to gatekeep the platform's public face.** Demos stay open. Operational tooling stays closed. The mechanism that closes operational tooling is the architectural decision.

## Decision

**All operational UIs (MLflow, Grafana, MinIO console, and any future operational tooling) are LAN-only and not publicly reachable. Demos remain publicly accessible without authentication. HTTP Basic Auth at Nginx is established as the platform's authentication mechanism, available for any future resource (operational UI ever exposed publicly, or any demo requiring per-demo authentication) without further architectural deliberation.**

The decision has three parts: how operational UIs are protected (LAN-only), what mechanism is available when authentication is needed (Basic Auth at Nginx), and how the pattern extends to demos when needed (deferred per-demo authentication, with the pattern documented but not currently enforced).

### Part 1 — Operational UIs are LAN-only

MLflow, Grafana, and the MinIO console are reachable **only from inside the home LAN** at `192.168.1.152:<port>`. Specifically:

- They are **not** proxied by Nginx onto the public domain
- They are **not** assigned subdomains (`mlflow.pandyahomelab.com` etc. do not exist)
- They are **not** included in any public DNS records
- They run on Docker networks (`mlops-network`, `data-network`) that are not accessible from outside the NAS

Operator access is via direct LAN URLs:

- MLflow: `http://192.168.1.152:5000` (or whichever port is assigned)
- Grafana: `http://192.168.1.152:3000`
- MinIO console: `http://192.168.1.152:9001`

These URLs work from any device on the home network. They do not work from outside.

When operational UIs need to be shown to others (during a job interview, a portfolio review, or remote troubleshooting), this is done via screen-share rather than public exposure. The operator drives; the audience watches. This is a deliberate trade-off: a small friction during occasional showcase events, in exchange for zero attack surface on operational tooling.

### Part 2 — Basic Auth at Nginx is the available mechanism

When authentication is needed for any resource — a future operational UI exposed publicly, a demo requiring authentication, or anything else — the mechanism is **HTTP Basic Auth implemented at the Nginx layer**.

The implementation pattern:

- Nginx's `auth_basic` and `auth_basic_user_file` directives gate the protected location
- Credentials are stored in an `htpasswd` file at a known location on the NAS, outside the repo
- The `htpasswd` file is generated using `openssl passwd -apr1` or `htpasswd` and committed nowhere
- The credential pair (username and password) is canonical-stored in the operator's password manager (per ADR-010)
- The credential pair is replicated to the htpasswd file on the NAS, and to `prod-aws` if any AWS resource ever needs the same auth

Example Nginx configuration for a hypothetical protected location:

```nginx
location /admin/ {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/auth/htpasswd;

    proxy_pass http://upstream-service:port/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Prefix /admin;
    # ... other proxy headers
}
```

The pattern is uniform: any location block can be protected by adding two `auth_basic*` directives. No application-level changes required for the protected service. The protection happens at the platform edge.

### Part 3 — Per-demo authentication pattern (anticipated, deferred)

Most demos are stateless inference (input → model → output) and require no authentication. Visitors reach `/ml/classification/iris-knn` and use it freely. This is the desired posture and is not changing.

However, future demos may legitimately need authentication. Possible cases:
- A demo that processes user-uploaded private documents
- A demo that maintains user-specific state across requests
- A demo that exposes personal data the operator does not want indexed

For these cases, the pattern is **the same Basic Auth mechanism applied per-demo at the Nginx location block**. A demo at `/ml/classification/secret-demo` would have its Nginx route extended with the `auth_basic` directives, plus its own `htpasswd` entry distinct from any platform-wide credential.

The pattern is documented here so that when the first demo needing authentication arrives, no architectural deliberation is needed. The operator extends the demo's Nginx route with `auth_basic`, generates a new credential pair, and proceeds. The demo itself does not need to be aware of authentication — Nginx handles it transparently.

The cookie-collision concern from ADR-005 and ADR-011 (cookies on the shared origin) does not apply to Basic Auth because Basic Auth uses HTTP headers, not cookies. This is a small but real architectural property: the Basic Auth mechanism is path-routing-compatible without colliding with anything else on the origin.

If a future demo needs richer authentication (OAuth, multi-user, role-based), that will be a different ADR superseding this one in the relevant scope. This ADR establishes Basic Auth as the platform's *current* authentication mechanism, not the only conceivable one.

### Credential storage and lifecycle

Per ADR-010, all credentials are canonically stored in the operator's password manager. The htpasswd file on the NAS is the deployed copy. Disaster recovery means recreating the htpasswd file from the password manager, not restoring from backup.

For the operator-side credential (the one that protects the LAN-only UIs *if* they ever become publicly exposed, or the one that protects future authenticated demos):

- One credential pair, named `pandyahomelab-admin` in the password manager
- Stored at `/volume1/pandya-homelab/.htpasswd` on the NAS, with `chmod 600` ownership by the operator user
- Excluded from Git via `.gitignore` (extending the patterns from ADR-009 and ADR-010)
- Excluded from Hyper Backup (per ADR-010's reasoning — credentials in backups expand attack surface)

For demo-specific credentials (when a demo ever needs them):

- Per-demo credential pair, named `pandyahomelab-demo-<demoname>` in the password manager
- Stored at `/volume1/pandya-homelab/.htpasswd-<demoname>` or similar per-demo file
- Same exclusions

### What this ADR does NOT lock

This ADR is deliberately silent on:

- **OAuth, SSO, or federated authentication.** Out of scope for single-operator. A future ADR can add these if the platform ever has multiple authenticated users.
- **TLS automation for `htpasswd` transport.** All Basic Auth happens behind TLS (per ADR-006), so credentials in transit are encrypted. The TLS automation itself is a Stage 5 concern.
- **Audit logging of authentication events.** Nginx logs include enough to reconstruct auth attempts, but no formal audit log infrastructure exists. Future Stage 4+ concern.
- **Rate limiting and brute-force protection.** Nginx's `limit_req` module can be added to protected locations, but this is implementation detail rather than architectural decision.
- **Multi-factor authentication.** Not relevant at single-operator scale; would be a future ADR.

These omissions are intentional. The platform now has *enough* authentication to protect what needs protecting. More elaborate authentication would be premature.

## Alternatives considered

**Operational UIs publicly reachable, all behind authentication (rejected).** Subdomains like `mlflow.pandyahomelab.com` and `grafana.pandyahomelab.com`, all gated by Basic Auth. Rejected because the marginal value of public access is low (occasional screen-share substitutes work fine) while the cost is real (additional attack surface, every UI must be hardened against scanners that find it, ongoing maintenance of multiple authenticated public endpoints). LAN-only is simpler, more secure, and sufficient.

**Mixed exposure (operational UIs partially public) (rejected).** Expose MLflow publicly (with auth) as part of the portfolio narrative — "here's my training history, with run comparisons" — while keeping Grafana and MinIO LAN-only. Rejected because it asks for ongoing decisions about which UI is "portfolio-worthy" and creates an inconsistent posture. The screen-share alternative serves the same portfolio narrative without any public exposure. If at some future moment a public MLflow becomes specifically valuable, a future ADR can supersede this one for that one resource.

**Application-level authentication in each tool (rejected as primary mechanism).** Configure MLflow's built-in auth, Grafana's built-in auth, and MinIO's IAM independently. Each tool has different credential conventions, different audit posture, different rotation procedures. Rejected because Basic Auth at Nginx provides uniform protection at the platform edge, with one credential pair, one configuration model, one rotation procedure. If specific tools ever need their internal auth (e.g., MLflow with multi-user fine-grained permissions), they can be enabled in addition to Nginx Basic Auth — but the platform-edge protection remains the primary mechanism.

**OAuth (GitHub, Google, etc.) as the primary mechanism (rejected).** More polished from a user experience perspective. Rejected for single-operator scope: the implementation complexity (registering an OAuth app, handling redirect URLs, managing tokens, handling refresh) vastly exceeds the value when there is exactly one user. OAuth becomes appropriate when there are multiple authenticated users with externally-managed identities.

**No authentication at all (rejected).** Leave operational UIs publicly reachable without authentication. Rejected for obvious reasons — public unauthenticated MLflow exposes training history; public unauthenticated MinIO exposes artifacts; public unauthenticated Grafana exposes operational metrics. Even if no individual exposure is catastrophic, the cumulative posture is unacceptable for any platform with public DNS.

**Per-demo authentication mandated for all demos (rejected).** Require every demo to be behind authentication "for safety." Rejected because it defeats the portfolio's primary value. A potential employer who has to log in to try `iris-knn` will not bother. Demos must remain frictionless; authentication is opt-in per demo when the demo's content genuinely needs it.

## Consequences

**Positive:**

- Operational UIs have zero public attack surface. Scanners cannot find them; bots cannot probe them; the only path to MLflow is "be on the home LAN."
- Demos remain frictionless. Visitors interact with `/ml/classification/iris-knn` and any future demo with a single click — no login, no friction, no abandoned visitors.
- The authentication mechanism is uniform. Basic Auth at Nginx works for any future need (a public-exposed UI, a demo requiring auth, an admin endpoint) without further architectural deliberation.
- Credential management is consistent with ADR-010. One credential pattern (htpasswd file, password-manager-canonical) extends naturally to authentication.
- The pattern is path-routing-compatible. Basic Auth uses headers, not cookies, so the cookie collision concerns from ADR-005 and ADR-011 do not apply here.
- The trade-off (LAN-only operational UIs require screen-share for showcase) is well-defined and acceptable for portfolio scale.
- Future authentication needs (per-demo auth, additional admin endpoints) have a documented pattern with no architectural barrier to implementation.

**Negative (trade-offs accepted):**

- Showing operational UIs to others requires screen-share or being physically present on the LAN. For occasional portfolio demonstrations, this is small friction; for routine remote sharing, it would be limiting.
- Basic Auth has well-known limitations: no logout (browser caches credentials until close), no fine-grained permissions, no audit log of who authenticated when. Acceptable at single-operator scale; would be unacceptable in a multi-user system.
- The htpasswd file is operator-managed. If credentials are forgotten (and not in the password manager), recovery is "regenerate htpasswd, restart Nginx." This is fast but disruptive.
- LAN-only operational UIs cannot be reached when the operator is traveling without VPN. Mitigated by SSH tunneling (`ssh -L 5000:localhost:5000`) but adds a step to remote troubleshooting.
- Browser Basic Auth dialogs are ugly. They cannot be styled. For occasional admin access, this is a non-issue; for any visitor-facing scenario, it would feel unprofessional.
- A future demo requiring something more sophisticated than Basic Auth (OAuth, multi-tenant auth) cannot be added to the existing architecture without superseding this ADR.

**Forecloses:**

- Public exposure of MLflow, Grafana, and MinIO. They are LAN-only by this ADR. Changing this requires a new ADR.
- Application-level authentication as the primary platform mechanism. Tools may use their internal auth in *addition* to Nginx Basic Auth, but Nginx Basic Auth is the architectural primary.
- Cookie-based authentication for any platform-managed resource. Path-routing concerns make cookie-based auth on the shared origin painful; Basic Auth (header-based) sidesteps this.
- Anonymous access to operational tooling. There is no anonymous read path for MLflow, Grafana, or MinIO from outside the LAN.

## Implementation reference

This ADR governs authentication-related setup steps in the Stage 2 → Implementation Transition Plan and ongoing operations.

**For the LAN-only operational UIs:**

1. Configure each UI to bind to the NAS IP at its assigned port (e.g., MLflow on `192.168.1.152:5000`).
2. Verify each UI is **not** routed by Nginx — its hostname does not appear in any `server_name` directive in `prod-nas` Nginx config.
3. Document the LAN URLs in the platform README so the operator (and future-self) knows where to find each UI.

**For the Basic Auth mechanism (when needed):**

1. Generate the credential in the password manager (`pandyahomelab-admin`):
   ```
   Username: admin
   Password: (32-char generated)
   ```
2. Create the htpasswd file on the NAS:
   ```bash
   htpasswd -c /volume1/pandya-homelab/.htpasswd admin
   # (paste password from password manager)
   chmod 600 /volume1/pandya-homelab/.htpasswd
   ```
3. Verify the file is in `.gitignore` (per ADR-009 and ADR-010 patterns):
   ```
   .htpasswd
   .htpasswd-*
   ```
4. Verify the file is excluded from Hyper Backup.

**When a future resource needs authentication:**

5. Add `auth_basic` and `auth_basic_user_file` directives to the resource's Nginx location block:
   ```nginx
   location /protected-thing/ {
       auth_basic "Restricted";
       auth_basic_user_file /etc/nginx/auth/htpasswd;
       proxy_pass http://upstream/;
       # ... other proxy headers
   }
   ```
6. Verify Nginx has the htpasswd file mounted/readable (`/etc/nginx/auth/htpasswd` mapped from `/volume1/pandya-homelab/.htpasswd` via the proxy container's volume mounts, per ADR-009's mount conventions).
7. Reload Nginx: `docker compose ... exec nginx nginx -s reload`.

**For per-demo authentication (when a demo needs it):**

8. Generate a demo-specific credential pair in the password manager (`pandyahomelab-demo-<demoname>`).
9. Create a per-demo htpasswd file (e.g., `/volume1/pandya-homelab/.htpasswd-<demoname>`).
10. Reference the per-demo file in the demo's Nginx location block.
11. Document the credential in the demo's `README.md` (without the password — just noting that auth is required and where the credential is stored).

## Related ADRs

- **ADR-001** — establishes the network isolation that keeps operational UIs reachable only from internal Docker networks; the LAN-only choice extends this principle to NAS-host-network exposure
- **ADR-005** — foreshadowed authentication as a future concern; this ADR resolves the trigger
- **ADR-006** — establishes Nginx as the reverse proxy at which Basic Auth is implemented; TLS termination at Nginx ensures Basic Auth credentials travel encrypted
- **ADR-008** — establishes the single repo where the .gitignore patterns for htpasswd files live
- **ADR-009** — establishes filesystem permissions that protect the htpasswd file at rest
- **ADR-010** — establishes the password-manager-canonical pattern that extends to authentication credentials
- **ADR-011** — establishes the per-demo conventions; per-demo authentication (when needed) integrates with the contract there

## Related working memos

- **Stage 2 Working Environment Memo** — DNS structure (no `mlflow.*` or `grafana.*` subdomains) is consistent with the LAN-only decision here
- **Stage 2 Security Map** — concern #3 (authentication) is fully addressed by this ADR
- **Stage 2 Transition Plan** — Phase 8 (implementation begins) operationalizes this ADR; the htpasswd file is created when the first authenticated resource is needed
- **Stage 2 Consolidation Memo** — context on the deliberation that led here
