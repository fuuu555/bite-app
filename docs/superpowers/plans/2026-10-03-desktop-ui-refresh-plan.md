# Desktop UI Refresh — First Implementation Plan

> **For implementation:** Use the approved design spec at `docs/superpowers/specs/2026-10-03-desktop-ui-refresh-design.md`. Implement only this first representative slice, then pause for user review before extending the redesign to other routes.

**Goal:** Deliver a noticeably improved desktop experience for the consumer app and admin restaurant management while preserving the current phone and tablet interfaces exactly as they are.

**Scope:** Desktop viewport is `min-width: 1024px`. The first slice includes the desktop app shell, Explore, Map, and the admin restaurant list/editor. This plan does not redesign every route, change API/data behavior, or alter phone/tablet layouts.

**Architecture:** Add an isolated `desktop.css` stylesheet loaded after the existing web and mobile styles. Keep all new desktop presentation rules under `@media (min-width: 1024px)`. Reuse current React pages, components, APIs, and business logic; make only small markup changes needed to provide desktop layout containers. Keep the existing mobile stylesheet and its behavior untouched.

**Tech stack:** Next.js App Router, React, TypeScript, existing CSS, existing Playwright/Vitest test setup.

## Tasks

### 1. Lock the responsive boundary and capture a baseline

**Files:**
- Modify: `apps/frontend/src/app/layout.tsx`
- Create: `apps/frontend/src/styles/desktop.css`
- Test: existing frontend Playwright coverage and responsive page checks

- Record baseline screenshots or equivalent visual checks for representative routes at widths `390`, `768`, `1023`, `1024`, `1280`, and `1440` pixels.
- Load `desktop.css` from the root layout after `globals.css` (which imports `web.css` and `mobile.css`) so desktop rules have predictable precedence.
- Keep every new selector in `desktop.css` within `@media (min-width: 1024px)`; do not edit `mobile.css`.
- Verify at `1023px` that desktop-specific styles are absent and at `1024px` that they activate.
- Ensure tablet (`768px` through `1023px`) screenshots remain visually equivalent to the baseline.

### 2. Build the desktop user-app shell

**Files:**
- Modify: user app shared layout/navigation components identified in the approved spec
- Modify: `apps/frontend/src/styles/desktop.css`
- Test: relevant navigation/layout component tests

- Present primary user navigation as a top navigation bar on desktop; retain the current bottom navigation on phone and tablet.
- Establish a centered, wider desktop content frame with consistent spacing and clear page-title hierarchy.
- Preserve current routes, labels, selected states, authentication behavior, and navigation actions.
- Avoid changing shared component behavior below `1024px`.

### 3. Refresh Explore as the first content page

**Files:**
- Modify: `apps/frontend/src/features/home/explore-page.tsx` (or the current Explore page path if it differs)
- Modify: `apps/frontend/src/styles/desktop.css`
- Test: Explore component tests and desktop visual checks

- Use the approved warm BiteMap visual direction: warm off-white canvas, coral accent, deep blue-green text, improved typography and whitespace.
- Improve desktop hierarchy for search/filter controls, highlighted recommendations, and the complete result list.
- Reuse existing result data and actions; do not introduce a new ranking algorithm or API request pattern.
- Keep existing phone/tablet composition unchanged.

### 4. Give the desktop map a list-and-map layout

**Files:**
- Modify: current public map page/layout component identified in the approved spec
- Modify: `apps/frontend/src/styles/desktop.css`
- Test: map page/component tests and desktop visual checks

- Use a two-panel desktop composition: search, filters, and result list on the left; a large interactive map on the right.
- Keep the map, filters, search behavior, selection state, and result actions backed by existing components and endpoints.
- Prevent panel overflow at `1024px`; allow the result list to scroll independently where appropriate.
- Preserve the existing responsive map layout below `1024px`.

### 5. Refresh the admin desktop workspace and restaurant management

**Files:**
- Modify: admin layout/sidebar component identified in the approved spec
- Modify: `apps/frontend/src/features/admin/.../restaurant-list.tsx` (confirm exact route/component path before editing)
- Modify: restaurant editor page/component identified in the approved spec
- Modify: `apps/frontend/src/styles/desktop.css`
- Test: admin restaurant list/editor tests and desktop visual checks

- Present the admin area as a workspace with persistent desktop sidebar navigation and a spacious main content region.
- Make the restaurant list easier to scan using the approved full-width list/table direction, clear filters, and readable row actions.
- Keep restaurant editing as a dedicated page rather than a narrow drawer.
- Preserve current permissions, forms, validation, API calls, and save behavior.
- Do not change the existing phone/tablet admin navigation or layout.

### 6. Verify, compare, and stop at the agreed review point

**Files:**
- Tests: relevant frontend unit/component and Playwright tests

- Run `pnpm lint:frontend`.
- Run `pnpm typecheck:frontend`.
- Run relevant `pnpm test:frontend` tests.
- Run `pnpm build:frontend`.
- Run targeted Playwright checks/screenshots for phone (`390px`), tablet (`768px`, `1023px`), and desktop (`1024px`, `1280px`, `1440px`) on the representative routes.
- Compare phone/tablet results against the baseline; fix any unintended difference before presenting the result.
- Show the user the first-round result and collect feedback. Do not proceed to redesign remaining routes until the user reviews this slice.

## Acceptance criteria

- At widths `390px`, `768px`, and `1023px`, the existing phone/tablet experience remains visually and functionally unchanged.
- At widths `1024px` and above, the consumer app uses top navigation and the refreshed desktop content frame.
- Desktop Map uses the approved left-list/right-map arrangement without changing map data behavior.
- Admin restaurant management uses the approved workspace/sidebar and full-width list/editor direction.
- Existing navigation, search/filter, map interactions, admin permissions, and restaurant editing continue to work.
- Lint, typecheck, relevant frontend tests, production build, and targeted responsive checks pass.
- Work pauses after this representative slice for user feedback.

## Explicitly deferred

- Redesigning all other user and admin routes.
- Any phone or tablet UI changes.
- API, database, ranking, map-query, or business-rule changes.
- Introducing a new component library or replacing the existing styling system.
