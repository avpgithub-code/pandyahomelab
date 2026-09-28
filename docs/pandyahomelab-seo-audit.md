# SEO Audit — pandyaHomeLab

**Site:** https://pandyahomelab.com
**Date:** 30 May 2026
**Auditor:** Claude (seo-audit)
**Scope:** Full-site technical + on-page + content review of the public site, focused on its purpose as a non-commercial AI portfolio / career-transition showcase.

---

## Method & verification limits (read first)

This audit is based on what could be observed live: the rendered homepage, one representative demo page (`/ml/iris-knn/`), and an indexation check. The following could **not** be directly verified with the tools available, and are marked *VERIFY* rather than asserted as pass/fail:

- `<head>` metadata (meta description, canonical, Open Graph, Twitter cards) — the fetch tool strips `<head>` during conversion.
- JSON-LD / structured data — the fetch tool strips `<script>` tags; this is a known false-negative trap, so schema is **not** reported as "missing."
- `robots.txt` and `sitemap.xml` — not reachable through the available fetch path.
- Core Web Vitals / page speed — no PageSpeed Insights access.

Confirm the *VERIFY* items yourself with: **Google Search Console**, **Rich Results Test** (renders JS, sees injected schema), **PageSpeed Insights**, and a direct `curl -I` from a machine on your network. Where this report is confident, it says so; where it isn't, it says *VERIFY*.

---

## Executive summary

**Overall health: foundation is clean, discoverability is the problem.** The pages that exist are well-built for SEO at the basic level — unique titles, sane heading hierarchy, readable keyword-bearing URLs, real and specific content, HTTPS, mobile viewport. What's missing is everything that lets a search engine *find, trust, and reliably reach* the site. For a portfolio whose entire job is to be seen by recruiters and hiring managers, that gap is the whole game.

**Top 5 priorities**

1. **Confirm indexation and connect Search Console.** A `site:pandyahomelab.com` query surfaced no pages from the domain. For a recently launched, self-hosted site that almost certainly means *not yet indexed* — but confirm in GSC rather than trusting the search result.
2. **Treat availability as an SEO problem, not just an ops one.** The site runs on a home Synology NAS behind residential Fios. If Googlebot arrives while the NAS is down or the dynamic IP has rotated, crawl errors accumulate and indexation stalls. This is the single most setup-specific risk here.
3. **Ship `robots.txt` + `sitemap.xml`.** Neither could be confirmed. Without a sitemap, your real demo URLs (`/ml/iris-knn/`, `/dl/mnist-cnn/`, etc.) are only discoverable via on-page links — and the homepage's primary nav is anchor-based, so the crawl surface is thin.
4. **Add per-page meta descriptions and Open Graph tags.** *VERIFY* — but likely absent. OG tags specifically matter for you: a portfolio gets shared on **LinkedIn**, and without OG tags those shares render as bare grey boxes.
5. **Make the author visible (E-E-A-T).** Nothing on the page ties the work to *Archit Pandya* with credentials or links. For a career-transition portfolio this is both an SEO trust signal and the actual point of the site.

**Quick wins (hours, not days):** meta descriptions, Open Graph/Twitter tags, `robots.txt`, a hand-written `sitemap.xml`, an About/author block, and `noindex` on infrastructure endpoints.

---

## Technical SEO findings

### T1 — Indexation likely absent
- **Impact:** High
- **Evidence:** `site:pandyahomelab.com` returned no pages from the domain (only unrelated "Pandya" namesakes). Consistent with a new, self-hosted site not yet crawled.
- **Fix:** Verify the property in Google Search Console (DNS TXT record via Hostinger is easiest for a root domain). Submit a sitemap, then use *URL Inspection → Request Indexing* on the homepage and each live demo. Repeat in Bing Webmaster Tools.
- **Priority:** 1

### T2 — Availability / crawl-reliability risk from self-hosting
- **Impact:** High
- **Evidence:** Architecture context — single Synology NAS, residential Fios, public 80/443 → NAS 8080/8443. No second origin; residential IPs can rotate.
- **Fix:** (a) Put the site behind **Cloudflare** (free tier) as a caching proxy — it serves cached HTML when the NAS blips, stabilizes the public IP behind Cloudflare's anycast, and adds a CDN + TLS edge for free; this also sidesteps the dynamic-IP problem. (b) If you stay on raw Fios, run a dynamic-DNS updater so the A record never goes stale. (c) Add uptime monitoring (UptimeRobot/Healthchecks) so you learn about downtime before Googlebot does. This is the highest-leverage structural fix for a home-hosted portfolio.
- **Priority:** 1

### T3 — No confirmed XML sitemap
- **Impact:** High
- **Evidence:** *VERIFY* — `sitemap.xml` not reachable via the audit path.
- **Fix:** Generate a static `sitemap.xml` listing only the real, indexable URLs (homepage + each **live** demo). Exclude `Planned` demos that 404 or are empty. Reference it from `robots.txt` and submit in GSC. At this scale a hand-written file is fine; no plugin needed.
- **Priority:** 1

### T4 — No confirmed robots.txt
- **Impact:** Medium
- **Evidence:** *VERIFY* — `robots.txt` not reachable via the audit path.
- **Fix:** Add a minimal `robots.txt` that allows crawling, points to the sitemap, and disallows infrastructure paths (see T5). Example:
  ```
  User-agent: *
  Allow: /
  Disallow: /mlflow/
  Disallow: /health
  Sitemap: https://pandyahomelab.com/sitemap.xml
  ```
- **Priority:** 2

### T5 — Infrastructure endpoints publicly linked
- **Impact:** Medium (SEO crawl-budget + security-adjacent)
- **Evidence:** Homepage links `/mlflow/` ("Open MLflow →") and `/health` directly. MinIO/Postgres/Redis are correctly described as internal — good.
- **Fix:** Keep MLflow and `/health` out of the index: `Disallow` in robots, add `X-Robots-Tag: noindex` on those responses, and ideally gate MLflow behind Basic Auth. An indexed MLflow UI is both crawl waste and an information-disclosure footgun.
- **Priority:** 3

### T6 — Trailing-slash / canonical consistency
- **Impact:** Low
- **Evidence:** `/ml/iris-knn/` resolved to `/ml/iris-knn` (the fetch landed on the non-slash form). Mixed forms can split signals if both stay reachable without canonicalization.
- **Fix:** Pick one canonical form, 301 the other to it in Nginx, and emit a self-referencing `<link rel="canonical">` on every page. Cheap insurance.
- **Priority:** 3

### T7 — Core Web Vitals unmeasured
- **Impact:** Medium
- **Evidence:** *VERIFY* — no PSI access. Note: both pages show a "Loading…" overlay and demo content depends on a JS call to a model API ("Prediction failed…" appeared on the demo when its backend didn't respond to the fetch).
- **Fix:** Run PageSpeed Insights on the homepage and one demo. Watch LCP (target < 2.5s) given the loading overlay, and CLS if content shifts in after load. Ensure the indexable *text* renders without requiring the API call to succeed.
- **Priority:** 2

### Technical — confirmed positives
- **HTTPS** serves correctly with a 200 on the homepage and demo.
- **Mobile viewport** is configured (`width=device-width, initial-scale=1.0`).
- **URLs are clean** — lowercase, hyphenated, descriptive, no parameters.

---

## On-page SEO findings

### O1 — Meta descriptions likely missing
- **Impact:** Medium
- **Evidence:** *VERIFY* — no description surfaced in the extracted head on either page.
- **Fix:** Add a unique 150–160 char description per page with the project's keyword and a reason to click. e.g. *"Interactive K-Nearest Neighbors demo on the Iris dataset — adjust flower measurements and get a live species prediction with confidence scores. Part of pandyaHomeLab."*
- **Priority:** 2

### O2 — Open Graph / Twitter cards likely missing
- **Impact:** Medium (high for *your* distribution channel)
- **Evidence:** *VERIFY* — not observable in extracted head.
- **Fix:** Add `og:title`, `og:description`, `og:image`, `og:url`, `og:type` and the `twitter:card` equivalents. You already produced a LinkedIn graphic in Stage 1 — use it as the `og:image`. Without these, every LinkedIn/Slack share of your portfolio renders as an unlabeled grey box.
- **Priority:** 2

### O3 — Anchor-based navigation leaves a thin crawlable surface
- **Impact:** Medium
- **Evidence:** Homepage primary nav is in-page anchors (`#ml`, `#dl`, `#nlp`, `#agentic`). The four-level URL hierarchy from ADR-003 (`/ml/`, `/ml/classification/`) is not expressed as crawlable landing pages; only the leaf demo URLs are real routes, reached via "Try it →" links.
- **Fix:** If the ADR-003 hierarchy is meant to carry SEO weight, create real `/ml/`, `/dl/`, `/nlp/`, `/agentic/` landing pages with crawlable internal links down to demos — that gives search engines a topical structure and more indexable pages. If you'd rather keep a one-page site, that's a legitimate choice; just make sure the sitemap lists the leaf demos directly so they're still discoverable.
- **Priority:** 2

### O4 — Live URLs deviate from the ADR-003 four-level scheme
- **Impact:** Low (consistency note, not an SEO defect)
- **Evidence:** Live demo is `/ml/iris-knn/`; ADR-003/004 specify `/ml/classification/iris-knn`. The technique-family level (L3) is collapsed in the running site.
- **Fix:** Not an SEO problem — shorter URLs are arguably better for sharing. But it's a drift from the locked architecture; either update the implementation to match the ADR or write a short superseding ADR so the contract and reality agree. Flagging because you track these deliberately.
- **Priority:** 3

### On-page — confirmed positives
- **Title tags** are unique and well-formed: *"pandyaHomeLab — AI Learning & Deployment Platform"* and *"Iris KNN Classifier — pandyaHomeLab"*. Good length, descriptor-then-brand pattern, brand at the end. Strong.
- **Heading structure** is clean: a single H1 per page, logical H2s (Featured Projects, Built With, MLOps Infrastructure) and H3s for individual projects. No multiple-H1 or skipped-level problems observed.
- **Content is specific and original** — real datasets, real metrics (≥98% MNIST accuracy, AUC/F1/Accuracy, MC-Dropout bands). This is exactly the kind of first-hand, concrete content search engines reward.

---

## Content & E-E-A-T findings

### C1 — Structured data: validate, then add
- **Impact:** Medium
- **Evidence:** *VERIFY* — cannot detect JSON-LD with the fetch tool (it strips scripts). Do **not** assume it's missing without checking.
- **Fix:** Run each page through the Rich Results Test. Then add `Person` schema (you, the author, with `sameAs` links to GitHub/LinkedIn) and `SoftwareApplication` or `CreativeWork` schema for each demo. For a portfolio, `Person` schema is the highest-value markup — it helps tie the whole site to your name as an entity.
- **Priority:** 2

### C2 — "Planned" demos as indexable dead-ends
- **Impact:** Low–Medium
- **Evidence:** Several projects (Object Detection, Sentiment, NER, Claude Agent) are marked *Planned* with placeholder paths.
- **Fix:** Don't let planned-but-empty URLs into the sitemap or index — empty/thin pages drag on site-wide quality signals. Keep them as non-linked "coming soon" cards (as now) until they're real, then add them to the sitemap.
- **Priority:** 3

### C3 — Author identity is invisible
- **Impact:** Medium
- **Evidence:** No visible author name, bio, credentials, or links to GitHub/LinkedIn on the homepage. There's an "About" affordance (ⓘ) but no surfaced author entity.
- **Fix:** Add a short About/author section: your name, the career-transition narrative, and outbound links to GitHub and LinkedIn (and an email or contact). This is simultaneously an E-E-A-T trust signal, the literal purpose of a portfolio, and the anchor for the `Person` schema in C1.
- **Priority:** 2

### Content — confirmed positive
- The platform demonstrates genuine **Experience** (working, deployed models you built) — the strongest E-E-A-T dimension and hard to fake. The fix in C3 is about making the *Expertise/Authoritativeness* signals visible, not manufacturing them.

---

## Prioritized action plan

**1 — Critical (unblock discovery)**
- Set up Google Search Console + Bing Webmaster Tools; verify via Hostinger DNS TXT.
- Put the site behind Cloudflare (free) for caching, stable origin, and CDN/TLS edge — fixes the home-hosting availability risk.
- Publish `sitemap.xml` (live URLs only) and submit it; request indexing on homepage + live demos.

**2 — High impact**
- Add `robots.txt` (allow crawl, point to sitemap, disallow `/mlflow/` and `/health`).
- Add per-page meta descriptions and Open Graph/Twitter tags (reuse the Stage 1 LinkedIn graphic as `og:image`).
- Add an About/author section with name, narrative, and GitHub/LinkedIn links.
- Run PageSpeed Insights; confirm indexable text renders without the model API.

**3 — Quick wins / hygiene**
- `noindex` + auth on MLflow; `noindex` on `/health`.
- Self-referencing canonical tags; settle trailing-slash form with a 301.
- Validate/add JSON-LD (`Person` + per-demo `SoftwareApplication`).
- Keep `Planned` demos out of the sitemap until they're live.

**4 — Longer term**
- Decide whether to build real `/ml/`, `/dl/`, etc. landing pages (more indexable surface + topical structure) or stay single-page; reconcile with ADR-003 either way.
- Once demos are stable, add a short write-up page per project (problem, approach, result) — these are the pages that actually rank for "iris knn demo," "mnist cnn pytorch," and similar long-tail queries, and they double as portfolio depth.

---

## One honest framing note

For most sites the SEO question is "how do we outrank competitors." For a non-commercial personal portfolio hosted on a home NAS, the realistic goal is narrower and more achievable: **be reliably crawlable, be unambiguously attributable to you, and rank for your own name + project names** so that when a recruiter searches "Archit Pandya pandyaHomeLab" or "pandyahomelab iris knn," your pages appear and render well when shared. The action plan above is ordered toward that goal, not toward chasing competitive head terms you don't need.
