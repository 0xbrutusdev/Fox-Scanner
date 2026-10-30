# Frontend Structure Improvement Plan

## Summary

Refactor the existing multi-page vanilla HTML/CSS/JavaScript frontend into explicit shared templates, native ES modules, and scoped CSS files without changing the Python hosting model or requiring a client-side framework.

This plan is derived from the frontend investigation and [DEPLOYMENT.md](../DEPLOYMENT.md). It preserves the current server-rendered/static asset model: the Python service continues to serve `frontend/` alongside its JSON and event-stream APIs.

## Assumptions and constraints

- Keep the seven public pages and their URLs stable.
- Do not introduce React, a SPA router, or a Node runtime as part of this refactor.
- Native ES modules are acceptable in the supported modern-browser baseline.
- Preserve existing API contracts, scan event streaming, query-string deep links, i18n, theme selection, wallet controls, and page behaviour.
- Treat the current HTML/CSS/JS as the behavioural source of truth; this is structural work, not a visual redesign.

## Requirements

- **REQ-001**: Shared site chrome must have one source of truth.
- **REQ-002**: JavaScript dependencies must be explicit and page ownership must be clear.
- **REQ-003**: Styles must be divided by ownership while preserving the existing rendered design.
- **REQ-004**: `replay.html` must use the common frontend conventions or be explicitly isolated.
- **REQ-005**: The deployment path must remain compatible with the single Python web service described in [DEPLOYMENT.md](../DEPLOYMENT.md).
- **REQ-006**: Add repeatable checks that prevent structural, behavioural, and visual regressions.
- **REQ-007**: Static assets must be cacheable and optimized without requiring invalidation by hand.

## Target structure

```text
frontend/
  templates/
    head.html
    header.html
    footer.html
  pages/
    index.html
    about.html
    api.html
    radar.html
    replay.html
    token-management.html
    tokens.html
  static/
    css/
      tokens.css
      base.css
      layout.css
      components.css
      pages/
        home.css
        about.css
        api.css
        radar.css
        replay.css
        token-management.css
        tokens.css
    js/
      core/
        api.js
        i18n.js
        format.js
        dom.js
      components/
        theme.js
        language.js
        wallet.js
        navigation.js
      pages/
        home.js
        radar.js
        replay.js
        token-management.js
        tokens.js
      entries/
        home.js
        about.js
        api.js
        radar.js
        replay.js
        token-management.js
        tokens.js
```

The final on-disk layout may retain existing root-level page files if changing the backend static-file mapping would add unnecessary risk. The important boundaries are templates, CSS layers, JS modules, and per-page entry points.

## Implementation phases

### Phase 0 — Establish behavioural baseline

**Plan 0.1 — Record page contracts and the current asset-loading matrix.** [REQ-005, REQ-006]

- [ ] T001 [Plan:0.1] Document public routes, expected script entry point, API calls, and dynamic DOM roots for `index`, `about`, `api`, `radar`, `replay`, `token-management`, and `tokens`.
- [ ] T002 [Plan:0.1] Record the existing page checks from [DEPLOYMENT.md](../DEPLOYMENT.md) and add specific smoke scenarios for scanning, deep links, theme, language, wallet UI, refresh polling, and error states.
- [ ] T003 [Plan:0.1] Capture desktop and mobile screenshots for all public pages before structural changes.

**Acceptance criteria:** each page has a documented route, loading entry point, primary API dependency, and smoke scenario.

### Phase 1 — Extract shared HTML shell

**Plan 1.1 — Introduce a server-compatible template/include mechanism.** [REQ-001, REQ-005]

- [ ] T004 [Plan:1.1] Inspect the frontend-serving path in `backend/foxscanner/server.py` and choose the smallest compatible option: server-side includes/templates or a deterministic build-time HTML composition step.
- [ ] T005 [Plan:1.1] Create a single shared head template containing metadata, icon links, font/style references, theme bootstrap, and cache-version placeholders.
- [ ] T006 [Plan:1.1] Create shared header/navigation and footer templates from the repeated markup currently present in the public pages.
- [ ] T007 [Plan:1.1] Migrate `index.html`, `about.html`, `api.html`, `radar.html`, `token-management.html`, and `tokens.html` to the shared shell while preserving each page's active navigation item and document metadata.

**Plan 1.2 — Normalize Replay.** [REQ-001, REQ-004]

- [ ] T008 [Plan:1.2] Move the `replay.html` header/footer onto the shared shell and define a page-specific content root.
- [ ] T009 [Plan:1.2] Move Replay's inline script and inline styles to page-owned static assets without changing rendered output or API behaviour.

**Acceptance criteria:** a header/footer/theme/i18n shell change requires edits in one shared source; all existing routes still return successful pages.

### Phase 2 — Make JavaScript dependencies explicit

**Plan 2.1 — Create core ES modules.** [REQ-002, REQ-005]

- [ ] T010 [Plan:2.1] Split `static/js/api.js` into explicit `core/api.js`, `core/i18n.js`, and `core/format.js` exports; preserve request methods, translated strings, formatting output, and escaping semantics.
- [ ] T011 [Plan:2.1] Extract small, dependency-free DOM and notification helpers into `core/dom.js`.
- [ ] T012 [Plan:2.1] Replace the `window.FS` dependency contract with module imports in migrated code; retain a temporary compatibility adapter only while all consumers are being migrated.

**Plan 2.2 — Isolate shared interaction controllers.** [REQ-002]

- [ ] T013 [Plan:2.2] Extract theme, language, wallet, and navigation concerns from `static/js/app.js` into `components/` modules with explicit `init()` and teardown-safe event registration.
- [ ] T014 [Plan:2.2] Keep scan-specific state, deep-link processing, scanner progress, results, chart, trending search, and counters in `pages/home.js`.
- [ ] T015 [Plan:2.2] Convert existing radar, token, recent, scan, result, and chart scripts into imported modules with narrow public interfaces.

**Plan 2.3 — Add page entry points.** [REQ-002, REQ-005]

- [ ] T016 [Plan:2.3] Add one `type="module"` entry script per page and load only the modules required by that page.
- [ ] T017 [Plan:2.3] Verify module MIME types and static serving behaviour in the Python server before switching any production page.

**Acceptance criteria:** no page relies on script tag order or undeclared global symbols; each feature module has an identifiable page or shared owner.

### Phase 3 — Split CSS by responsibility

**Plan 3.1 — Establish CSS layers.** [REQ-003]

- [ ] T018 [Plan:3.1] Extract color, typography, spacing, and theme variables from `static/css/app.css` into `tokens.css`.
- [ ] T019 [Plan:3.1] Move reset/base rules, reusable layout primitives, and shared components into `base.css`, `layout.css`, and `components.css`.
- [ ] T020 [Plan:3.1] Move `.about-*`, `.api-*`, `.radar-*`, `.tm-*`, `.token-*`, home, and Replay styles into independently owned page stylesheets.
- [ ] T021 [Plan:3.1] Preserve responsive breakpoints and reduced-motion behaviour; remove superseded rules only after screenshot comparison.

**Plan 3.2 — Prevent style ownership drift.** [REQ-003, REQ-006]

- [ ] T022 [Plan:3.2] Adopt a naming and ordering convention for shared components versus page-owned selectors.
- [ ] T023 [Plan:3.2] Add a CSS lint/format check and a rule that page-specific selectors do not enter the shared component layer without a documented reuse case.

**Acceptance criteria:** an engineer can locate a visual rule by layer or page ownership without scanning a monolithic stylesheet.

### Phase 4 — Build, caching, and quality gates

**Plan 4.1 — Add a minimal static-asset pipeline.** [REQ-005, REQ-007]

- [ ] T024 [Plan:4.1] Choose a minimal build tool only if needed for HTML composition, CSS concatenation, minification, and content-hashed asset filenames; otherwise keep native module delivery and add deterministic asset version generation.
- [ ] T025 [Plan:4.1] Configure production cache headers for fingerprinted CSS, JS, fonts, and image assets, while keeping HTML non-immutable.
- [ ] T026 [Plan:4.1] Convert oversized decorative raster assets to suitable responsive WebP/AVIF variants where visual comparison preserves quality.

**Plan 4.2 — Add validation and release checks.** [REQ-006]

- [ ] T027 [Plan:4.2] Add static HTML validation, JavaScript lint/type checks, CSS linting, and a production asset-size budget to CI.
- [ ] T028 [Plan:4.2] Add browser smoke coverage for all public routes, home scan states, Replay data rendering, Radar/Token refresh, theme/language persistence, and mobile navigation.
- [ ] T029 [Plan:4.2] Add automated checks for missing template includes, missing module entry points, broken asset references, and invalid static MIME types.

**Acceptance criteria:** CI blocks broken module imports, missing assets, invalid rendered HTML, and critical browser-flow regressions.

## Sequencing and dependencies

1. Complete Phase 0 before modifying any structure.
2. Complete the shared shell before migrating Replay or page entry points.
3. Migrate modules page by page, starting with informational pages, then Radar/Tokens, and lastly the scan home page.
4. Split CSS in parallel with each page migration, not as a single high-conflict rewrite.
5. Introduce content hashing and strict cache headers only after asset paths are generated deterministically.

## Rollback strategy

- Make each page migration independently deployable.
- Keep the previous static HTML and classic script entry point until that page's module smoke tests pass.
- On a regression, restore the prior page template and its known-good asset references; API and backend contracts remain unchanged.
- Do not combine the structural refactor with feature changes, API changes, or visual redesign work.

## Requirement mapping

| Requirement | Plan items | Completion evidence |
| --- | --- | --- |
| REQ-001 Shared shell | 1.1, 1.2 | Shared head/header/footer templates; migrated public pages |
| REQ-002 Explicit JavaScript ownership | 2.1, 2.2, 2.3 | Core/component/page modules and per-page entries |
| REQ-003 Scoped CSS ownership | 3.1, 3.2 | Layered shared CSS and page-owned stylesheets |
| REQ-004 Replay normalization | 1.2 | Replay shell, stylesheet, and script module |
| REQ-005 Deployment compatibility | 0.1, 1.1, 2.3, 4.1 | Python-server integration and deployment verification |
| REQ-006 Regression prevention | 0.1, 3.2, 4.2 | Smoke checks, linting, rendered-page validation |
| REQ-007 Static asset optimization | 4.1 | Fingerprinted assets, cache policy, image variants |
