# Going live on managed services (free tiers)

The whole app on free plans, no server to manage:

| piece | service | free plan |
|---|---|---|
| website (Next.js) | **Vercel** | free, HTTPS, `<project>.vercel.app` address |
| API (FastAPI + AI module, Docker) | **Render** web service | free, 512 MB RAM, **sleeps after 15 min idle** (first request then takes ~1 min) |
| Postgres + file storage | **Supabase** (one project gives both) | 500 MB database, 1 GB files |
| Redis (rate limits, cache) | **Upstash** | free database |
| vector database | **Qdrant Cloud** | 1 GB cluster |
| AI models | **Mistral** (you already have a key) | your current plan |

How it fits together: the browser only ever talks to the Vercel address. Vercel forwards every
`/api/...` request to the Render API (`BACKEND_URL`, see `Frontend/next.config.ts`), so the login
cookie stays first-party and nothing needs a custom domain. Verified locally in exactly this mode:
sign-in + cookie refresh, chat streaming word by word, a 10 MB upload, download.

Never paste keys or passwords into chat, code or git: only into the services' dashboards (and your
local `Backend/.env`).

---

## 1. Collect the keys (about 30 minutes, all sign-ups work with "Continue with GitHub")

Keep a private note (e.g. a local text file, not in the repo) with each value as you get it.

### 1a. JWT secret (on your computer)
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
→ `JWT_SECRET`. Use a NEW one for production, not the one in your local `.env`.

### 1b. Mistral
Use the key you already rotated (console.mistral.ai → API Keys). → `MISTRAL_API_KEY`

### 1c. Supabase: database + file storage
1. supabase.com → **New project**. Name `eap`, a strong **database password** (save it), region
   close to you (e.g. Mumbai / `ap-south-1`).
2. **Database URL:** top bar **Connect** → **Session pooler** (works over IPv4) → copy the URI,
   put your password in place of `[YOUR-PASSWORD]` and add `?sslmode=require` at the end:
   `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require`
   → `DATABASE_URL` (the API converts this format itself, and percent-encodes special characters
   like `@` in the password, so paste it as Supabase shows it).
3. **File bucket:** **Storage** → **New bucket** → name `uploads`, keep it **private**.
4. **S3 keys:** **Storage** → **Settings** (S3 connection) → note the **Endpoint**
   (`https://<ref>.supabase.co/storage/v1/s3`) and **Region**, then **New access key** →
   copy the **Access key ID** and **Secret access key** (shown once).
   → `S3_ENDPOINT_URL`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

### 1d. Upstash: Redis
upstash.com → **Create database** (Redis, region near your Render region, free) → on its page,
**Connect** → copy the URL that starts with `rediss://default:...@...upstash.io:6379`.
→ `REDIS_URL` (note the double `s`: encrypted).

### 1e. Qdrant Cloud: vector database
cloud.qdrant.io → **Create cluster** → **Free** tier, a nearby region → when it's ready, copy the
**cluster URL** (`https://<id>.<region>.cloud.qdrant.io:6333`) and create/copy an **API key**.
→ `QDRANT_URL`, `QDRANT_API_KEY`

---

Before the next step you can test every key from your computer (prints no secrets):
`cd Backend; uv run python scripts/check_services.py <file with the values>`.

## 2. API on Render

1. render.com → **New** → **Web Service** → connect GitHub → pick
   `AshwinYadav816/enterprise-ai-agent-platform`.
2. Settings:
   - **Language / Runtime:** Docker
   - **Branch:** `main`
   - **Root Directory:** leave **empty** (the image needs both `Backend/` and `ai/`)
   - **Dockerfile Path:** `Backend/Dockerfile`  · **Docker Build Context Directory:** `.`
   - **Region:** the one **closest to your Supabase database** (Supabase in Tokyo /
     `ap-northeast-1` → **Singapore**). Every database query crosses this distance.
   - **Instance Type:** Free
   - **Health Check Path** (Advanced): `/api/v1/health`
3. **Environment Variables** (Advanced → Add from .env is fastest):

   ```
   ENV=prod
   AI_MODE=real
   JWT_SECRET=<1a>
   DATABASE_URL=<1c.2>
   REDIS_URL=<1d>
   MISTRAL_API_KEY=<1b>
   QDRANT_URL=<1e>
   QDRANT_API_KEY=<1e>
   STORAGE_BACKEND=s3
   S3_BUCKET=uploads
   S3_REGION=<1c.4>
   S3_ENDPOINT_URL=<1c.4>
   AWS_ACCESS_KEY_ID=<1c.4>
   AWS_SECRET_ACCESS_KEY=<1c.4>
   FORWARDED_ALLOW_IPS=*
   CORS_ORIGINS=["https://<your-vercel-project>.vercel.app"]
   ```
   (`CORS_ORIGINS` can be filled in after step 3; the site works without it because the
   browser calls the API through Vercel on the same address.)
4. **Create Web Service.** The first build takes ~5–10 minutes. On start the container runs the
   database migrations by itself. Done when the log shows `Application startup complete` and
   `https://<service>.onrender.com/api/v1/ready` shows `"status":"ready"` with database, redis,
   ai_config and qdrant all `ok`.

## 3. Website on Vercel

1. vercel.com → **Add New… → Project** → import the same GitHub repo.
2. **Root Directory:** `Frontend` (Framework preset: Next.js is detected).
3. **Environment Variables:** `BACKEND_URL` = `https://<service>.onrender.com` (no slash at the
   end). Do **not** set `NEXT_PUBLIC_API_URL` (empty = same address).
4. **Deploy** (~2 minutes). Your site: `https://<project>.vercel.app`.
5. Back in Render, set `CORS_ORIGINS` to that address (step 2.3) → it redeploys.

## 4. First data

1. **Demo users** (run once on your computer, writes to the production database):
   ```powershell
   cd Backend
   $env:DATABASE_URL = "<1c.2>"; uv run python scripts/seed_demo.py; Remove-Item Env:DATABASE_URL
   ```
   The demo passwords are public (README): sign in as admin and change it at
   **Settings → Change password**, or create your own users under **Admin → Users**.
2. Sign in, open **Documents**, upload the files from `ai/eval/docs/` (visibility: Employee) and
   wait for **Ready**. Then work through `ai/eval/TEST_QUESTIONS.md` on the live site.

## 5. Check it's really working

- Chat answers appear **word by word** (not all at once at the end).
- Upload a large file (10–25 MB) once: it should reach Ready.
- Download a document from Documents.
- Meetings / Reports / Email produce a result (they can take up to a minute).

## Day to day

- **Every `git push` to `main` redeploys both** (Render rebuilds the API, Vercel the site).
- **Free Render sleeps** after 15 minutes without requests: open the site ~1 minute before a demo.
- Logs: Render → service → **Logs**; Vercel → project → **Logs**.
- Changing a key: edit it in the dashboard → the service restarts with it.

## Troubleshooting

| symptom | cause / fix |
|---|---|
| Vercel shows `ROUTER_EXTERNAL_TARGET_ERROR` | the API took >120 s to answer, usually Render waking up; reload |
| sign-in works but you're logged out on refresh | `BACKEND_URL` missing or `NEXT_PUBLIC_API_URL` set on Vercel; fix and redeploy |
| `/ready` says `database` failed | `DATABASE_URL`: use the **Session pooler** URI with the real password |
| `/ready` says `qdrant` failed | `QDRANT_URL` must include `:6333`; check `QDRANT_API_KEY` |
| uploads fail, `Access Denied` in Render logs | S3 keys / bucket name / region / endpoint (1c.4) |
| "The AI service is busy right now" | Mistral is out of capacity; it switches models where it can, else retry later |
| Render deploy fails "out of memory" | free plan limit; Render **Starter** plan (512 MB → 2 GB) |
