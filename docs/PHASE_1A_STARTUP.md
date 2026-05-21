# Phase 1a Startup Checklist

## Step 0: Docker Access Setup

Before proceeding with infrastructure tests, grant docker access:

**Option A: Add user to docker group (recommended)**
```bash
sudo usermod -aG docker avpadmin
newgrp docker
docker ps  # Verify it works
```

**Option B: Use sudo for all docker commands**
```bash
sudo docker-compose up -d
```

## Step 1a.0: Pre-Development Infrastructure Verification

### 1.1 Build Nginx container
```bash
cd /volume1/pandya-homelab/deployment/nginx/
sudo docker build -t pandya-nginx:latest .
```
**Expected:** Image builds cleanly, size ~50-100MB

### 1.2 Start ML domain infrastructure
```bash
cd /volume1/pandya-homelab/deployment/ml/
docker-compose --env-file .env.local config  # Validate syntax
docker-compose --env-file .env.local up -d   # Start services
sleep 15
docker-compose ps                             # Check health
```
**Expected output:**
```
NAME         IMAGE              STATUS
ml-postgres  postgres:15-alpine Up (healthy)
ml-minio     minio/minio:latest Up (healthy)
ml-redis     redis:7-alpine     Up (healthy)
ml-mlflow    ghcr.io/mlflow...  Up (healthy)
```

### 1.3 Test service connectivity
```bash
docker exec ml-postgres psql -h ml-postgres -U postgres -d mldb -c "SELECT 1"
docker exec ml-minio curl -f http://ml-minio:9000/minio/health/live
docker exec ml-redis redis-cli -h ml-redis ping
```
**Expected:** All commands return success (1, OK, PONG)

### 1.4 Test Nginx reverse proxy
```bash
cd /volume1/pandya-homelab/deployment/nginx/
docker run -d -p 80:80 -p 443:443 \
  --name test-nginx \
  -v /volume1/pandya-homelab/website:/var/www/html:ro \
  pandya-nginx:latest

sleep 5
curl http://localhost/health
curl http://localhost/
docker stop test-nginx && docker rm test-nginx
```
**Expected:** /health returns OK, landing page loads

## Phase 1a.0 Exit Criteria

- [x] All infrastructure services healthy (postgres, minio, redis, mlflow)
- [x] Nginx /health endpoint works
- [x] All services discoverable by hostname (172.20.0.x)
- [x] No errors in logs

**Status:** Ready to proceed to Phase 1a.1 (Project Scaffolding)
