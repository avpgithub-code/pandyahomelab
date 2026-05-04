# ADR-005: Path-based routing for Stage 1, subdomain hybrid deferred

**Status:** Accepted
**Date:** April 2026
**Stage:** 1 (Conceptual Design)

## Context

ADR-003 established a four-level URL hierarchy. The question this ADR resolves is more specific: **at the routing layer, do all URLs sit under one hostname (`pandyahomelab.com/...`) or do APIs live on subdomains (`api.ml.pandyahomelab.com/...`)?**

This decision affects:
- Number of TLS certificates needed
- DNS records to manage at Hostinger
- Number of Nginx server blocks
- CORS and cookie scoping behavior between marketing pages and APIs
- How a user types or shares an API endpoint

Two viable models existed:

- **Pure path-based:** `pandyahomelab.com/ml/classification/iris-knn`. One hostname, one cert, one server block.
- **Hybrid (paths for marketing, subdomains for APIs):** `pandyahomelab.com/ml/` for the technique page, `api.ml.pandyahomelab.com/iris-knn` for the actual API endpoint. Wildcard cert needed.

## Decision

**Stage 1 uses pure path-based routing. The subdomain hybrid is deferred — not rejected — to a future stage.**

All URLs at all four levels live under `pandyahomelab.com/...`. One TLS certificate (issued via HTTP-01 challenge), one Nginx server block, one DNS A record at Hostinger.

## Alternatives considered

**Pure subdomain-based (rejected for Stage 1).** Each domain on its own subdomain (`ml.pandyahomelab.com`, `dl.pandyahomelab.com`). Cleanest separation but requires a wildcard certificate (DNS-01 challenge), which adds operational complexity to TLS automation. Acceptable for a mature platform; overkill for Stage 1.

**Hybrid (deferred, not rejected).** Marketing pages on paths (`/ml/`), APIs on subdomains (`api.ml.pandyahomelab.com`). The hybrid sidesteps the CORS-and-cookies trap that pure path-based creates when you eventually have a JS frontend. It is the model real production platforms tend to converge on. We accept that a future ADR may supersede this one when:
- A specific demo needs same-origin requests for credentialed APIs
- A demo requires CORS configuration that conflicts with the marketing site
- The platform takes on a JS-heavy frontend that needs a clear API origin separate from the marketing origin

## Consequences

**Positive:**

- Fastest path to running. One cert, one DNS record, one server block. Stage 2 can ship without first solving wildcard cert automation.
- Clean URLs that mirror the four-level hierarchy directly. No mental model shift between marketing pages and demos.
- All static and dynamic content shares one origin, so any link from the landing page to a demo is a same-origin navigation. No CORS edge cases in Stage 1.
- TLS automation in Stage 5 can use the simplest possible Let's Encrypt setup (HTTP-01 challenge through the same Nginx).

**Negative:**

- Containers mounted at deep URL paths must emit only relative URLs in their responses. Absolute URLs like `<a href="/predict">` will resolve to `pandyahomelab.com/predict` — wrong. Mitigation: ADR-003 already requires this behavior; Stage 2 service templates will enforce it.
- Cookies set by any container (e.g., a Jupyter session cookie) are scoped to the entire `pandyahomelab.com` origin. Two containers using the same cookie name will collide. Mitigation: Stage 2 conventions will require per-container cookie name prefixes.
- CORS becomes brittle if a Stage 4 frontend is hosted separately and tries to call an API on the same origin — there is no clean way to relax CORS for one path without doing so for the entire origin.

**Forecloses:**

- Pure subdomain isolation is foreclosed for Stage 1. Adding it later means migrating URLs (and any external links) — manageable but not free.

## Supersession trigger

This ADR will be revisited when any of the following becomes true:
- A demo requires authentication beyond Basic Auth (cookies become a real concern)
- A frontend application is added that is not co-located with the API
- The platform begins serving requests from non-browser clients (third-party API consumers)
