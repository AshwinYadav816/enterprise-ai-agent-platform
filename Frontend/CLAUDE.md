@AGENTS.md

# Frontend: Enterprise AI Agent Platform

Next.js 16 (App Router, `src/`, TypeScript strict) · Tailwind CSS v4 · shadcn/ui (Radix, `radix-nova`)
· TanStack Query · react-hook-form + zod · openapi-fetch. Plan: [docs/FRONTEND_PLAN.md](docs/FRONTEND_PLAN.md)
(one phase at a time). Backend: `../Backend` (FastAPI), AI module: `../ai`.

## Commands
```bash
npm run dev          # http://localhost:3000 (backend must run on http://localhost:8000)
npm run lint         # eslint
npm run typecheck    # tsc --noEmit
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

## Next.js 16 notes (verified in node_modules/next/dist/docs)
- `cacheComponents` + `partialPrefetching` are on. Recently visited routes stay mounted (hidden with
  React `<Activity>`) instead of unmounting: effects are cleaned up when hidden, but component state
  survives. Matters for chat streams, dialogs and polling (see docs/…/preserving-ui-state).
- Pages/layouts get typed props via the global `PageProps<"/route">` / `LayoutProps<"/route">`.
- No Next middleware/proxy for auth: guards are client-side (backend enforces auth anyway).

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
