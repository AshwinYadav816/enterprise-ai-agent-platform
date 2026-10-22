@AGENTS.md

# Frontend: Enterprise AI Agent Platform

Next.js 16 (App Router, `src/`, TypeScript strict) · Tailwind CSS v4 · shadcn/ui (Radix, `radix-nova`)
· TanStack Query · react-hook-form + zod · openapi-fetch. Plan: [docs/FRONTEND_PLAN.md](docs/FRONTEND_PLAN.md)
(one phase at a time). Backend: `../Backend` (FastAPI), AI module: `../ai`.

## Commands
```bash
npm run dev          # http://localhost:3000 (backend must run on http://localhost:8000)
npm run lint         # eslint
npm run typecheck    # next typegen (route types) + tsc --noEmit
npx vitest run       # unit tests (npm test = watch mode)
npm run gen:api      # regenerate src/lib/api/schema.d.ts from ../Backend/openapi.json
npm run format       # prettier (+ tailwind class sorting)
npm run build        # production build; run before committing a phase
```

## Rules
- **Never hand-write API types.** Use `paths` / `components` from `src/lib/api/schema.d.ts`; after any
  backend change run `npm run gen:api`, then `npm run typecheck` shows what broke.
- **Colors only through tokens** (`bg-primary`, `text-coral-text`, `bg-blue-tint`, `bg-success-tint`…),
  defined once in `src/app/globals.css`. No hex values in components.
- **Coral rule:** `coral` only for small non-text accents (active-nav bar, streaming cursor, new dots,
  wordmark dot, chart highlight). Coral text = `text-coral-text`. Never coral on buttons, large
  surfaces, body text or errors. shadcn `accent` = blue-tint hover, not coral.
- **Typography:** `type-display` / `type-title` / `type-answer` (Newsreader), `type-body` / `type-small`
  / `type-eyebrow` (Inter), `font-mono`. Use these utilities, not new `text-[size]` values.
- **Depth by borders** (`border bg-card`); only popovers/menus/dialogs use `shadow-pop`.
- **Auth:** access token only in memory (module variable + context). Never localStorage /
  sessionStorage. The refresh cookie is httpOnly, path `/api/v1/auth`, SameSite=Lax: the browser must
  use `localhost` for BOTH the frontend and `NEXT_PUBLIC_API_URL` (never mix with 127.0.0.1).
- **Streaming chat:** `@microsoft/fetch-event-source` (POST + auth header), `openWhenHidden: true`,
  `onerror` rethrows (no auto retry), never `EventSource`. Only research/chat stream `token`s;
  meeting/email/report/document send `status` then a `result` card. Chat accepts `transcript`.
- **Downloads** go through `downloadFile()` (fetch with auth → blob), never `<a href>` to the API.
- **Markdown:** react-markdown + remark-gfm, no raw HTML, no `dangerouslySetInnerHTML`.
- **No `any`.** Server errors are `{error: {code, message}}`; show `message`.
- Accessibility: visible focus, aria-labels on icon buttons, status = text + icon (never colour alone),
  works at 390 px wide, respects `prefers-reduced-motion`.
- Poll only while something is `processing`.

## API layer (Phase 1)
- `api` (`lib/api/client.ts`): typed openapi-fetch client; paths include `/api/v1`
  (`api.GET("/api/v1/users/me")`). Wrap results with `unwrap()` → data or throws `ApiError`
  (`status`, `code`, `message`, `details` for 422 fields).
- Everything authenticated goes through `authFetch` (`lib/api/auth.ts`): Bearer token, 401 → one
  refresh → one retry; auth endpoints are never retried. Reuse it for downloads and the SSE stream.
- **Refresh is dangerous to duplicate**: the backend rotates the cookie and revokes ALL sessions if
  an old one is replayed. Only call `refreshAccessToken()` (single-flight in the tab + Web Locks
  across tabs); never POST /auth/refresh directly.
- `useAuth()` → `{user, status, login, register, logout, refreshUser}`; `login`/`register` return the
  session (check `must_change_password`). Session restore uses the user from the refresh response
  (no extra GET /users/me).
- Query keys only from `lib/api/keys.ts`. Mutations toast errors globally; pass
  `meta: { silentError: true }` when the form shows the error itself. Queries retry once, never on 4xx.
- Downloads: `downloadFile("/documents/{id}/download", "fallback.pdf")`.

## Shell, guards, forms (Phase 2)
- Route groups: `(auth)` = login/register/change-password (split-screen layout), `(app)` = everything
  behind `<AuthGuard>` + `AppShell` (sidebar ≥ lg, top bar + Sheet below). `/admin/*` has its own
  `AuthGuard adminOnly`. Guards use `useSearchParams`, so they wrap themselves in `<Suspense>`.
- Redirect rules live in `lib/redirects.ts` (`safeNext` blocks open redirects; `postLoginPath`
  handles must_change_password). Login/register don't navigate themselves: `GuestGuard` does.
- New nav entries go in `components/layout/nav-items.ts`.
- Forms: react-hook-form + zod + `TextField`/`PasswordField`/`FormAlert` and
  `handleFormError(error, setError, fields)` from `components/auth/form-fields.tsx` (422 details →
  fields, everything else → `errors.root.server`). Schemas mirror backend limits.
- Pages: server `page.tsx` exporting `metadata` + `PageHeader`; interactive parts are client
  components. `EmptyState` / `ErrorState` for empty and failed data.
- Don't put `aria-expanded` on ghost/outline buttons unless they control a popup: shadcn styles
  `aria-expanded:bg-accent` (it looked permanently pressed).

## Documents (Phase 3)
- File rules and role helpers: `lib/documents.ts` (`validateFile`, `visibilityOptions`,
  `VISIBILITY_LABEL`, `ROLE_ORDER`); formatting: `lib/format.ts` (`formatBytes`, `formatRelative`).
- `useDocuments(filters)` = infinite query + 3 s polling only while something is processing +
  ready/failed toasts. Multipart uploads use `uploadDocument()` (authFetch + FormData), not `api`.
- Backend `DocumentOut.owner_name` exists for the Owner column (added in this phase).
- shadcn dialog footers use `-mx-5 -mb-5` to match our `p-5` dialog padding.

## Chat (Phase 4)
- `lib/api/sse.ts` `streamMessage()` = fetchEventSource POST (openWhenHidden, onerror rethrows,
  one retry only after a 401 + refresh). Event shapes: `lib/chat/types.ts`.
- Live replies live in `lib/chat/stream-store.ts` (module store keyed by conversation, read via
  `useChatStream`), NOT component state: survives /chat → /chat/[id] and hidden routes. Phases
  streaming → settling → cleared once the saved reply is fetched (`knownMessageIds` / `messageId`);
  `failed` = refused before saving (Retry). Navigation never stops a reply; only Stop does.
  `resetStreams()` on logout.
- History uses `GET …/messages?order=desc` (backend param added in Phase 4) → newest page first.
- Only research/chat stream tokens; meeting/email/report/document answers arrive in `done` + a
  `result` card. A single card agent's answer text is hidden (it repeats the card).
- `[n]` → citation chip only if source n exists (`lib/chat/citations.ts`); raw HTML never rendered.
- `/chat*` pages are full-bleed in AppShell (own height + scrolling).
- Backend `FAKE_AI_DELAY_MS=80` (Backend/.env) makes fake replies stream visibly.
- Headless Chrome blocks repeated automatic downloads in a reused profile: test downloads in a
  fresh profile (the app itself is fine).

## Next.js 16 notes (verified in node_modules/next/dist/docs)
- `cacheComponents` + `partialPrefetching` are on. Recently visited routes stay mounted (hidden with
  React `<Activity>`) instead of unmounting: effects are cleaned up when hidden, but component state
  survives. Matters for chat streams, dialogs and polling (see docs/…/preserving-ui-state).
- Pages/layouts get typed props via the global `PageProps<"/route">` / `LayoutProps<"/route">`.
- No Next middleware/proxy for auth: guards are client-side (backend enforces auth anyway).
- `experimental.instantInsights.validationLevel = "manual-warning"`: automatic instant-navigation
  validation can't see pages behind the client guard and flagged every page as "dropped".
- `LayoutProps`/`PageProps` come from `next typegen` (.next/types); `npm run typecheck` runs it.

## Gotchas
- `cn` comes from the `cn` package (shadcn's drop-in for clsx + tailwind-merge); `@/lib/utils`
  re-exports it. Custom `text-*` font sizes would be mistaken for colours by the merger, which is why
  the type scale uses `type-*` utilities.
- shadcn's old `form` component is gone; use `field.tsx` (`Field`, `FieldLabel`, `FieldError`, …)
  with react-hook-form's `Controller`/`register`.
- `@hookform/resolvers` is pinned to v5 (v6 has an npm peer conflict). `@types/node` ^22 (vitest 5).
  Vitest needs no React plugin: Vite 8/oxc compiles TSX, `resolve.tsconfigPaths` handles `@/*`.
- On Windows, if `next dev` dies with a Turbopack panic "exit code 0xc0000142", stop the dev server,
  delete `.next`, start again.
- Git: team repo, work on `main`; stage only this folder (plus `ai/`, `Backend/` when changed).
  `.env.local` is ignored; `.env.example` is committed.
