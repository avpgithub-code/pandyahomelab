# Postmortem: Cloudflare Tunnel outage — 36 days across two incidents

**Status:** Resolved
**Date:** 27 August 2026
**Severity:** SEV-1 — total public unavailability of `pandyahomelab.com` and all demos
**Duration:** 15 days (11–26 Jul 2026) + 21 days (6–27 Aug 2026)
**Detection:** Owner loaded the homepage. Both times.
**Author:** Archit Pandya

---

## 1. Summary

`pandyahomelab.com` served Cloudflare **Error 1033** ("Cloudflare Tunnel error") continuously for 21 days, after an identical 15-day outage five weeks earlier. Every visitor to the public site — the entire point of this platform — saw an error page.

Nothing downstream of the tunnel was broken at any point. The NAS was up, Docker was up, Nginx was serving 200s on every route, and every ML/DL demo was healthy. The single failure was that `cloudflared`, the process connecting the NAS to Cloudflare's edge, was not running.

It was not running because it was launched as a bare `nohup` background process with no restart supervision — the only component of the platform outside a Docker restart policy. Each NAS reboot killed it permanently.

A fix for this had been written on 26 July 2026, immediately after the first incident. It was never deployed. The second outage it was authored to prevent happened anyway.

---

## 2. Impact

| | |
|---|---|
| Public site | Error 1033 for all visitors, both windows |
| `www` and `mlflow-dl` subdomains | Same — all tunnel hostnames affected |
| Data loss | None |
| Internal / LAN access | Unaffected throughout |
| Total public downtime | **36 days** |

This is a portfolio platform whose purpose is to be publicly reachable. Functionally, the platform did not exist for a third of the period between 11 July and 27 August.

---

## 3. Timeline

| Date | Event |
|---|---|
| **11 Jul 2026** | NAS reboot. `cloudflared` receives SIGTERM and does not restart. Site begins returning 1033. |
| 11–26 Jul | Outage undetected. **15 days.** |
| **26 Jul 2026** | Owner discovers the outage. Tunnel restarted manually. A containerised, supervised replacement is authored: `deployment/cloudflared/config.yml` + a `cloudflared` service in `deployment/nginx/docker-compose.yml`. **It is never deployed and never committed.** |
| **6 Aug 2026, ~15:38 UTC** | NAS reboot. The still-bare `cloudflared` process is killed again. Last line written to `~/cloudflared.log`. Site begins returning 1033. |
| 6–27 Aug | Outage undetected. **21 days.** |
| **27 Aug 2026, ~15:02 UTC** | Owner loads the homepage, sees Error 1033, opens an investigation. |
| 27 Aug, 15:06 | Diagnosis complete; tunnel restored via the interim bare process. Site returns 200. |
| 27 Aug, ~15:15 | Containerised tunnel deployed. First attempt crash-loops on a Synology ACL. |
| 27 Aug, ~15:20 | ACL cause identified, `user: "0:0"` applied, container healthy with 4 edge connections. Bare process retired. |
| 27 Aug, ~15:30 | Latent `/health` and compose-build defects found and fixed while verifying. |

---

## 4. Diagnosis

Four commands isolated the fault in under two minutes. They are now recorded in the runbook (§4.6):

```bash
ps -ef | grep [c]loudflared         # -> nothing running
tail ~/cloudflared.log              # -> last entry 2026-08-06T15:38Z, 21 days stale
uptime                              # -> up 20 days: boot time matches the last log entry
curl -sk -o /dev/null -w '%{http_code}' \
     -H 'Host: pandyahomelab.com' https://127.0.0.1:8443/   # -> 200
```

The last one is the decisive check. **A healthy origin plus a 1033 means the tunnel is the only broken link** — it removes Nginx, Docker, the demos, DNS, and the NAS itself from suspicion in a single call.

A stale log is also a distinct signal from a noisy one: a log whose last entry is days old proves the process *died*, not that it is failing to connect. That distinction pointed straight at supervision rather than at Cloudflare.

---

## 5. Root causes

### 5.1 Primary: the public ingress was the one unsupervised component

Every service on this platform runs under `restart: unless-stopped` and self-healed across both reboots without intervention. `cloudflared` alone ran as:

```bash
nohup cloudflared tunnel run pandya-homelab >> ~/cloudflared.log 2>&1 &
```

No supervision, no restart, no alert on exit. The blast radius of the single unsupervised process was the entire public platform, because it sat in front of everything else.

### 5.2 Contributing: the auto-start mechanism never worked

A DSM Task Scheduler Boot-up task was believed to cover this. It failed to restore the tunnel across two consecutive reboots and left no error, no log, and no evidence of having run. It has been abandoned rather than repaired — a restart policy on a container is verifiable in a way a Task Scheduler entry is not.

### 5.3 Contributing: the remediation was written but never verified

The containerised fix existed on disk from 26 July. It was correct in design. It failed on first deploy because of §5.4, and the work stopped there — leaving the platform on the known-broken path for another five weeks, with the fix appearing "done" because the files existed.

**"Written" is not "deployed." "Deployed" is not "verified."** The only evidence that counts is a probe against the running system.

### 5.4 Blocking defect: Synology ACLs vs. a distroless container

The first containerised deploy crash-looped:

```
open /etc/cloudflared/config.yml: permission denied
```

`cloudflare/cloudflared` is distroless and defaults to user `nonroot` (uid 65532). The mounted config and credentials live on `/volume1` under Synology ACLs:

```
$ ls -la deployment/cloudflared/config.yml
-rwxrwxrwx+ 1 avpadmin users 1861 ... config.yml     # <- 777 is SYNTHETIC

$ synoacltool -get deployment/cloudflared/config.yml
 [0] group:administrators:allow:rwxpdDaARWc--
 [1] user:avpadmin:allow:rwxpdDaARWc--
 [2] user:admin:allow:rwxpdDaARWc--                  # <- no `everyone` ACE
```

The POSIX mode displays as `777` with a trailing `+`. That mode is synthetic; the ACL is what the kernel enforces, and it grants nothing to uid 65532.

**Resolved** with `user: "0:0"` on the service — root bypasses the ACL via `CAP_DAC_OVERRIDE`.

**Rejected alternative:** adding an `everyone` read ACE with `synoacltool -add`. That keeps the container non-root but makes the *tunnel credentials* readable by every account on the NAS. A port-less container with two read-only file mounts running as root is the smaller exposure.

This generalises: **any** container mounting `/volume1` files as a non-root user will hit this.

---

## 6. Latent defects found while verifying

Neither caused the outage. Both were found because the fix was verified by probing rather than by reading exit codes — and both had been silently masking the state of the system for a month.

### 6.1 The Nginx healthcheck had never passed

`nginx.conf` redirected `/health` along with everything else on port 80:

```nginx
server {
    listen 80;
    return 301 https://$server_name$request_uri;    # swallows /health
}
```

A server-level `return` runs in the rewrite phase and short-circuits location matching. The Dockerfile healthcheck uses `wget --spider`, which does not follow redirects, so the check failed on every 10-second interval since it was introduced. Fixed by serving `/health` from a `location` block ahead of the catch-all redirect.

This matters beyond tidiness: `restart: unless-stopped` does not act on health status, so an unhealthy container never self-heals, and a `depends_on` health condition can never be satisfied. It was a broken sensor, not a broken service — which is why it went unnoticed.

### 6.2 `docker compose build` was a silent no-op

The `pandya-nginx` service declared `image:` with **no `build:` section**. Compose therefore had no build context:

```
$ sudo docker compose build --no-cache pandya-nginx
[+] Building 0.0s (0/0)                       # did nothing, exited 0
```

A `--force-recreate` afterwards relaunched the stale image. Because `nginx.conf` is `COPY`ed into the image rather than bind-mounted, **every `nginx.conf` change for an unknown period looked applied and was not** — including the §6.1 fix, which stayed dormant while `curl http://172.24.0.2/health` still returned 301.

Fixed by wiring `build: {context: ., dockerfile: Dockerfile}` into the service, removing the trap rather than relying on remembering it.

**The tell:** a real build prints numbered steps (`[pandya-nginx 4/6] COPY nginx.conf …`). `0.0s (0/0)` means nothing was built, regardless of exit code.

---

## 7. The pattern: everything reported success

The single most important observation from this incident. Not one failure in the chain threw an error:

| Component | What it did | What it reported |
|---|---|---|
| `nohup cloudflared` | Died at reboot | Nothing. Log simply stops. |
| DSM Boot-up task | Did not restore the tunnel | Nothing. No error, no record. |
| `docker compose build` | Built nothing | `0.0s (0/0)`, **exit code 0** |
| `ls -la` | File was unreadable | Mode `777` |
| `docker compose up` | Container crash-looping | `✔ Container pandya-cloudflared Started` |
| Nginx healthcheck | Never passed | Container kept serving traffic normally |

A verification strategy built on "did the command fail?" would have caught **none** of these. Every one was caught by probing the actual endpoint:

```bash
curl -s http://172.24.0.3:20241/ready     # {"status":200,"readyConnections":4,...}
curl -s http://172.24.0.2/health          # 200 OK  (301 = stale image)
```

**Check the outcome, not the exit code.**

---

## 8. Remediation

| # | Action | Status |
|---|---|---|
| 1 | Tunnel runs as `pandya-cloudflared` with `restart: unless-stopped` | ✅ Done |
| 2 | `user: "0:0"` to survive Synology ACLs on `/volume1` mounts | ✅ Done |
| 3 | Duplicate host config `~/.cloudflared/config.yml` deleted — one config, no drift | ✅ Done |
| 4 | DSM Task Scheduler boot task abandoned | ✅ Done — but found still *enabled* on 23 Sep 2026; disabled then (not yet deleted) |
| 5 | `/health` served from a `location` block; healthcheck passes | ✅ Done |
| 6 | `build:` wired into the `pandya-nginx` compose service | ✅ Done |
| 7 | Runbook §4.6 rewritten: single config, ACL requirement, 1033 diagnosis steps | ✅ Done |
| 8 | Runbook §6 manual "step 4: start the tunnel" removed | ✅ Done |
| 9 | **Cloudflare Zero Trust → Tunnel Health notification** | ✅ Done 23 Sep 2026 — tunnel `pandya-homelab` + future tunnels, trigger healthy/degraded/down, email; test alert received |
| 10 | Audit the platform for any other unsupervised process | ⬜ Open |

Commits on `fix/cloudflared-supervised-container`:

- `e730a0f` — supervise the tunnel as a container to end Error 1033
- `fd778c1` — wire compose to the Dockerfile so rebuilds actually rebuild

### Verification (27 Aug 2026, post-fix)

```
container /ready       -> {"status":200,"readyConnections":4}
nginx /health          -> 200 OK
pandyahomelab.com      -> 200
www.pandyahomelab.com  -> 200
mlflow-dl...           -> 200
```

---

## 9. Action item 9 is the one that matters

Items 1–8 prevent *this* failure from recurring. **None of them prevents the next one from going unnoticed for three weeks.**

The tunnel can still fail in ways a restart policy cannot fix — expired credentials, a Cloudflare-side change, a config edit that does not parse, a network partition. The detection mechanism for both incidents was the owner happening to load the homepage. That mechanism has a demonstrated 15–21 day latency.

Cloudflare Zero Trust offers a **Tunnel Health** notification (free) that emails on disconnect. It is roughly five minutes of setup and is the highest-value item remaining.

**Update 23 Sep 2026:** enabled. It covers `pandya-homelab` and any future tunnel, fires on any change between healthy, degraded and down, and emails the owner. A dashboard **Test** send was received. Detection latency drops from weeks to minutes.

---

## 10. Lessons

1. **In a system where everything is supervised, audit the exception.** One unsupervised process took down a platform of a dozen self-healing containers, because it sat in front of them.
2. **Detection is a separate problem from recurrence.** Fixing the cause of an outage does nothing about the next one you do not notice.
3. **"Written" ≠ "deployed" ≠ "verified."** A correct fix that was never confirmed running is indistinguishable from no fix at all — the second outage proved it.
4. **Silent success is the dangerous failure mode.** Exit code 0 is not evidence. Probe the endpoint.
5. **Commit the remediation immediately.** The only copy of this fix spent a month untracked in a working tree on the machine it was meant to protect.
6. **On Synology, `ls -la` lies.** Mode `777` with a trailing `+` means an ACL decides. Use `synoacltool -get`.

---

## Related

- [ADR-006 — Custom Nginx replaces DSM reverse proxy](../adr/ADR-006-nginx-replaces-dsm-proxy.md)
- [ADR-019 — Internet access and domain routing](../adr/ADR-019-internet-access-domain-routing.md)
- [Development Runbook §4.6 — Cloudflare Tunnel](../DEVELOPMENT_RUNBOOK.md)
