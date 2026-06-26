# Deploying CloneLM to Railway

CloneLM deploys as **three Railway components in one project**, built straight
from this Git repo by Railway's default builder (**Railpack**) — no Dockerfile:

| Component | Source | Notes |
| --- | --- | --- |
| **Postgres + pgvector** | template | the data + vector store |
| **backend** | `backend/` | FastAPI; embeds via **Voyage AI** in this mode |
| **frontend** | `frontend/` | React/Vite static bundle served by `serve` |

> ⚠️ **Set each service's Root Directory** (`backend` / `frontend`) in the Railway
> UI. This is what makes Railway detect that service's `railway.toml` and project
> files — without it Railpack analyzes the repo **root** (no project there) and the
> build fails. The `railway.toml` files intentionally set **no** `builder`, so
> Railpack auto-detects uv/Python and Node (pinning Nixpacks fails on uv projects
> unless `$NIXPACKS_UV_VERSION` is set).

The hosted build flips `DEPLOYED=true`, which makes the app **multi-user**:
accounts + login are required, each user brings their **own** Anthropic + Voyage
keys (stored encrypted), embeddings run on **Voyage AI** (no GPU), and the
local-model (Ollama) option is hidden. Both bge-m3 and `voyage-3.5` emit 1024-dim
vectors, so the schema is unchanged. Per-user isolation: a user only ever sees
their own notebooks.

## Prerequisites

- This repo pushed to GitHub.
- A **JWT secret** and a **Fernet encryption key** for the server (generated
  below) — the server itself holds **no** model API keys.
- **Each user** signs up with their own **Anthropic** (`sk-ant-…`) and **Voyage**
  (`pa-…`, <https://dash.voyageai.com>) keys. As the operator/evaluator you'll
  register an account with your own keys to try it.

## 1. Create the project + database

1. Railway → **New Project** → **Deploy from GitHub repo** → pick this repo.
2. **New → Database**. Use a **pgvector-enabled Postgres** — search Railway
   templates for **“pgvector”** (image `pgvector/pgvector`, same as our
   `docker-compose.yml`). The backend's first migration runs
   `CREATE EXTENSION IF NOT EXISTS vector`, which needs that image. (The plain
   Postgres plugin may not bundle the extension.)

## 2. Backend service

Add a service from the repo and set **Settings → Root Directory = `backend`**
(Railway then picks up `backend/railway.toml`). Under **Variables**:

| Variable | Value |
| --- | --- |
| `DEPLOYED` | `true` |
| `APP_ENV` | `production` |
| `JWT_SECRET` | a long random string — `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SECRET_ENCRYPTION_KEY` | a Fernet key — `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference the DB service) |
| `CORS_ORIGINS` | your frontend URL — fill in after step 3 |

The server holds **no** model keys — `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY` are
**not** needed (each user supplies their own at registration). `DATABASE_URL`
arrives as `postgresql://…`; the app rewrites it to the `postgresql+psycopg://…`
driver scheme automatically, so paste it as-is.

> **Keep `JWT_SECRET` and `SECRET_ENCRYPTION_KEY` safe and stable.** Rotating
> `SECRET_ENCRYPTION_KEY` makes every stored user key undecryptable (users would
> re-enter their keys); rotating `JWT_SECRET` invalidates active sessions.

Under **Settings → Networking → Generate Domain** to get the backend URL, e.g.
`https://clonelm-backend.up.railway.app`. The start command runs
`alembic upgrade head` (creates the pgvector extension + schema) before booting.

## 3. Frontend service

Add a second service from the same repo, **Root Directory = `frontend`**. Under
**Variables**:

| Variable | Value |
| --- | --- |
| `VITE_API_BASE` | the backend URL from step 2 (e.g. `https://clonelm-backend.up.railway.app`) |

`VITE_API_BASE` is **build-time** — Vite inlines it into the bundle, so it must
be set before the build and a change to it requires a redeploy. **Generate a
Domain** for this service too — that public URL is the one you share.

## 4. Wire the two together

1. Set the backend's `CORS_ORIGINS` to the **frontend** domain from step 3
   (comma-separated if you have several).
2. Redeploy the backend (CORS change) and the frontend (so the build picks up
   `VITE_API_BASE`).

Open the frontend URL — that's your shareable CloneLM. Visitors **register** an
account with their own Anthropic + Voyage keys, then get their own isolated
notebooks. (The backend runs `alembic upgrade head` on boot, which creates the
`app_user` table.)

## Notes

- **Multi-user isolation** is enforced server-side: every notebook is owned by a
  user, and cross-user access returns 404. Passwords are argon2id-hashed; API
  keys are Fernet-encrypted at rest and never returned to the client.
- **Audio Overview** falls back to a silent WAV here: the local Piper neural TTS
  lives in the opt-in `audio` extra, which the lean hosted build doesn't install.
  To enable real audio, set `backend/railway.toml`'s build to install it
  (`uv sync --extra audio`) and accept the heavier image.
- **Secrets** live only in Railway Variables — never commit them. Use a long
  `JWT_SECRET` (32+ bytes) and a real Fernet `SECRET_ENCRYPTION_KEY`.
- **Switching back to local** is just `DEPLOYED=false` (the default, single-user,
  no login) on a machine with the `embeddings` extra installed
  (`uv sync --extra embeddings`).
