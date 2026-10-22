# Frontend Development Plan — Enterprise AI Agent Platform
Owner: Member 1 (Frontend Development) · Scope: UI, dashboard, authentication screens, chat interface, file upload module
Works with: Member 2 (backend API, `openapi.json`) · Member 3 (AI result shapes) · Member 4 (Docker, Nginx, deploy)

> **Agreed deviations from the original text (2026-10-22)**
> - The folder is `Frontend/` and the backend is `Backend/` (capital letters; paths matter in Docker/CI).
>   Every `backend/…` / `frontend/…` path below means `Backend/…` / `Frontend/…`.
> - Git: commit on `main` with the team flow (add → commit → pull --rebase → push), no branch/PR per phase.
> - Phase 4 composer adds **Attach transcript** (paste or .txt/.vtt) sent as the chat `transcript` field
>   (needed for the meeting → email demo). Only research/chat stream `token`s; meeting, email, report and
>   document send `status` then a `result` card. Result cards get **Download PDF** via
>   `GET /conversations/{id}/messages/{message_id}/results/{index}/pdf`.
> - The doc picker only offers `ready` documents (the backend returns 409 `document_not_ready` otherwise).
> - Next.js 16.4 with `cacheComponents` (routes stay mounted when hidden); see `CLAUDE.md`.
> - `success` token darkened to `#2A7353` (AA on its badge tint); badge tints added for success, warning,
>   destructive. shadcn `form` is replaced by `field`.

---

## Part A — How to use this with Claude Code (read once)

**Setup**
1. `Frontend/CLAUDE.md` holds the working rules; this file is `Frontend/docs/FRONTEND_PLAN.md`.
2. Open Claude Code inside `Frontend/`.
3. **One phase per session.** Paste only that phase's "Prompt" block.
4. When "Done when" passes: commit, `/clear`, next phase.

**Why this saves tokens**
- API types are **generated** from the backend's `openapi.json`: Claude Code never writes or guesses request/response types.
- Design tokens are defined once (Phase 0) and mapped onto shadcn's variables, so every component is on-brand without per-component styling work.
- You develop against the **real backend in `AI_MODE=fake`**: streaming and all endpoints work, no mock server to build, no Mistral spend.
- `/clear` between phases; plan mode (Shift+Tab) for Phase 4 (chat); paste exact errors and say "fix this".
- Visual check yourself in the browser — describing "the button looks off" with a screenshot is cheaper than Claude Code guessing.

**Before you start each session**
```bash
# terminal 1 — backend (see Backend/README.md)
cd Backend && docker compose up -d && uv run uvicorn app.main:create_app --factory --reload
# terminal 2 — frontend
cd Frontend && npm run dev        # http://localhost:3000
```
Log in with the users from `Backend/scripts/seed_demo.py`.

**Your checks after every phase (3 minutes)**
- `npm run lint` · `npm run typecheck` · `npx vitest run` green.
- Click through the new screens at desktop width **and** ~390 px (phone) width.
- Tab through the page with the keyboard: you can see where focus is and reach every action.
- Grep the diff for `#` hex colors in components, `localStorage`, `any`, `dangerouslySetInnerHTML` — should be none.

---

## Part B — Architecture decisions (already made)

| Decision | Choice | Reason |
|---|---|---|
| Framework | Next.js App Router, TypeScript strict, `src/` dir, `@/*` alias | PRD stack; file-based routing keeps pages organised |
| Rendering | Route groups `(auth)` and `(app)`; authenticated pages are client components inside a server layout shell | Data is per-user behind a Bearer token held in memory, so it's fetched client-side |
| Route protection | **Client-side** `AuthProvider` + guards. No Next middleware/proxy for auth | The refresh cookie is scoped to `/api/v1/auth` on the backend, so Next can't see it. Backend enforces auth anyway |
| API URL | `NEXT_PUBLIC_API_URL` — `http://localhost:8000` in dev, empty (same origin, Nginx routes `/api`) in prod | Same-site in both cases → refresh cookie works |
| API client | `openapi-typescript` generates `schema.d.ts` from `../Backend/openapi.json`; `openapi-fetch` client with middleware that adds the Bearer token and handles 401 → refresh → retry once | Fully typed, zero hand-written API types |
| Token handling | Access token in a module variable + React context. On load: `POST /auth/refresh` → then `GET /users/me`. Concurrent 401s share ONE refresh promise | Secure (no JS-readable token storage) and no refresh storms |
| Server state | TanStack Query; keys in `lib/api/keys.ts`; mutations invalidate exact keys | Caching, polling, retries for free |
| Forms | react-hook-form + zod; server errors mapped to fields or a toast | Consistent validation, little code |
| Streaming chat | `@microsoft/fetch-event-source` (POST + auth header). `openWhenHidden: true`, and `onerror` **throws** (no auto-retry) | Default retry/visibility behaviour would re-POST and duplicate messages |
| Markdown | react-markdown + remark-gfm, no raw HTML. `[n]` citations converted to footnote chips | Safe rendering, editorial-style citations |
| Downloads | Fetch as blob with the auth header → object URL → click → revoke | Plain `<a href>` can't send the Bearer token |
| Charts | recharts (shadcn chart wrapper) with the chart palette from Part C | Matches the design system |
| Toasts | sonner; API errors use the backend message `{error: {code, message}}` | One error path |
| Testing | Vitest + Testing Library for logic and key components; Playwright for 4 end-to-end flows against the real stack (fake AI) | Confidence without a big test suite |
| Theme | Light theme only for the project; tokens structured so dark mode can be added later | Keeps scope realistic; ivory is the identity |

### Route map
```
/                      → redirect: /chat if logged in, else /login
/login  /register  /change-password (forced when must_change_password)
/chat                  new conversation          /chat/[id]   existing conversation
/documents             knowledge base (upload, list, status, insights)
/meetings              meeting assistant          /reports     report generator
/email                 email assistant            /history     all generations   /history/[id]
/settings              profile + password
/admin                 dashboard (admin only)     /admin/users   /admin/activity
```

### App shell
- **Left sidebar (desktop ≥ 1024 px, collapsible; sheet/drawer on mobile):** wordmark · "New chat" button · nav (Chat, Documents, Meetings, Reports, Email, History) · Admin section (admins only) · user menu at bottom (name, role badge, Settings, Log out).
- **Chat page** adds a second column: conversation list (search, rename, delete).
- **Top bar (mobile only):** menu button, page title.

---

## Part C — Design system: Warm Ivory · Deep Editorial Blue · Touch of Coral

**Feel:** a well-made print publication — calm ivory paper, confident ink-blue type, generous whitespace, thin rules instead of heavy boxes, one warm coral detail that draws the eye. Not a generic SaaS dashboard.

### Color tokens (contrast checked against WCAG AA)
| Token | Hex | Use | Contrast |
|---|---|---|---|
| `background` | `#FAF6EE` | page (warm ivory) | — |
| `card` / `popover` | `#FFFDF8` | cards, dialogs, menus | — |
| `muted` | `#F3EDE1` | sidebar, table headers, inputs' hover, skeletons | — |
| `border` / `input` | `#E6DDCC` | 1 px rules, input borders (inputs use `#D9CFBC` for visibility) | — |
| `foreground` (ink) | `#1A2233` | body text (blue-black, never pure black) | 14.8 : 1 |
| `muted-foreground` | `#5B6475` | secondary text, captions | 5.5 : 1 |
| `primary` (editorial blue) | `#1D3461` | primary buttons, links, active nav text, headings accents | 11.4 : 1 |
| `primary-foreground` | `#FAF6EE` | text on blue | 11.4 : 1 |
| `primary-hover` | `#162849` | hover/pressed blue | — |
| `blue-tint` | `#E6ECF5` | selected rows, active nav background, user chat bubble | blue on it 10.3 : 1 |
| `coral` | `#E8664A` | **accent fills only**: active-nav indicator bar, streaming cursor, unread/new dots, chart highlight series, logo dot | 3.0 : 1 (non-text only) |
| `coral-text` | `#B8452B` | coral-coloured *text* (e.g. "New" label, small highlights) | 5.0 : 1 |
| `coral-tint` | `#FCE8E1` | coral badge backgrounds (with `coral-text`) | 4.5 : 1 |
| `success` | `#2A7353` (plan: `#2F7D5B`) | ready status, success toasts | 5.3 : 1 (4.9 on its tint) |
| `warning` | `#8A5A00` | processing status | 5.5 : 1 |
| `destructive` | `#B42318` | delete, failed status, errors (kept clearly redder than coral) | 6.1 : 1 |
| `ring` | `#1D3461` | focus ring (2 px, 2 px offset) | — |

Added in Phase 0: `success-tint #E4F1E9`, `warning-tint #F8EED9`, `destructive-tint #FBE7E4` (badge backgrounds).

**Chart palette (in order):** `#1D3461` blue · `#E8664A` coral · `#6B8CB8` soft blue · `#D9A441` ochre · `#5E8C7A` sage. Gridlines `#E6DDCC`, axis text `#5B6475`.

### The coral rule (this is what makes it look designed)
- Blue does the work (buttons, links, selection). Coral is the **signature**, ~5 % of any screen.
- Coral **never** on: primary buttons, large surfaces, body text, error states.
- Coral **always** on: active-nav indicator (3 px left bar), the blinking cursor while the AI streams, the dot in the wordmark, the first series in a chart that needs emphasis, "new/unread" dots.
- Coral text only in `coral-text` (`#B8452B`), never `#E8664A`, because plain coral fails text contrast.

### shadcn mapping (important)
shadcn's `--accent` is the **hover background of menus and ghost buttons**. Set `--accent` = `blue-tint` (`#E6ECF5`) and `--accent-foreground` = `primary`. Define coral as **separate** tokens (`--coral`, `--coral-text`, `--coral-tint`), otherwise every hover turns coral. Also map `--secondary` = `muted`, `--sidebar*` variables = `muted`/`primary`/`blue-tint`, `--chart-1..5` = chart palette.

### Typography (next/font/google)
- **Headings & AI answers:** *Newsreader* (serif) — page titles 32/40 semibold, section titles 22/28, assistant chat messages 17/28 regular. This serif is the "editorial" voice.
- **UI & body:** *Inter* — 15/24 base, 13/20 small, labels 12 px uppercase with 0.06em tracking for section eyebrows.
- **Code / IDs:** *JetBrains Mono* 13 px.
- Implemented as utilities `type-display`, `type-title`, `type-answer`, `type-body`, `type-small`, `type-eyebrow`.

### Shape, spacing, depth
- Radius: 8 px (cards, inputs, buttons), 12 px (dialogs), full (badges, avatars).
- Spacing on a 4 px grid; page padding 32 px desktop / 16 px mobile; content max-width 1200 px; chat column max 760 px.
- Depth by **borders, not shadows**: cards = `card` + 1 px `border`. Only popovers/dialogs get a soft shadow (`0 8px 24px rgb(26 34 51 / 0.08)`, utility `shadow-pop`).
- Motion: 150 ms ease-out for hovers, 200 ms for dialogs; respect `prefers-reduced-motion`.

### Signature components
- **Wordmark:** "Agent Platform" (or your final name) in Newsreader semibold, blue, with a coral dot.
- **Citations:** `[n]` in answers becomes a small superscript chip (blue-tint background, blue text); hover/click opens a popover with filename, page and snippet, plus "Open document". Sources list under the answer like footnotes, separated by a thin rule.
- **Agent status line:** while working, a muted line "Planning… → Meeting agent → Email agent" with the active step in blue and a coral pulsing dot.
- **Result cards:** meeting / email / report / insights results render as cards with a small uppercase eyebrow ("MEETING SUMMARY"), serif title, and actions (Copy, Download PDF, Open in History).
- **Status badges:** processing (warning, animated dot), ready (success), failed (destructive). Text + icon, never colour alone.

---

## Part D — Phases

Estimated ~7 weeks part-time. Phases 0–2 = working login + shell; 3–5 = all user features; 6–8 = admin, polish, tests, deploy.

### Phase 0 — Project skeleton + design system ✅
**Prompt:**
> Phase 0. Read Part B and Part C of the plan. In `frontend/` (keep the existing CLAUDE.md and docs/), create a Next.js app with `npx create-next-app@latest . --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm` (if it refuses because the folder isn't empty, create in a temp subfolder and move files up). Then:
> - Init shadcn/ui (`npx shadcn@latest init`) and add: button, input, textarea, label, form, select, dialog, alert-dialog, dropdown-menu, popover, tooltip, tabs, table, badge, card, separator, skeleton, sheet, scroll-area, avatar, sonner, checkbox, chart.
> - `app/globals.css`: all tokens from Part C as CSS variables mapped onto shadcn's variable names exactly as described in "shadcn mapping", plus `--coral`, `--coral-text`, `--coral-tint`, `--blue-tint`, `--success`, `--warning`, `--primary-hover`; expose them as Tailwind colors (`bg-coral`, `text-coral-text`, `bg-blue-tint`, …) using the mechanism of the installed Tailwind version (check it). Base: `body` uses background/foreground, focus-visible ring style, reduced-motion rule.
> - Fonts via `next/font/google`: Newsreader, Inter, JetBrains Mono as CSS variables → Tailwind `font-serif`, `font-sans`, `font-mono`; sans is the default.
> - Deps: @tanstack/react-query, react-hook-form, zod, @hookform/resolvers, openapi-fetch, @microsoft/fetch-event-source, react-markdown, remark-gfm, recharts (if chart didn't add it), lucide-react; dev: openapi-typescript, vitest, @vitejs/plugin-react, jsdom, @testing-library/react, @testing-library/jest-dom, @testing-library/user-event, prettier, prettier-plugin-tailwindcss.
> - Scripts: `typecheck` (tsc --noEmit), `test` (vitest), `gen:api` (openapi-typescript ../backend/openapi.json -o src/lib/api/schema.d.ts), `format`. Vitest config with jsdom + setup file.
> - `.env.example` (NEXT_PUBLIC_API_URL=http://localhost:8000), `.env.local` ignored.
> - `components/common/wordmark.tsx` and a dev-only page `app/styleguide/page.tsx` showing: every color token as a swatch with name, type scale, buttons (all variants), inputs, badges (status variants), a card, a citation chip, a result-card shell. Delete the create-next-app demo content; root page redirects to `/login` for now.

**Done when:** `npm run dev` shows http://localhost:3000/styleguide in ivory/blue/coral with the right fonts; lint + typecheck pass. **Look at it yourself and adjust tokens now** — every later screen inherits them.

### Phase 1 — API layer + auth state
**Prompt:**
> Phase 1. Read Part B rows "API client", "Token handling", "Server state". Files: `lib/api/schema.d.ts` (run `npm run gen:api`), `lib/api/client.ts`, `lib/api/auth.ts`, `lib/api/errors.ts`, `lib/api/keys.ts`, `lib/api/download.ts`, `providers/query-provider.tsx`, `providers/auth-provider.tsx`, `app/layout.tsx` (wrap providers + Toaster), tests `lib/api/__tests__/client.test.ts`.
> - auth.ts: in-memory `getToken/setToken/clearToken`; `refreshAccessToken()` calling POST /auth/refresh with `credentials: "include"`; a shared in-flight promise so concurrent callers trigger only ONE refresh.
> - client.ts: `openapi-fetch` client with baseUrl `${NEXT_PUBLIC_API_URL}/api/v1`, `credentials: "include"`, middleware adding `Authorization`; on 401 from a non-auth endpoint: refresh once and retry the request once; if refresh fails → clearToken + call a registered `onAuthLost` callback.
> - errors.ts: `ApiError` (status, code, message) from the backend `{error: {code, message}}` shape; `toastError(err)`; `unwrap()` helper that returns data or throws ApiError.
> - keys.ts: query-key factory for users, documents, conversations, messages, generations, admin.
> - download.ts: `downloadFile(path, fallbackName)` — fetch with auth (same refresh logic), read filename from Content-Disposition, blob → object URL → click → revoke.
> - auth-provider: on mount try refresh → GET /users/me; exposes `{user, status: "loading"|"authenticated"|"anonymous", login, register, logout, refreshUser}`; registers onAuthLost to set anonymous. login/register store the access token and user.
> - query-provider: QueryClient with retry 1 (no retry on 4xx), refetchOnWindowFocus false, global mutation onError → toastError.
> - Tests (mock fetch): Bearer header added; 401 → one refresh → retry succeeds; two parallel 401s → refresh called once; failed refresh → onAuthLost called; ApiError parsed from error body.

**Done when:** tests, lint, typecheck pass.

### Phase 2 — Auth pages + app shell + guards
**Prompt:**
> Phase 2. Read Part B "Route map", "App shell" and Part C. Files: `app/(auth)/layout.tsx`, `login/page.tsx`, `register/page.tsx`, `change-password/page.tsx`, `app/(app)/layout.tsx`, `components/layout/sidebar.tsx`, `nav-items.ts`, `user-menu.tsx`, `mobile-topbar.tsx`, `components/layout/auth-guard.tsx`, `app/page.tsx`, placeholder `page.tsx` for every (app) route showing the page title, `components/common/page-header.tsx`, `empty-state.tsx`, `error-state.tsx`.
> - (auth) layout: split screen on desktop — left: ivory panel with wordmark, serif headline about the product and three short feature lines; right: form card. Single column on mobile.
> - Forms with react-hook-form + zod: login (email, password); register (organization name, full name, email, password ≥ 8, confirm); change-password (current, new, confirm). Backend error → message under the form. Submit buttons show a spinner and are disabled while pending. After login: if `must_change_password` → /change-password, else → `next` query param or /chat.
> - auth-guard: while status loading → full-page skeleton (no flash of login page); anonymous → redirect `/login?next=<path>`; must_change_password → /change-password; `adminOnly` prop → non-admins redirected to /chat. Logged-in users visiting (auth) pages → /chat.
> - Sidebar per Part B/C: active item = blue-tint background + blue text + 3 px coral left bar; "New chat" primary button; Admin group only for admins; user menu with name, role badge, Settings, Log out. Collapsible on desktop (icons only + tooltips), Sheet on mobile.
> - page-header: eyebrow (optional), serif title, description, actions slot.

**Done when:** you can register, log in, see the shell, navigate all placeholder pages, log out, and refreshing the browser keeps you logged in. A seeded employee does not see Admin and is redirected from /admin.

### Phase 3 — Documents (knowledge base)
**Prompt:**
> Phase 3. Files: `app/(app)/documents/page.tsx`, `components/documents/upload-dialog.tsx`, `dropzone.tsx`, `documents-table.tsx`, `status-badge.tsx`, `visibility-select.tsx`, `lib/hooks/use-documents.ts`, `lib/format.ts` (bytes, dates, relative time), tests `components/documents/__tests__/dropzone.test.tsx`.
> - Upload dialog: drag-and-drop + browse, multiple files; client-side check of extension (pdf, docx, pptx, xlsx) and size (25 MB) with clear per-file errors; visibility select (Everyone / Managers & admins / Admins only → employee/manager/admin; options above the user's own role are hidden); uploads run sequentially with per-file progress state (pending, uploading, done, error).
> - Table: filename (file-type icon), visibility badge, status badge, pages/chunks, owner, uploaded (relative time), actions menu (Download, Get insights → links to `/history` flow in Phase 5 — for now disabled with tooltip "Coming soon", Delete with alert-dialog, shown only to owner or admin). Search by filename, status filter, "Load more" cursor pagination.
> - Polling: refetch every 3 s while any visible document is `processing`, stop otherwise. Toast when a document becomes ready or failed. Failed rows show the error in a tooltip.
> - Empty state: illustration-free, serif line "Your knowledge base is empty" + upload button. Mobile: table becomes stacked cards.
> - Test: dropzone rejects wrong extension and oversize file, accepts valid ones.

**Done when:** upload a PDF → see processing → ready (fake AI is instant; try `AI_MODE=real` once too), download works, delete works, employee can't see a manager-only doc.

### Phase 4 — Chat with streaming — use plan mode
**Prompt:**
> Phase 4. Enter plan mode first and show me the component tree and the streaming state design before writing code. Read Part B "Streaming chat", "Markdown" and Part C "Signature components". Files: `app/(app)/chat/page.tsx`, `chat/[id]/page.tsx`, `components/chat/conversation-list.tsx`, `message-list.tsx`, `message.tsx`, `markdown.tsx`, `citation.tsx`, `sources-footer.tsx`, `agent-status.tsx`, `composer.tsx`, `doc-picker.tsx`, `agent-select.tsx`, `result-card.tsx`, `lib/api/sse.ts`, `lib/hooks/use-chat-stream.ts`, `lib/hooks/use-conversations.ts`, tests for `sse.ts` and `markdown.tsx`.
> - sse.ts: `streamMessage(conversationId, body, handlers, signal)` using fetchEventSource: POST, JSON body, auth header, `openWhenHidden: true`; `onopen` checks status (401 → refresh once then retry the whole call ONCE; other non-200 → throw ApiError); `onerror` rethrows (no auto retry); dispatches by event name: status, agent, token, sources, result, error, done.
> - use-chat-stream: state `{phase: idle|streaming|error, text, sources, agentSteps, results, error}`; `send(content, {docIds, forceAgent})` adds the user message optimistically, streams into a draft assistant message, `stop()` aborts (AbortController); on done/abort → invalidate messages + conversations queries and clear the draft (server copy replaces it).
> - /chat with no id: on first send create a conversation, `router.replace` to /chat/[id], then stream.
> - message-list: loads history (cursor "Load earlier" at top), auto-scrolls only if the user is near the bottom; "Jump to latest" button otherwise.
> - message: user = right-aligned blue-tint bubble (sans); assistant = no bubble, Newsreader 17 px, full width; coral blinking cursor while streaming; actions on hover: copy, (for interrupted/error) retry.
> - markdown.tsx: react-markdown + remark-gfm, no raw HTML; preprocess `[n]` (only when a source n exists) into `[n](#cite-n)` and render those links as `<Citation n source>` chips with a popover (filename, page, snippet, "Open document" → download); tables/code styled with tokens.
> - agent-status: from status/agent events, e.g. "Planning… → Meeting agent → Email agent", active step blue with coral pulsing dot; collapses to a small "Used: Meeting, Email" line after done.
> - result-card: renders `result` events by shape — meeting (summary, decisions, action-items table), email (subject, body, Copy), report (title, sections), insights (summary, key points); eyebrow + serif title per Part C.
> - composer: autosizing textarea, Enter to send, Shift+Enter newline, disabled while streaming (Stop button instead); doc-picker (popover listing ready documents, multi-select, shows chips); agent-select (Auto default, or force Research/Email/Report/Meeting/Document).
> - conversation-list: grouped Today / Previous 7 days / Older, search, rename inline, delete with confirm; active item uses the nav active style.
> - Tests: SSE dispatch by event type with a mocked stream; markdown turns `[1]` into a citation only when source 1 exists and never renders raw HTML.

**Done when:** with fake AI tokens stream in live with the coral cursor; Stop works; reloading shows the saved conversation; with real AI an answer shows citations whose popovers open the right document. Check on a phone width too.

### Phase 5 — Tools: meetings, reports, email, insights, history
**Prompt:**
> Phase 5. Files: `app/(app)/meetings/page.tsx`, `reports/page.tsx`, `email/page.tsx`, `history/page.tsx`, `history/[id]/page.tsx`, `components/tools/meeting-form.tsx`, `report-form.tsx`, `email-form.tsx`, `generation-view.tsx`, `generation-list.tsx`, reuse `components/chat/result-card.tsx` pieces, `lib/hooks/use-tools.ts`; enable "Get insights" in the documents actions menu. Tests: `email-form.test.tsx`.
> - Layout for each tool page: two columns on desktop (form left ~40 %, result right), stacked on mobile. Result area: empty state before running; while running a calm skeleton with "Working on it… this can take up to a minute"; then the result view with actions Copy (markdown), Download PDF (`downloadFile`), Open in History.
> - meetings: tabs Paste / Upload (.txt, .vtt, .docx); title optional; result shows summary, key decisions, action items table (task, owner — "Unassigned" styled muted, due), open questions.
> - reports: report type segmented control (Weekly, Monthly, Sprint, Project), period input with sensible placeholder per type, instruction textarea, optional documents multi-select (ready docs only).
> - email: task tabs (Draft, Rewrite, Fix grammar, Change tone, Summarize thread), tone select shown for Draft/Rewrite/Change tone, text area labelled per task; result: subject + body with separate copy buttons.
> - insights: from the documents menu → POST insights → navigate to `/history/[id]`.
> - history: list of generations with kind filter tabs, title, kind badge, relative time; detail page renders with generation-view + PDF.
> - All submits disabled while pending; 429 shows "You're sending requests too quickly — try again in a minute."
> - Test: email form shows tone only for the right tasks and sends the right payload.

**Done when:** each tool produces a result and a PDF that downloads and opens; history lists everything you generated.

### Phase 6 — Admin
**Prompt:**
> Phase 6. Files: `app/(app)/admin/page.tsx`, `admin/users/page.tsx`, `admin/activity/page.tsx`, `components/admin/kpi-tile.tsx`, `tokens-chart.tsx`, `agent-usage-chart.tsx`, `docs-status-chart.tsx`, `users-table.tsx`, `create-user-dialog.tsx`, `activity-table.tsx`, `lib/hooks/use-admin.ts`. All wrapped in auth-guard `adminOnly`.
> - Dashboard (one GET /admin/stats call): KPI row — Users (with active last 7 days), Documents (with storage formatted), Conversations, Messages, Tokens last 30 days. Charts using the Part C chart palette and the shadcn chart wrapper: tokens per day (line/area, blue; today's point highlighted coral), usage per agent (horizontal bar), documents by status (bar with status colours), generations by kind. Each chart has a title, a one-line takeaway in muted text, and an accessible table fallback (visually hidden).
> - Users: table (name, email, role select inline, status, last login), search + role filter + load more; create-user dialog → on success shows the temporary password ONCE in a highlighted box with Copy and the note "Share this securely; the user must change it on first login"; deactivate/activate with confirm; backend guard errors (last admin, self-demotion) shown as toasts.
> - Activity: table (time, user, action as readable label, target, IP), filters for action and user, load more.

**Done when:** an admin sees real numbers that change after using chat/tools, can create a user and log in as them.

### Phase 7 — Settings, polish, accessibility, landing
**Prompt:**
> Phase 7. Polish only — no new features beyond these. Files: `app/(app)/settings/page.tsx`, `app/page.tsx`, `components/common/*` as needed, `app/not-found.tsx`, `app/(app)/error.tsx`, `app/(app)/loading.tsx`.
> - Settings: profile form (full name, email read-only, role badge), change password form.
> - `app/page.tsx` becomes a simple public landing for logged-out visitors (logged-in → /chat): serif headline, one paragraph, the five agents as a row of minimal cards, "Sign in" / "Create workspace" buttons. Same tokens, no stock images.
> - Review every page for: loading skeletons, empty states, error states with retry, mobile layout at 390 px, keyboard access and visible focus, aria-labels on icon buttons, page `<title>` via metadata, `prefers-reduced-motion`. Coral usage matches the coral rule in Part C (list every place coral appears and remove extras). Fix with minimal diffs and list each fix.

**Done when:** you can demo every screen on a laptop and a phone without anything looking broken; Lighthouse accessibility score ≥ 95 on login, chat and documents.

### Phase 8 — E2E tests, Docker, handover
**Prompt:**
> Phase 8. Files: `playwright.config.ts`, `e2e/*.spec.ts`, `Dockerfile`, `.dockerignore`, `next.config.*`, `README.md`. (1) Playwright (baseURL localhost:3000, backend must be running with AI_MODE=fake; use seed users from env vars): login + forced password change; upload a document and wait for ready; chat streams a reply and persists after reload; admin creates a user. (2) `next.config`: `output: "standalone"`. (3) Dockerfile: multi-stage on node LTS alpine, `npm ci`, build with `NEXT_PUBLIC_API_URL` as a build arg (empty = same origin), run as non-root with `node server.js`. (4) README: run locally, env vars, scripts, regenerating API types, notes for Member 4 — Nginx serves `/` → frontend and `/api` → backend on the same domain, `proxy_buffering off` for `/api/v1/conversations/` (SSE).

**Done when:** `npx playwright test` passes locally; the Docker image builds and runs; Member 4 deploys it behind Nginx and streaming works in production.

---

## Part E — Integration checkpoints
1. **Phase 0:** share `/styleguide` screenshot with the team — agree on the look before building screens.
2. **Phase 1:** whenever the backend changes, Member 2 exports `openapi.json` → you run `npm run gen:api` → typecheck shows exactly what broke.
3. **Phase 4:** confirm with Member 3 the `result` payload shapes (MeetingSummary, EmailOutput, Report, DocumentInsights) and `agent`/`status` event data — result-card depends on them.
4. **Phase 8:** same-domain deploy with Member 4 (cookie + SSE both depend on it).

## Part F — Demo script (frontend part)
1. Landing → create workspace → admin dashboard (empty) → create manager + employee.
2. Upload documents with different visibility; watch status go processing → ready.
3. Chat: streaming serif answer with coral cursor, citation popover opens the source.
4. "Summarize this transcript and email the action items to the team" → agent status shows both agents → meeting + email result cards.
5. Report → PDF download. History shows everything.
6. Log in as employee: manager-only doc absent; no Admin menu.
7. Admin dashboard: token chart and activity log reflect the demo.

## Part G — Common mistakes to avoid
- Storing the token in localStorage "to survive refresh" → the refresh cookie already does that.
- `EventSource` or default fetchEventSource retry → duplicate messages. Use the settings in Phase 4.
- Using shadcn `accent` for coral → every hover turns orange.
- Coral text in `#E8664A` → fails contrast. Use `coral-text`.
- Hand-writing API types → silently drift from the backend. Always `gen:api`.
- `<a href>` to protected downloads → 401. Use `downloadFile`.
- Building against a mock API → double work. The backend in fake mode is your mock.
- Polling forever → wasted requests. Poll only while something is processing.
