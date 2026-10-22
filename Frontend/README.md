# EAP Frontend

Web app of the Enterprise AI Agent Platform: sign-in, chat with streaming AI answers, document
knowledge base, meeting / report / email tools, history and the admin dashboard. It talks to the
backend (`../Backend`, FastAPI) over its REST + SSE API.

Next.js 16 (App Router) · TypeScript · Tailwind CSS v4 · shadcn/ui (Radix) · TanStack Query · Vitest

## Run locally

Prerequisites: Node 22+, and the backend running (see `../Backend/README.md`):

```bash
cd ../Backend && docker compose up -d && uv run uvicorn app.main:create_app --factory --reload
```

Then, in this folder:

```bash
npm install
cp .env.example .env.local       # PowerShell: copy .env.example .env.local
npm run dev                      # http://localhost:3000
```

Open the app at **http://localhost:3000** (not 127.0.0.1): the frontend and `NEXT_PUBLIC_API_URL`
must use the same host name or the sign-in cookie is not sent. Demo users are listed in
`../Backend/README.md`. Use the backend's `AI_MODE=fake` for UI work (no Mistral cost).

The design system reference page is at http://localhost:3000/styleguide (dev only).

## Scripts

| script                        | does                                                                |
| ----------------------------- | ------------------------------------------------------------------- |
| `npm run dev`                 | dev server with hot reload                                          |
| `npm run build` / `npm start` | production build / serve it                                         |
| `npm run lint`                | ESLint                                                              |
| `npm run typecheck`           | `tsc --noEmit`                                                      |
| `npm test` / `npx vitest run` | unit tests (watch / once)                                           |
| `npm run gen:api`             | regenerate `src/lib/api/schema.d.ts` from `../Backend/openapi.json` |
| `npm run format`              | Prettier (sorts Tailwind classes)                                   |

After the backend API changes: `cd ../Backend && uv run python scripts/export_openapi.py`, then
`npm run gen:api` and `npm run typecheck` here to see what needs updating.

## Environment

| variable              | dev                     | prod                                                    |
| --------------------- | ----------------------- | ------------------------------------------------------- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | empty (same origin; Nginx routes `/api` to the backend) |

## Layout

```
src/app/                 routes (App Router); globals.css holds all design tokens
src/components/ui/       shadcn components, adapted to the design system
src/components/common/   shared app components (wordmark, …)
src/lib/                 utilities; lib/api/ = generated API types and client
docs/FRONTEND_PLAN.md    phase plan, architecture and design system
```
