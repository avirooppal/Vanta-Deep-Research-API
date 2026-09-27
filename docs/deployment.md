# Vanta Cloud Deployment Guide

Vanta can be deployed to any cloud provider in minutes.

---

## 1. Railway (1-Click)

1. In [Railway](https://railway.app), click **New Project** → **Deploy from GitHub repo**.
2. Railway reads [`railway.json`](../railway.json) and [`Procfile`](../Procfile).
3. Add a **PostgreSQL** database (with pgvector) and a **Redis** plugin from Railway.
4. Set environment variables:
   - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}`
   - `REDIS_URL`: `${{Redis.REDIS_URL}}`
   - `SECRET_KEY`: `<generate-32-chars>`
   - `SINGLE_CONTAINER_MODE`: `true`
5. Generate a public domain (e.g. `https://vanta-backend-production.up.railway.app`).

---

## 2. Render Blueprint (1-Click)

1. In [Render](https://render.com), click **New** → **Blueprint**.
2. Connect your repo; Render will read [`render.yaml`](../render.yaml).
3. It will provision the web service, PostgreSQL 16 with pgvector, and Redis.
4. Click **Apply**.

---

## 3. Fly.io

1. Run:
   ```bash
   fly launch --config fly.toml
   ```
2. Attach Fly Postgres with pgvector and Upstash Redis.
3. Deploy:
   ```bash
   fly deploy
   ```

---

## 4. Self-Hosted Cloud VPS (Caddy Automatic SSL)

For any Ubuntu/Debian server (DigitalOcean, Hetzner, AWS EC2, Linode):

```bash
cp deploy/env.cloud.example deploy/.env.cloud
# Set DOMAIN (e.g. api.yourdomain.com), ACME_EMAIL, PG_PASSWORD, REDIS_PASSWORD, SECRET_KEY
docker compose -f deploy/docker-compose.cloud.yml --env-file deploy/.env.cloud up -d --build
```
