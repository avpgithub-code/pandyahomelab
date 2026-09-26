# pandyaHomeLab — Development Runbook

**Version:** 1.1 (adds Phase 3 lessons)  
**Last Updated:** 2026-09-25  
**Purpose:** Reference for all future ML/DL/NLP/Agentic project development.  
Captures every hard-won lesson from Phase 1a so Phase 1b+ is clean first time.

---

## 1. Infrastructure Overview

### 1.1 What's Already Running (Never Recreate)

| Service | Container | IP | Host Port | Notes |
|---|---|---|---|---|
| PostgreSQL | ml-postgres | 172.20.0.2 | 5433 | DSM has native postgres on 5432 — use 5433 |
| MinIO | ml-minio | 172.20.0.3 | 9000/9001 | Object storage + console |
| Redis | ml-redis | 172.20.0.4 | 6379 | Cache |
| MLflow (ML) | ml-mlflow | 172.20.0.5 | 5000 | Public read-only at `/mlflow/` |
| MLflow (DL) | dl-mlflow | 172.21.0.5 | — | Public read-only at `mlflow-dl.pandyahomelab.com` |
| MLflow (NLP) | nlp-mlflow | 172.22.0.5 | — | Public read-only at `mlflow-nlp.pandyahomelab.com` |
| Nginx | pandya-nginx | 172.24.0.2 (proxy) / .20 on ml, dl, nlp networks | 8080/8443 | Reverse proxy entry point |
| Cloudflare Tunnel | pandya-cloudflared | 172.24.0.3 | — | The only public ingress |

The full, current allocation (every container, IP and host port) is
[NETWORK_CIDR_SUMMARY.md](NETWORK_CIDR_SUMMARY.md). This section is a quick reference only.

### 1.2 Port Allocation — NEVER USE THESE

| Port | Occupied By | Why |
|---|---|---|
| 80, 443 | DSM native Nginx | Verizon ISP blocks 80/443 for residential anyway |
| 5432 | DSM native PostgreSQL | Always use 5433 for ml-postgres |
| 5500, 5501 | DSM web UI | Internal DSM ports |
| 5443 | DSM native Nginx HTTPS | |
| 6379 | ml-redis | |
| 8080, 8443 | pandya-nginx | |
| 9000, 9001 | ml-minio | |
| 8001 | ml-iris-knn | Phase 1a project |

### 1.3 Project Slots

Each domain has ten project slots, `.10`–`.19`, and ten host ports (ML 8001–8009, DL 8010–8019,
NLP 8020–8029, Agentic 8030–8039; ADR-016 Amendment 1). All demo host ports bind to
`127.0.0.1`. Slots in use as of 2026-09-25:

| Project | Host port | IP |
|---|---|---|
| ml-iris-knn | 127.0.0.1:8001 | 172.20.0.10 |
| ml-housing-linear | 127.0.0.1:8002 | 172.20.0.11 |
| ml-titanic-automl | 127.0.0.1:8003 | 172.20.0.12 |
| dl-mnist-cnn | 127.0.0.1:8010 | 172.21.0.10 |
| dl-lstm-forecast | 127.0.0.1:8011 | 172.21.0.11 |
| nlp-quora-randomforest | 127.0.0.1:8020 | 172.22.0.10 |
| nlp-imdb-textrep | 127.0.0.1:8021 | 172.22.0.11 |
| nlp-text8-word2vec | 127.0.0.1:8022 | 172.22.0.12 |
| *(3d, reserved)* | 127.0.0.1:8023 | 172.22.0.13 |

Check a slot against the CIDR summary before using it; if an address isn't there, amend
ADR-016 first.

---

## 2. Network Topology (ADR-016)

### 2.1 Docker Networks

```
Internet
    ↓
Cloudflare Tunnel (HTTPS, noTLSVerify: true)
    ↓
pandya-nginx (172.24.0.2 on proxy-network, 172.20.0.20 on ml-network)
    ↓
ml-iris-knn (172.20.0.10) | ml-housing-linear (172.20.0.11) | ...
```

### 2.2 Network Names

| Network | CIDR | Docker Name | Gateway |
|---|---|---|---|
| ML domain | 172.20.0.0/24 | ml_ml-network | 172.20.0.1 |
| DL domain | 172.21.0.0/24 | dl_dl-network | 172.21.0.1 |
| NLP domain | 172.22.0.0/24 | nlp_nlp-network | 172.22.0.1 |
| Agentic domain | 172.23.0.0/24 | agentic_ag-network | 172.23.0.1 |
| Proxy | 172.24.0.0/24 | nginx_pandya-proxy-network | 172.24.0.1 |

### 2.3 IP Allocation Rules (ADR-016)

```
.1   = Gateway
.2   = PostgreSQL
.3   = MinIO
.4   = Redis
.5   = MLflow
.10  = Project 1 (e.g., ml-iris-knn)
.11  = Project 2 (e.g., ml-housing-linear)
.12  = Project 3
.20  = Nginx (when attached to domain network)
```

---

## 3. HTTP Request Flow — End to End

```
Browser → https://pandyahomelab.com/ml/iris-knn/
    ↓
Cloudflare Edge (DNS: pandyahomelab.com → tunnel CNAME)
    ↓
cloudflared (running on NAS, connects to Cloudflare)
    ↓
https://localhost:8443 (Nginx, self-signed cert, noTLSVerify)
    ↓
Nginx strips /ml/iris-knn/ prefix → proxy_pass http://ml_projects/
    ↓
ml-iris-knn:8000 (FastAPI, on ml-network 172.20.0.10)
    ↓
Response back up the chain
```

### 3.1 Nginx Routing Rules

```nginx
# PATTERN: Each project gets its own sub-path
location /ml/iris-knn/ {
    proxy_pass http://ml_projects/;   # trailing slash strips prefix
}

location /ml/housing-linear/ {
    proxy_pass http://ml_housing/;    # new upstream for Phase 1b
}

# Domain root returns listing JSON
location = /ml/ {
    return 200 '{"domain":"ml","projects":["iris-knn","housing-linear"]}';
}

# Undeployed domains return 503
location /dl/ {
    return 503 '{"status":"coming_soon","domain":"dl"}';
}
```

---

## 4. Known Issues & Solutions

### 4.1 Port Conflicts

| Problem | Solution |
|---|---|
| `bind: address already in use` on 5432 | DSM postgres owns 5432 — map ml-postgres to 5433 |
| `bind: address already in use` on 80/443 | DSM nginx owns 80/443 — use 8080/8443 for our Nginx |
| Nginx container exits with "host not found in upstream" | Future domain upstreams don't exist yet — return 503 instead |

### 4.2 Docker Patterns

```dockerfile
# ✅ CORRECT: Install system-wide (not --user)
RUN pip install --no-cache-dir -r requirements.txt

# ❌ WRONG: --user causes permission denied when running as appuser
RUN pip install --user --no-cache-dir -r requirements.txt

# ✅ CORRECT: Copy from builder to system locations
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# ✅ CORRECT: Healthcheck without curl (not in slim image)
HEALTHCHECK CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# ❌ WRONG: curl not available in python:3.11-slim
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
```

### 4.3 Python 3.8 Compatibility (NAS system Python)

```python
# ✅ CORRECT for Python 3.8
from typing import Optional, List, Tuple
def func(x: Optional[str] = None): ...

# ❌ WRONG: Python 3.10+ only
def func(x: str | None = None): ...

# ✅ CORRECT: Pydantic v2 validator
from pydantic import field_validator
@field_validator("data")

# ⚠️ DEPRECATED (works but warns): Pydantic v1 style
from pydantic import validator
@validator("data")
```

**Installing spaCy on the NAS's Python 3.8 (for local tests).** Some of spaCy's compiled
dependencies no longer ship Python 3.8 wheels, and pip's fallback source build fails because
`/tmp` is mounted `noexec`. Force wheels and pin the last versions that have them:

```bash
python3 -m pip install --user --only-binary=:all: "spacy==3.7.5" "murmurhash==1.0.10" \
    "cymem==2.0.8" "preshed==3.0.9" "blis==0.7.11" "thinc==8.2.4" "srsly==2.4.8"
```

Containers use Python 3.11 and are unaffected.

### 4.4 Python Import Path (Hyphenated Folders)

```bash
# Folder names use hyphens (ADR convention)
# Python can't import from hyphenated names
# Solution: create symlinks at project root

ln -s db-logic db_logic
ln -s application-logic application_logic
ln -s presentation-logic presentation_logic

# Add to conftest.py for tests:
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

### 4.5 Docker Compose Environment Variables

```bash
# ✅ CORRECT: create .env file (auto-loaded by docker-compose ps)
cp .env.local .env

# ⚠️ WARNING: --env-file flag only works with up/down, not ps
sudo docker-compose --env-file .env.local up -d   # works
sudo docker-compose ps                             # shows warnings without .env
```

### 4.6 Cloudflare Tunnel

There is exactly **one** tunnel config: `deployment/cloudflared/config.yml`, mounted
read-only into the `cloudflared` service in `deployment/nginx/docker-compose.yml`. The old
host copy at `~/.cloudflared/config.yml` was **deleted on 2026-08-27** — keeping a second
copy meant a new subdomain could be added to one file and silently missed in the other.
Only the credentials (`958f0f40-….json`) and `cert.pem` remain in `~/.cloudflared/`.

```yaml
# ✅ CORRECT (deployment/cloudflared/config.yml)
ingress:
  - hostname: pandyahomelab.com
    service: https://pandya-nginx:443
    originRequest:
      noTLSVerify: true   # required for Nginx's self-signed cert

# ❌ WRONG: inside a container `localhost` is the container itself, not the NAS host
    service: https://localhost:8443

# ❌ WRONG: causes redirect loop (HTTP → HTTPS → Cloudflare → loop)
    service: http://pandya-nginx:80
```

**The container must run as root** — `user: "0:0"` in the compose service. The cloudflared
image is distroless and defaults to uid 65532 (`nonroot`), but the mounted config and
credentials live on `/volume1` under Synology ACLs that grant access only to
`avpadmin` / `admin` / `administrators`. `ls -la` shows mode `777` with a trailing `+`;
that mode is synthetic and the ACL is what the kernel enforces — check it with
`synoacltool -get <path>`. Without `user: "0:0"` the container crash-loops on
`open /etc/cloudflared/config.yml: permission denied`. This applies to **any** container
mounting `/volume1` files as a non-root user.

```bash
# ✅ CORRECT: the tunnel is a supervised container — start/stop it with the stack
cd /volume1/pandya-homelab/deployment/nginx/
sudo docker-compose up -d
sudo docker logs pandya-cloudflared | grep "Registered tunnel connection"

# ❌ WRONG: no supervision. This is what caused the 2026-07-11 → 07-26 outage —
# SIGTERM'd during a reboot, never restarted, Error 1033 for 15 days.
nohup cloudflared tunnel run pandya-homelab >> ~/cloudflared.log 2>&1 &

# ❌ WRONG: also killed when the terminal closes
cloudflared tunnel run pandya-homelab &
```

**Diagnosing Error 1033.** Every internal signal will look healthy — NAS up, all ports
open, Nginx returning 200 on every route — because nothing downstream of the tunnel is
broken. Check the tunnel first, not the site:

```bash
sudo docker ps --filter name=pandya-cloudflared      # should be Up, not Restarting
sudo docker logs --tail 20 pandya-cloudflared
curl -s http://172.24.0.3:20241/ready                # expect readyConnections: 4
```

The container's metrics port is bound inside `pandya-proxy-network` and deliberately not
published to the host, so `/ready` is reachable from the NAS host but not from the LAN.
A refused connection there (curl exit 7) means the container is not serving — host→container
routing is fine, as `curl -k https://172.24.0.2:443` (pandya-nginx) proves.

### 4.7 Mounting Data into Non-Root Demo Containers

Demo images run as `appuser` (uid 1000). Datasets that can't be baked into an image (licence)
are mounted read-only from the project's `data/` folder. The Synology ACL on `/volume1` denies
uid 1000 by default (same trap as cloudflared, §4.6). For a **web-facing** container reading
**public, non-secret** data, grant read to `everyone` on that folder instead of running as root:

```bash
synoacltool -add data/qqp "everyone:*:allow:r-x---a-R-c--:fd--"   # name must be `*`
synoacltool -get data/qqp/train.parquet | grep everyone          # files inherit it
```

Keep `user: "0:0"` only for port-less containers that mount secrets (cloudflared).

### 4.8 MLflow Idle Memory

MLflow 3.x starts a background job runner plus 6 worker processes (~1.1 GB idle) because
`MLFLOW_SERVER_ENABLE_JOB_EXECUTION` defaults to true. They serve GenAI-only features
(issue detection, LLM scorers, prompt optimisation) that this platform doesn't use. All three
trackers now run with it off and `--workers 2`, ~0.5 GB each (was 1.70 / 1.38 / 0.76 GB).
Keep both settings on any new tracker. Inspect a container's processes with
`sudo docker top <container> -eo rss,args`.

### 4.9 `/tmp` Is RAM on the NAS

`/tmp` is a tmpfs, so every file there uses memory (it shows up as `shared` in `free -m`).
1.1 GB of benchmark files once took available memory from 4.2 to 3.1 GB. Keep datasets and
models under the project's `data/` folder, not `/tmp`.

---

## 5. New Project Checklist (Phase 1b+)

For every new project, follow this checklist:

### 5.1 Pre-Development
- [ ] Assign port (next available: 8002 for ml-housing)
- [ ] Assign IP (next available: 172.20.0.11 for ml-housing)
- [ ] Verify no port conflicts: `sudo netstat -tlnp | grep <port>`
- [ ] Confirm ML infrastructure is running: `sudo docker-compose ps` in deployment/ml/

### 5.2 Project Scaffolding
- [ ] Create feature branch: `git checkout -b ml-housing-linear/scaffold`
- [ ] Copy template: `cp -r ml/_templates/ml-project-template/ ml/ml-housing-linear/`
- [ ] Update pyproject.toml: name, version, description
- [ ] Update README.md: project title and overview
- [ ] Update CHANGELOG.md: v1.0.0-alpha1 entry
- [ ] Create symlinks: `ln -s db-logic db_logic` etc.

### 5.3 Development
- [ ] Add dataset to `data/` (force-add if .gitignore blocks: `git add -f data/`)
- [ ] Implement db-logic: loader + preprocessor
- [ ] Implement application-logic: model + service
- [ ] Implement presentation-logic: routes + schemas + ui.html
- [ ] All imports use underscore names (db_logic, not db-logic)
- [ ] Use `Optional[str]` not `str | None` (Python 3.8 on NAS)
- [ ] fetch() in ui.html uses full path: `/ml/housing-linear/predict`

### 5.4 Testing (TIER 1)
```bash
python3 -m pytest tests/ -v
# Expected: all tests passing
```

### 5.5 Docker Build (TIER 2)
```bash
sudo docker build -f docker/Dockerfile -t ml-housing-linear:latest .
sudo docker run -d -p 8002:8000 --name ml-housing-linear ml-housing-linear:latest
sleep 15
curl http://localhost:8002/health
sudo docker stop ml-housing-linear && sudo docker rm ml-housing-linear
```

### 5.6 Integration (TIER 3)
```bash
# Add to docker-compose.dev.yml (port 8002, IP 172.20.0.11)
# Add upstream to nginx.conf
# Add /ml/housing-linear/ location block
# Rebuild Nginx: docker-compose down && docker build && docker-compose up -d
# Test: curl -k https://localhost:8443/ml/housing-linear/health
```

### 5.7 Nginx Update Pattern
```bash
# 1. Add upstream in nginx.conf
upstream ml_housing {
    server ml-housing-linear:8000 max_fails=3 fail_timeout=30s;
}

# 2. Add location block
location /ml/housing-linear/ {
    proxy_pass http://ml_housing/;
    ...
}

# 3. Update /ml/ listing
location = /ml/ {
    return 200 '{"domain":"ml","projects":["iris-knn","housing-linear"]}';
}

# 4. Rebuild Nginx
cd deployment/nginx/
sudo docker-compose down
sudo docker build -t pandya-nginx:latest .
sudo docker-compose up -d

# 5. Connect Nginx to ml-network (already done — no change needed)
```

### 5.8 Commit & Tag
```bash
git add .
git commit -m "feat(ml-housing-linear): implement housing price regression"
git checkout main
git merge --ff-only ml-housing-linear/scaffold
git tag v.ml-housing-linear-1.0.0
```

---

## 6. Docker Compose Startup Order

When starting fresh after NAS reboot:

```bash
# Step 1: ML infrastructure
cd /volume1/pandya-homelab/deployment/ml/
sudo docker-compose up -d
sleep 20

# Step 2: ML projects
sudo docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Step 3: Nginx + Cloudflare tunnel (the tunnel is now a service in this stack)
cd /volume1/pandya-homelab/deployment/nginx/
sudo docker-compose up -d
```

There is **no manual step 4 any more.** The tunnel runs as the `cloudflared` service in
`deployment/nginx/docker-compose.yml` with `restart: unless-stopped`, so it comes back
by itself after a reboot.

> ⚠️ **Do not start the tunnel with `nohup cloudflared tunnel run pandya-homelab &`.**
> That was the old step 4, and it is exactly what caused the 15-day outage: a bare
> background process has no supervision, so when it was SIGTERM'd during the
> 2026-07-11 reboot it never came back — while every container self-healed. The
> public site returned Error 1033 for 15 days with the NAS, Nginx, and all demos
> perfectly healthy. Running it manually now also risks two instances fighting over
> the tunnel. See §4.6.

---

## 7. Useful Diagnostic Commands

```bash
# Check all running containers
sudo docker ps

# Check container networks and IPs
sudo docker inspect <container> --format '{{range $net, $conf := .NetworkSettings.Networks}}{{$net}}: {{$conf.IPAddress}}{{"\n"}}{{end}}'

# Check port usage
sudo netstat -tlnp | grep <port>

# Check Nginx routing
curl -k https://localhost:8443/health
curl -k https://localhost:8443/ml/iris-knn/health

# Check cloudflared
ps aux | grep cloudflared | grep -v grep
tail -20 ~/cloudflared.log

# Purge Cloudflare cache (when page not updating)
# Cloudflare Dashboard → Caching → Purge Everything
```
