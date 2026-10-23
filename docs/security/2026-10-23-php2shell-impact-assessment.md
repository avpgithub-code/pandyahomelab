# Security assessment: php2shell PHP RCE (CVE-2026-109618, CVE-2026-109619)

**Status:** Closed (one residual item tracked below)
**Date:** 23 October 2026
**Verdict:** pandyaHomeLab **not affected**. The NAS host carried an unused, vulnerable PHP runtime; it was patched, then removed.
**Author:** Archit Pandya

---

## 1. The advisory

Disclosed 21 October 2026 ([Help Net Security](https://www.helpnetsecurity.com/2026/10/21/php2shell-php-vulnerabilities-patched-cve-2026-109618-cve-2026-109619/)).

| | |
|---|---|
| CVE-2026-109618 | RCE via out-of-memory corruption of partly initialised request data |
| CVE-2026-109619 | RCE via request-owned global state surviving into a later request on the same worker |
| Affected | Every PHP that serves web requests: PHP-FPM, mod_php, php-cgi, FrankenPHP, LiteSpeed |
| Preconditions | Network access only. One unauthenticated request, before any application code runs |
| Fixed in | 8.5.12, 8.4.27, 8.3.36, 8.2.35. 8.1 and older: upstream EOL, vendor backports only |
| Exploitation | Public working exploit; in-the-wild attempt seen 17 Oct 2026, four days before disclosure |

The bugs live in the per-request lifecycle of the web SAPIs. The CLI binary is not the attack surface.

---

## 2. Exposure analysis

### 2.1 The platform: not exposed

| Layer | Finding |
|---|---|
| Public ingress | Cloudflare Tunnel routes all four hostnames to `pandya-nginx:443`; anything else gets `http_status:404` |
| Nginx | Every upstream is `proxy_pass` to a Python service. No `fastcgi_pass`, no PHP handler |
| Images | Python 3.10–3.12 slim, `nginx:1.25-alpine`, Postgres, Redis, MinIO, MLflow, cloudflared. No PHP in any image |
| Repository | No `.php` files; no PHP, FPM or FastCGI references in deployment config |

No PHP sits anywhere on the request path. The Cloudflare WAF rules shipped for this CVE are therefore irrelevant to the platform.

### 2.2 The NAS host: vulnerable runtime present, not served

| Item | Version | Role |
|---|---|---|
| PHP8.2 package | 8.2.30 (vulnerable) | Dependency of Note Station only. Includes `php82-fpm` and `php82-cgi` |
| DSM built-in `/usr/bin/php` | 8.1.32 (upstream EOL) | CLI only: DSM DDNS updaters, package indexers |

Not reachable as a web SAPI at the time of assessment:

- No php-fpm process or socket was running.
- Web Station was not installed; its leftover vhost configs sat in `conf.d-available`, not enabled.
- DSM's nginx only serves `index_ds.php` as a static file (`default_type text/html`); everything else goes to DSM's own CGI handlers.
- Note Station's web API is compiled `.so` modules; it shells out to the PHP CLI for import/export only.

**Latent risk:** installing Web Station or any PHP web app (WordPress, phpMyAdmin) on the unpatched package would have made it a live web SAPI. QuickConnect is enabled, so such an app would not be LAN-only.

---

## 3. Actions taken (23 Oct 2026)

| # | Action | Verified |
|---|---|---|
| 1 | PHP8.2 package updated 8.2.30 → **8.2.35-0171** via Package Center | CLI, CGI and FPM binaries all report 8.2.35 |
| 2 | Note Station uninstalled (no notes; installed weeks earlier and never used) | `/var/packages/NoteStation` gone |
| 3 | PHP8.2 package uninstalled (no remaining dependents) | No `php82*` binaries; no PHP processes |
| 4 | Public site re-checked after each step | Home, cricstat, predictor, ML/NLP demos, all three MLflow trackers: 200 |

### 3.1 Opportunistic hardening (found during the assessment)

The NAS listening-port review turned up services bound to every interface that the platform does not use:

| Port | Service | Action | Verified |
|---|---|---|---|
| 23 | Telnet | Disabled | Closed |
| 21, 55536–55899 | FTP and FTPS | Both disabled | Closed |
| 3306 | MariaDB 10 | Package **stopped**, not uninstalled. Only user database belonged to a retired personal site; data kept on disk | Closed; no `mysqld` |

SSH (22) remains enabled; it is the operator's access path. SFTP was already off.

### 3.2 Side finding: Container Manager alerts were a reboot, not a crash loop

DSM showed 20 grouped "container stopped unexpectedly" alerts, including `analytics-ingester`. Investigation: the NAS rebooted at ~08:44 local on 22 Oct; the ingester stopped cleanly (exit 0, not OOM) and has run healthy since, with 7 restarts in three weeks. Every container **and the tunnel** came back unattended, which validates the fix from the [Cloudflare Tunnel outage postmortem](../postmortems/2026-08-27-cloudflare-tunnel-outage.md).

---

## 4. Residual risk and open items

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | DSM built-in PHP 8.1.32 is fixed only by a DSM update. CLI-only, so low exposure | Operator | Watch Control Panel → Update & Restore |
| 2 | Root cause of the 22 Oct reboot (manual, DSM auto-update, or power) not yet confirmed | Operator | Check Log Center → System |
| 3 | No external uptime monitoring; an unplanned reboot is only noticed by chance | — | Carried into the spec review |

---

## 5. Lessons

1. **The platform's design held.** Keeping all public traffic behind one tunnel into one nginx that only proxies to containers meant answering "are we exposed?" took a grep, not an audit.
2. **The host is part of the attack surface.** The vulnerable software was not in the repo; it was a NAS package pulled in by an unused app. The repo cannot see this, so host packages need their own periodic review.
3. **Remove, don't just patch.** Uninstalling the unused runtime closes this CVE and every future one in the same package.

---

## Related

- [Postmortem: Cloudflare Tunnel outage](../postmortems/2026-08-27-cloudflare-tunnel-outage.md)
- [ADR-001: Networks isolate by trust boundary](../adr/ADR-001-trust-boundary-isolation.md)
- [ADR-019: Internet access and domain routing](../adr/ADR-019-internet-access-domain-routing.md)
- [NETWORK_CIDR_SUMMARY.md](../NETWORK_CIDR_SUMMARY.md)
