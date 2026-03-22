# Deployment Guide

## Backend (GCP VM)

**Host:** GCP VM accessible via `ssh ssh-social`
**URL:** https://moneyflow-api.skdev.one
**Port:** 8025 (Docker) → nginx reverse proxy → SSL via Let's Encrypt
**Project dir on VM:** `~/finance-agent`

### First-time setup

```bash
# Clone repo on VM
ssh ssh-social
cd ~
git clone https://github.com/rsumit123/finance-agent.git
cd finance-agent

# Build and run
docker build -t moneyflow-backend .
docker run -d --name moneyflow-backend --restart unless-stopped \
  -p 8025:8025 \
  -v ~/finance-agent/data:/app/data \
  moneyflow-backend

# Nginx config (already at /etc/nginx/sites-available/moneyflow-api.skdev.one)
# Proxies moneyflow-api.skdev.one → localhost:8025
# SSL managed by Certbot (auto-renews)
```

### Redeployment

```bash
ssh ssh-social "cd ~/finance-agent && git pull && \
  docker build -t moneyflow-backend . && \
  docker stop moneyflow-backend && \
  docker rm moneyflow-backend && \
  docker run -d --name moneyflow-backend --restart unless-stopped \
    -p 8025:8025 \
    -v ~/finance-agent/data:/app/data \
    moneyflow-backend"
```

### Verify

```bash
curl https://moneyflow-api.skdev.one/api/health
# {"status":"ok"}
```

### Logs

```bash
ssh ssh-social "docker logs moneyflow-backend --tail 50"
ssh ssh-social "docker logs moneyflow-backend -f"  # follow
```

### Nginx config location

- Available: `/etc/nginx/sites-available/moneyflow-api.skdev.one`
- Enabled: `/etc/nginx/sites-enabled/moneyflow-api.skdev.one`
- SSL cert: `/etc/letsencrypt/live/moneyflow-api.skdev.one/`

---

## Frontend (Vercel)

**Vercel project:** `moneyflow-ui`
**URL:** https://moneyflow.skdev.one
**Source dir:** `frontend/`

### Environment variables (set in Vercel dashboard/CLI)

| Variable | Value | Scope |
|---|---|---|
| `VITE_API_URL` | `https://moneyflow-api.skdev.one` | Production |

### First-time setup

```bash
cd frontend

# Link to Vercel project
npx vercel link  # select moneyflow-ui

# Set env var
echo "https://moneyflow-api.skdev.one" | npx vercel env add VITE_API_URL production

# Add custom domain
npx vercel domains add moneyflow.skdev.one

# Deploy
npx vercel --prod
```

### Redeployment

```bash
cd frontend
npx vercel --prod
```

### SPA routing

`frontend/vercel.json` has a rewrite rule to handle client-side routing:

```json
{ "rewrites": [{ "source": "/(.*)", "destination": "/" }] }
```

### DNS

- `moneyflow.skdev.one` → CNAME → `cname.vercel-dns.com` (frontend)
- `moneyflow-api.skdev.one` → A record → GCP VM IP (backend)

---

## Full redeploy (both)

```bash
# From project root
git push

# Backend
ssh ssh-social "cd ~/finance-agent && git pull && \
  docker build -t moneyflow-backend . && \
  docker stop moneyflow-backend && \
  docker rm moneyflow-backend && \
  docker run -d --name moneyflow-backend --restart unless-stopped \
    -p 8025:8025 \
    -v ~/finance-agent/data:/app/data \
    moneyflow-backend"

# Frontend
cd frontend && npx vercel --prod
```
