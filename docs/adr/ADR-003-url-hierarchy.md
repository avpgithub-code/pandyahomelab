# ADR-003: URL hierarchy uses four-level progressive disclosure

**Status:** Accepted
**Date:** April 2026
**Stage:** 1 (Conceptual Design)

## Context

pandyaHomeLab serves both static content (landing pages, domain overviews) and dynamic content (running model APIs) under a single domain (pandyahomelab.com). A user journey ranges from "what is this site" (broad orientation) to "let me try the iris classifier" (specific interactive demo).

The platform needed a URL scheme that would:
- Reflect how users actually move through the site (broad → narrow)
- Make routing predictable for the reverse proxy
- Make backend-service identity clear without forcing every container to know its public URL
- Scale to dozens of demos without forcing naming debates each time

## Decision

**URLs follow a four-level progressive disclosure hierarchy. Each level answers a different question at a different level of generality.**

| Level | URL pattern                                  | User question              | Served by                |
|-------|----------------------------------------------|----------------------------|--------------------------|
| L1    | `pandyahomelab.com/`                         | What is this site?         | Static `index.html`      |
| L2    | `/ml/  /dl/  /nlp/  /agentic/`               | What field am I in?        | Static domain HTML       |
| L3    | `/ml/classification/  /ml/regression/  ...`  | What problem am I solving? | Static technique HTML    |
| L4    | `/ml/classification/iris-knn`                | What demo am I about to use? | Running container       |

Levels 1-3 are static HTML files served directly by Nginx from a mounted volume. Level 4 is a running container behind an Nginx `proxy_pass` rule.

## Alternatives considered

**Pure subdomain-based (rejected for Stage 1).** Hosting each domain on its own subdomain (`ml.pandyahomelab.com`, `dl.pandyahomelab.com`) is structurally cleaner but requires either a wildcard TLS certificate (DNS-01 challenge) or per-subdomain certs. For a Stage 1 deliverable, the operational simplicity of one cert and one server block outweighs the architectural elegance. Path-based gets us running fastest. See ADR-005 for the deferred subdomain hybrid.

**Flat URL space (rejected).** URLs like `/iris-knn` or `/linear-regression` lose the hierarchy entirely — users cannot tell from the URL what kind of demo they are about to load. Loses the scannability benefit.

**Mixed hierarchy with no consistent rule (rejected).** Mixing technique families with algorithms at the same level (`/ml/classification/` next to `/ml/random-forest/`) breaks the hierarchy because Random Forest *is* a classification algorithm. A user clicking `/classification/` would not see all classification work, because Random Forest sits elsewhere. See ADR-004 for the technique-vs-algorithm separation rule.

## Consequences

**Positive:**

- Each level reduces the universe of possibilities, matching how users actually narrow their attention. Progressive disclosure is a well-understood UX pattern.
- Routing is predictable: Nginx serves static files for L1-L3 and proxies to containers for L4. No runtime lookups, no rewrites beyond stripping the L4 prefix.
- Containers do not know their public URL — they respond at their own root (`/`, `/predict`). Nginx handles the URL-to-container mapping. URL structure can evolve without changing model code.
- New demos slot in without naming debates: every demo lives under its appropriate technique family with a `dataset-algorithm` name. ADR-004 governs the L4 naming.

**Negative:**

- Mounting an interactive demo at a deep URL (`/ml/classification/iris-knn/`) requires Nginx to strip the prefix before proxying to the container. If the container generates absolute URLs in its responses (e.g., links to `/predict`), those will be wrong relative to the proxy mount point. Mitigation: every Stage 4 container must emit only relative URLs, or honor the `X-Forwarded-Prefix` header.
- Static HTML at L1-L3 means three files per domain (domain landing, technique pages, optional sub-topic pages). Maintenance burden grows with content depth. Mitigation: a templating step in Stage 2 generates these from a single source.

**Forecloses:**

- Single-page application architectures where all routing is client-side are not directly supported by this pattern without additional Nginx config (`try_files` fallbacks).
