# EAP Frontend

Web app of the Enterprise AI Agent Platform: sign-in, chat with streaming AI answers and
citations, the document knowledge base, meeting / report / email tools, history, settings and the
admin dashboard. It talks to the backend (`../Backend`, FastAPI) over REST + Server-Sent Events.

Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui (Radix) ·
TanStack Query · Vitest · Playwright

## Run locally

Prerequisites: Node 22+, and the backend running (see `../Backend/README.md`; `AI_MODE=fake`
needs no Mistral key):

```bash
cd ../Backend && docker compose up -d && uv run uvicorn app.main:create_app --factory --reload
```

Then, in this folder:

```bash
npm install
cp .env.example .env.local       # PowerShell: copy .env.example .env.local
npm run dev                      # http://localhost:3000
```

Open **http://localhost:3000** (not 127.0.0.1): the frontend and `NEXT_PUBLIC_API_URL` must use
the same host name or the sign-in cookie is not sent. Demo users (from the backend seed):

| role     | email                  | password          |
| -------- | ---------------------- | ----------------- |
| admin    | admin@acme-demo.com    | Admin@Demo2026    |
| manager  | manager@acme-demo.com  | Manager@Demo2026  |
| employee | employee@acme-demo.com | Employee@Demo2026 |

## Environment

| variable              | dev                     | production                                                   |
| --------------------- | ----------------------- | ------------------------------------------------------------ |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | **empty** = same origin (Nginx routes `/api` to the backend) |

It is inlined into the browser bundle at **build** time (a Docker build argument, not a runtime
variable).

## Scripts

| script                        | does                                                                |
| ----------------------------- | ------------------------------------------------------------------- |
| `npm run dev`                 | dev server with hot reload                                          |
| `npm run build` / `npm start` | production build / serve it                                         |
| `npm run lint`                | ESLint                                                              |
| `npm run typecheck`           | route types (`next typegen`) + `tsc --noEmit`                       |
| `npm test` / `npx vitest run` | unit tests (watch / once)                                           |
| `npx playwright test`         | end-to-end tests (below)                                            |
| `npm run gen:api`             | regenerate `src/lib/api/schema.d.ts` from `../Backend/openapi.json` |
| `npm run check:api`           | fails if `schema.d.ts` is out of date (for CI)                      |
| `npm run format`              | Prettier (sorts Tailwind classes)                                   |

### When the backend API changes

```bash
cd ../Backend && uv run python scripts/export_openapi.py   # writes openapi.json
cd ../Frontend && npm run gen:api && npm run typecheck      # shows exactly what broke
```

API types are never written by hand; `schema.d.ts` is generated and committed. The one exception
is the chat stream (SSE events and agent result cards, `src/lib/chat/types.ts`), which OpenAPI
can't describe: `Backend/tests/test_frontend_contract.py` fails if the AI module's result shapes
change, so the frontend gets updated with them.

### End-to-end tests (Playwright)

Four flows against the real stack: forced password change for a new user, document upload until
ready (then delete), chat streaming that survives a reload, and an admin creating a user.

```bash
# backend running with AI_MODE=fake (the chat test expects the fake answer)
npx playwright test             # starts `npm run dev` if nothing is on :3000
npx playwright test --ui        # watch them
```

- Uses the installed Google Chrome locally; on CI run `npx playwright install chromium` and set `CI=1`.
- Accounts default to the seed users; override with `E2E_ADMIN_EMAIL`, `E2E_ADMIN_PASSWORD`,
  `E2E_MANAGER_*`, `E2E_EMPLOYEE_*`. Point at another deployment with `E2E_BASE_URL` (frontend)
  and `E2E_API_URL` (API; the same URL behind Nginx).
- Tests clean up after themselves (users created are deactivated, uploads and conversations
  deleted). Login is rate-limited to 5 per minute per account: wait a minute between full runs.

## Docker

```bash
docker build -t eap-frontend .                                   # same origin (behind Nginx)
docker build -t eap-frontend --build-arg NEXT_PUBLIC_API_URL=https://api.example.com .
docker run --rm -p 3000:3000 eap-frontend
```

Multi-stage on `node:22-alpine`: `npm ci`, `next build` with `output: "standalone"`, and a small
runtime image (~340 MB) that runs `node server.js` as the non-root `node` user on port 3000, with a
health check on `/login`. `.dockerignore` is a whitelist, so `.env*` never enters the image.

## Notes for deployment (Member 4)

Serve the frontend and the API on **one domain**: Nginx sends `/api` to the backend and
everything else to this container. The refresh cookie (httpOnly, path `/api/v1/auth`,
SameSite=Lax) and the chat stream both depend on that. Build the image with an empty
`NEXT_PUBLIC_API_URL`.

Tested configuration (frontend container + backend, full Playwright suite passing through it):

```nginx
server {
    listen 80;
    server_name your.domain;
    client_max_body_size 26m;                   # 25 MB uploads + multipart overhead

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Chat answers are Server-Sent Events: no buffering, long reads (the API pings every 15 s).
    # A REGEX location on purpose: a prefix location ending in "/" (location /api/v1/conversations/)
    # makes Nginx 301-redirect GET /api/v1/conversations and breaks the conversation list.
    location ~ ^/api/v1/conversations/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    location / {
        proxy_pass http://frontend:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- Production: HTTPS, and the backend with `ENV=prod` (the refresh cookie becomes `Secure`) and
  `FORWARDED_ALLOW_IPS` set to the proxy (see `../Backend/README.md`).
- Check streaming after deploying: send a chat message and the answer should appear word by
  word, not all at once at the end.

## Layout

```
src/app/                 routes (App Router); globals.css holds all design tokens
src/components/ui/       shadcn components, adapted to the design system
src/components/…         feature components (chat, documents, tools, admin, layout, common)
src/lib/                 API client + auth, SSE, hooks, formatting
e2e/                     Playwright flows
docs/FRONTEND_PLAN.md    phase plan, architecture and design system
CLAUDE.md                conventions for working on this code
```
