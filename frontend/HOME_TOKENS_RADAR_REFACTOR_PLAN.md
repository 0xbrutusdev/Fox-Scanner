# Home, Tokens, and Radar Frontend Refactor Plan

## Outcome

Refactor the Home (`/`), Tokens (`/tokens`), and Radar (`/radar`) pages into a distinctive trader-facing product built around an **evidence terminal** concept: FoxScanner should feel like a live investigator of holder behavior, not a generic token directory with a risk badge.

The visual signature should combine:

- the existing black/yellow FoxScanner palette;
- the fox as a focused investigator and guide, not the primary content;
- a reusable “FoxTrace” visual language for wallet clusters, fresh wallets, insiders, concentration, liquidity, and scan freshness;
- motion that explains scanning and updates instead of running as constant decoration;
- compact, information-dense layouts that remain legible and operable on phones.

This is a frontend refactor plan. Current token records are temporary and must not be treated as durable product content or used as proof of scanner accuracy.

## Scope and constraints

- Preserve the Python service and multi-page vanilla HTML/CSS/JavaScript architecture described in [DEPLOYMENT.md](../DEPLOYMENT.md).
- Preserve `/`, `/tokens`, `/radar`, deep-linked scans, current JSON contracts, theme, i18n, wallet controls, and shared navigation.
- Build on the shared shell and native-module work already described in [FRONTEND_STRUCTURE_PLAN.md](./FRONTEND_STRUCTURE_PLAN.md); do not recreate shared header/footer or module migration work in this visual refactor.
- Keep scan scoring and token eligibility semantics unchanged unless an API extension is explicitly approved.
- Treat “verified” as identity evidence only. Never style it as a safety guarantee.
- Do not introduce React, a SPA router, WebGL, or a permanent animation runtime for this work.

## Investigation summary

### Verified implementation facts

- The three routes are rendered through the shared server shell in [server.py](../backend/foxscanner/server.py).
- Home markup lives in [index.html](./index.html), token discovery markup in [tokens.html](./tokens.html), and Radar markup in [radar.html](./radar.html).
- Page behavior is currently owned by [scan.js](./static/js/scan.js), [recent.js](./static/js/recent.js), [tokens.js](./static/js/tokens.js), and [radar.js](./static/js/radar.js).
- Most relevant page styling still lives in the 55 KB uncompressed [app.css](./static/css/app.css). The existing structural plan should move new page rules into page-owned stylesheets.
- The Home hero mascot is a 681,635-byte flattened PNG in [mascot-hero.png](./static/img/mascot-hero.png). It is visually strong but cannot support efficient part-level animation.
- The current Radar already has the most distinctive interaction: a time-based circular scope with a continuous sweep and token blips.
- The current Tokens page combines recently verified, most viewed, and newly created tokens under the heading “Recently Verified,” which understates the page’s actual purpose.
- Live inspection at 1440, 1024, 768, 390, and 360 px found no document-level horizontal overflow.
- At a 360 px viewport, the Tokens “Most Viewed” toolbar is wider than its panel. The refresh button ends at approximately 354 px while the panel ends at 329 px, so the control is clipped by `overflow: hidden`.
- At 360 px, Radar action buttons wrap into two lines. They remain usable, but the card grows significantly and the action hierarchy is unclear.
- At 360 px, the Home hero consumes about 449 px before the recent-token section; the static mascot occupies roughly 235 px and pushes the scanner lower than necessary.

### Product and UX findings

1. **Home is visually memorable but not immediately differentiated by data.** The static fox dominates the hero, while the unique product value—holder relationships, operator clusters, fresh wallets, and likely sell pressure—is not visible until after a scan.
2. **Home has two scan affordances.** The icon inside the field and the separate “Check” button compete without adding a second meaningful action.
3. **Tokens reads as two utility tables rather than a trader workspace.** It lacks a clear distinction between attention, freshness, and trust state; empty states provide no useful next action.
4. **Radar has the right metaphor but insufficient decision support.** The scope is fascinating, but cards only expose age, launchpad, market cap at scan, score, and trade links. Users cannot quickly see why a token qualified.
5. **Loading, empty, stale, and request-error states are visually conflated.** A zero count can briefly look authoritative before data arrives.
6. **The desktop-to-mobile layout mostly stacks instead of reprioritizing.** Important controls can clip or wrap unpredictably, and the mobile information hierarchy is not intentionally different from desktop.
7. **Continuous ticker and sweep motion can distract from live information.** Both need lifecycle control, focus behavior, and reduced-motion alternatives.

## Design direction: FoxTrace Evidence Terminal

FoxTrace is a reusable visual grammar, not a separate feature or a claim of new backend analysis.

- **Node**: a wallet or token identity.
- **Edge**: a known relationship already present in scan evidence.
- **Halo**: concentration or severity.
- **Pulse**: a new or refreshed observation.
- **Trail**: the ordered scan stages from contract to holder evidence.
- **Stamp**: a verdict or identity state with explicit semantics.

Use these primitives across all three pages so the brand becomes recognizable even when the mascot is absent. Yellow remains the active signal color; green is reserved for evidence that passes a defined rule, orange/red for risk, and neutral grey for unavailable or unknown data.

The visual tone should be closer to a compact trading terminal plus forensic map than a cyberpunk game HUD. Avoid fake charts, fake PnL, invented holder connections, or decorative numbers.

## Shared page system

### Navigation and global layout

- Keep the existing shared header, but add a subtle route context label on mobile so the current page remains obvious when navigation is collapsed.
- Keep the wallet, theme, and language controls in the header. Do not make wallet connection a prerequisite for scanning or browsing.
- Standardize a page intro pattern: eyebrow/status, focused `h1`, one-sentence value proposition, freshness/source metadata, then primary content.
- Use a maximum content width of 1200 px, 24 px desktop gutters, and 16 px mobile gutters.
- Establish page-owned stylesheets: `pages/home.css`, `pages/tokens.css`, and `pages/radar.css`, loaded through the existing page metadata in [server.py](../backend/foxscanner/server.py).

### Shared trader components

- `signal-chip`: compact label for launchpad, age, score band, or evidence status.
- `freshness-indicator`: last successful update time, polling state, and stale/error state.
- `evidence-strip`: three to five scan facts with icons and explicit unknown states.
- `token-identity`: image/fallback initials, symbol, name, short contract, and copy action.
- `data-state`: separate skeleton, empty, stale, and error treatments with useful recovery actions.
- `risk-stamp`: score and band with a tooltip or adjacent copy that explains what it does and does not mean.
- `foxtrace-mini`: small SVG cluster preview populated only from available evidence.

## Home page plan

### Information architecture

Replace the centered vertical stack with a desktop split hero:

- **Left, primary:** eyebrow (“BNB holder intelligence”), headline, two-line explanation, scanner field, one primary scan action, and a sample/demo action.
- **Right, supporting:** a compact fox investigator scene integrated with a FoxTrace evidence map.
- **Below hero:** three product-proof statements—linked wallets, fresh-wallet concentration, and estimated sell pressure—followed by a controlled recent-scans rail.

Recommended headline:

> See who really holds the token before you trade.

Recommended supporting copy:

> FoxScanner traces holder relationships, launch wallets, and concentration signals behind fresh BNB tokens.

### Scanner interaction

- Use one primary submit control. The field icon is decorative or becomes a clear-loading control only while a scan is active.
- Detect a valid BNB address locally and transition the field to a ready state without claiming the token is valid.
- Keep name/symbol suggestions, but label them as search suggestions and keep address scanning as the deterministic path.
- Add a “Try a sample scan” secondary action using a documented mock/demo record, visibly marked as demo data.
- On submit, morph the hero’s evidence map into the existing scan progress stages instead of abruptly hiding the entire hero.
- Keep deep-link behavior and scan-result APIs unchanged.

### Fox and media recommendation

Keep the Chinese-inspired fox character, but reposition it as a right-side investigator rather than a full-width centerpiece. The hat character and scroll must remain legible and should be reviewed for intended brand meaning before public launch.

Preferred implementation:

1. Commission or export three transparent layers: `fox-body`, `magnifier`, and `scan-glow`.
2. Deliver the body as responsive AVIF/WebP with PNG fallback.
3. Deliver the scan glow and wallet nodes as lightweight SVG.
4. Animate the magnifier and glow with CSS transforms; no library is required.

Optional richer asset:

- a 4–6 second silent side-loop showing the fox lifting the magnifier while wallet nodes resolve;
- WebM plus MP4 fallback, a matching poster image, `muted`, `playsinline`, and no audio track;
- load the video only above 768 px and only after the main scan UI is interactive;
- never autoplay when `prefers-reduced-motion: reduce`, Save-Data is enabled, or the page is hidden;
- budget: no more than 900 KB total for the optional loop and no more than 180 KB for the poster.

Do not use a full-bleed background video. It would compete with the scan field, weaken text contrast, and increase mobile LCP cost.

### Home motion specification

- Page entrance: 180–240 ms opacity/translate transition, once, after first paint.
- Fox idle: 5–7 second low-amplitude breathing loop; pause while offscreen or hidden.
- Magnifier inspection: 1.4 seconds on first load, then only on field focus or valid-address readiness.
- Scan beam: 700 ms sweep synchronized with scan submission; progress then follows real scan events.
- Wallet nodes: reveal in event order with 90 ms stagger; never invent nodes before evidence arrives.
- Recent-scan rail: replace compulsory infinite marquee with a drag/scroll-snap rail. Optional auto-advance pauses on hover, focus, touch, hidden tab, and reduced motion.
- Result-state score: count up only once and only when its final value is known; screen readers receive the final value, not every frame.

### Home acceptance criteria

- The scan field and primary action are visible without scrolling at 360 × 800, 390 × 844, 768 × 1024, 1024 × 768, and 1440 × 900.
- The mascot never pushes the primary scanner below the first 55% of a mobile viewport.
- Submit behavior, deep links, suggestions, progress events, errors, and result rendering remain functional.
- The page has useful static content when media fails or motion is disabled.
- The hero poster is responsive and materially smaller than the current 681 KB PNG.

## Tokens page plan

### Positioning and information architecture

Rename the page-level concept from “Recently Verified” to **Token Pulse** or **Market Watch**. Keep “Recently Verified” as one explicitly labeled subsection.

Recommended order:

1. Page intro with BNB scope and freshness indicator.
2. Compact segmented view: `Most checked`, `New launches`, `Recently verified`.
3. A single responsive data surface instead of two competing panels on narrow screens.
4. Optional watchlist/bookmark affordance only after its persistence model is defined; do not fake it with transient UI.

### Desktop and tablet data surface

- Keep a two-column overview at widths above 960 px, but make “Most checked” the primary 7-column span and “New launches” the secondary 5-column span.
- Add explicit source/freshness labels and an automatic-refresh status.
- Preserve time windows, but move range controls to a dedicated row so the title and refresh action cannot collide.
- Add sorting only for fields supplied by the API. Do not imply price movement or liquidity when those values are absent.
- Each row should have one primary action (“Inspect”) with copy and secondary actions in an overflow menu.
- Replace the current empty row with an empty-state panel: explain the selected window, offer a larger window, and link to scan a token.

### Mobile data surface

- At 640 px and below, render list cards rather than squeezing four table columns.
- First line: token identity and risk stamp.
- Second line: checks or creation age plus verification/launch context.
- Third line: full-width “Inspect” action; copy remains a 44 × 44 px adjacent control.
- Range options become a horizontally scrollable segmented control with the refresh control pinned outside the scroll area.
- Do not hide clipped controls. Every interactive control must remain fully inside the panel at 320 px.

### Tokens motion and effects

- New rows enter with a 180 ms background tint and settle; do not reorder while the user is interacting with a row.
- A refresh rotates the icon once and uses skeleton rows only when there is no previous data.
- Live updates briefly highlight changed fields for 600 ms; unchanged rows do not animate.
- The recently verified rail uses scroll-snap and an edge fade; no unconditional infinite motion on mobile.
- Token avatars use a neutral shimmer only during image load, then stop.

### Tokens acceptance criteria

- The 360 px refresh clipping defect is eliminated; test again at 320, 360, 390, and 430 px.
- No table or card requires horizontal page scrolling.
- Range selection, manual refresh, 15-second updates, copy, and row navigation remain keyboard and touch operable.
- Loading, empty, stale, and request-error states are visually and semantically distinct.
- “Verified” always includes language equivalent to “identity verified” and never changes the risk score styling.

## Radar page plan

### Preserve and strengthen the signature interaction

Retain the circular Radar because it is the strongest differentiator, but make its geometry meaningful and expose the legend:

- radial distance = token age within the selected window;
- blip ring color = score band using the same scale as scan results;
- blip size = fixed by default; only encode another metric after the API supplies a reliable value;
- selected blip = linked highlight between scope and result card;
- center label = `now`; outer ring = the current time window.

Add an adjacent plain-language legend so the scope is understandable without relying on animation.

### Decision workflow

- Add filters for launchpad and maximum age using current payload fields.
- Add score filtering only if product policy defines the score threshold; default eligibility remains controlled by the backend.
- Add a compact “Why it qualified” evidence strip only after the Radar API returns the relevant factors. Until then, show the existing CLEAN score and a link to the full scan—do not fabricate reasons client-side.
- Prioritize one trade action based on the launch venue, then put alternative venues in a menu. Keep “Full scan” visually distinct from trade actions.
- Add `last updated`, polling state, and stale/error recovery near the live indicator.
- When no launch qualifies, keep the scope visible in an idle state and explain the qualification criteria with a scan CTA.

### Radar motion and effects

- Slow the sweep to approximately 6 seconds and lower its opacity so labels remain readable.
- Pause the sweep when the scope is offscreen, the document is hidden, a blip has keyboard focus, or reduced motion is requested.
- On data refresh, pulse only new blips; existing blips should smoothly reposition over 280–360 ms if the time window changes.
- Hover/focus links a blip to its card with a shared highlight and a subtle connecting line.
- Selecting a blip on mobile scrolls the corresponding card into view and leaves a persistent selected state.
- Under reduced motion, replace the sweep with a static 20-degree sector and update blips without interpolation.

### Radar acceptance criteria

- The scope and legend are understandable when animations are disabled.
- Blips and labels remain inside the 320 px layout, including long Chinese token names.
- Cards render as three columns at wide desktop, two at tablet, and one at mobile with no ambiguous wrapped action group.
- New, stale, empty, and failed polling states do not display a misleading live zero.
- External trade links keep `rel="noopener"`; the full scan remains an internal link.
- Current 15-second polling and hidden-tab request suppression remain intact.

## Responsive strategy

### Layout bands

- **1280 px and above:** full split Home hero; two-column Tokens workspace; Radar hero plus three-column card grid.
- **960–1279 px:** tighter split layouts, two-column Radar cards, reduced decorative media.
- **641–959 px:** stacked Home/Radar hero, one-column Tokens panels, two-column cards only where content remains readable.
- **320–640 px:** mobile-specific content order, card-based token lists, single-column Radar cards, compact non-blocking mascot.

Use fluid `clamp()` sizing inside these bands and container queries for panel toolbars where practical. Breakpoints must follow content failure, not a device-name list.

### Required viewport review

Verify portrait layouts at 320 × 568, 360 × 800, 390 × 844, 430 × 932, and 768 × 1024. Verify landscape/desktop at 844 × 390, 1024 × 768, 1280 × 800, 1440 × 900, and 1920 × 1080.

At every viewport:

- no document-level horizontal overflow;
- no clipped focus ring or clipped interactive control;
- minimum 44 × 44 px touch targets for primary mobile controls;
- sticky header and open mobile navigation do not obscure focused content;
- long symbols, CJK names, and contract addresses truncate without hiding copy/access actions;
- software keyboard does not cover the Home scanner status or submit control;
- safe-area insets are respected on notched devices.

## Accessibility, motion, and content rules

- Target WCAG 2.2 AA contrast and keyboard behavior.
- Preserve semantic headings, landmarks, tables on desktop, and equivalent list semantics on mobile.
- Use `aria-live="polite"` for scan phase and refresh completion, but do not announce every Radar timer tick.
- Every animation must have a static end state and obey `prefers-reduced-motion`.
- Pause animation and polling work where appropriate on `visibilitychange` and when components are offscreen.
- Do not communicate risk by color alone; pair color with text/icon shape.
- Explain that CLEAN means no currently detected disqualifying evidence, not guaranteed safety.
- Use “last checked” and “last updated” timestamps instead of vague live claims when data becomes stale.
- Ensure translated strings can expand by at least 35% without clipping.

## Performance budgets

- LCP at the 75th percentile: under 2.5 seconds on a representative mobile connection.
- CLS: under 0.1; reserve media, avatar, skeleton, and scope dimensions.
- INP: under 200 ms for scanner input, filters, card selection, and mobile navigation.
- Home poster: target 180 KB or less; optional delayed video: 900 KB or less total.
- Do not add more than 20 KB compressed JavaScript for presentation behavior across the three pages.
- Prefer CSS/SVG and native browser APIs over an animation library.
- Lazy-load below-fold token images and decode them asynchronously.
- Stop rendering loops and timers for hidden/offscreen components.

## Implementation sequence

### Phase 0 — Baseline and visual contract

- Capture the current three pages at all required viewports in dark and light themes.
- Record Home initial, valid-input, scanning, result, empty, and error states.
- Record Tokens loading, populated, empty-window, refresh, and API-error states.
- Record Radar loading, populated, empty, stale, and API-error states.
- Freeze the existing API payload examples as test fixtures; label them as fixtures, not production truth.
- Define FoxTrace tokens, icon meanings, motion durations, and risk language before implementation.

**Exit:** approved wireframes and a state matrix exist for all three pages.

### Phase 1 — Shared presentation primitives

- Add page-owned stylesheets through [server.py](../backend/foxscanner/server.py).
- Implement shared token identity, freshness, data-state, evidence-strip, and risk-stamp components.
- Add a small motion controller for reduced-motion, visibility, and intersection-based pausing.
- Create responsive image derivatives and the layered fox/SVG assets.

**Exit:** primitives render correctly in dark/light themes and at 320–1440 px without page-specific data logic changes.

### Phase 2 — Home refactor

- Refactor [index.html](./index.html) into the split hero and product-proof layout.
- Keep scan business logic in [scan.js](./static/js/scan.js); move presentation orchestration into the Home page module defined by the structural plan.
- Integrate the layered fox scene, evidence-map preview, sample scan, and event-driven scan transition.
- Replace the automatic recent-token marquee with a controllable scroll-snap rail.

**Exit:** all current scan paths pass and the initial scanner remains above the fold on required mobile viewports.

### Phase 3 — Tokens refactor

- Refactor [tokens.html](./tokens.html) around Token Pulse/Market Watch sections.
- Update [tokens.js](./static/js/tokens.js) to render desktop tables and equivalent mobile cards from the same normalized view model.
- Separate toolbar rows, add data-state handling, and fix the clipped refresh control.
- Keep current API calls, timing, and navigation behavior.

**Exit:** range, refresh, copy, updates, empty/error states, and navigation pass at all target widths.

### Phase 4 — Radar refactor

- Add the scope legend, filters supported by current fields, selected-blip state, and polling/freshness status to [radar.html](./radar.html).
- Update [radar.js](./static/js/radar.js) to separate data normalization, scope plotting, card rendering, and motion lifecycle.
- Consolidate card actions and create linked blip/card focus behavior.
- Gate “Why it qualified” on a real API extension; ship without invented evidence if that dependency is deferred.

**Exit:** scope semantics, cards, filters, and polling states work with mouse, touch, keyboard, reduced motion, and temporary fixtures.

### Phase 5 — Quality gates and rollout

- Add browser interaction tests and viewport screenshots for all acceptance states.
- Run existing Python frontend/server tests and update assertions only when the approved markup contract changes.
- Test current Chrome, Edge, Firefox, and Safari/iOS behavior; verify video/image fallbacks.
- Measure Core Web Vitals and asset budgets before enabling optional rich media.
- Roll out one route at a time behind a server-rendered body class or feature flag.

**Exit:** visual review, accessibility review, browser tests, and performance budgets pass for all three routes.

## Test plan

### Functional

- Home address paste, suggestion choice, submit, deep link, scan progress, result, retry, and error.
- Tokens time-window changes, refresh, polling, copy, row/card navigation, empty/error fallback.
- Radar polling, filter, blip selection, card linkage, copy, full scan, and external trade links.
- Theme, language, wallet menu, mobile navigation, tab return, and hidden-tab behavior on every route.

### Responsive and visual

- Screenshot comparisons for all required viewports in light/dark themes.
- Long English, CJK, emoji, missing image, very long symbol, and missing-value fixtures.
- Zoom at 200% and text-only zoom without hidden actions or horizontal page scrolling.
- Portrait/landscape rotation and software-keyboard interaction on Home.

### Accessibility

- Keyboard-only route through header, scanner, controls, rows/cards, and footer.
- Screen-reader checks for scan progress, refresh completion, risk meaning, and scope legend.
- Reduced-motion verification with no auto-scrolling, rotating sweep, stagger, or count-up.
- Contrast and focus-visible review in both themes.

### Performance

- Cold-cache and warm-cache measurements.
- Low-end mobile CPU/network profile with and without optional hero media.
- Confirm images reserve dimensions and do not shift layout.
- Confirm timers, animations, and network polling stop or throttle when hidden.

## API dependencies and optional follow-up

The first refactor can ship against current payloads. The following enhancements require backend contracts and must remain visibly absent until implemented:

- Radar “Why it qualified” factors;
- liquidity and market-cap change since scan;
- watchlist persistence;
- verified-identity state in token discovery rows;
- server-authoritative sorting beyond the current returned lists.

If approved, define these as versioned response fields with unknown/null states and fixture coverage before frontend implementation.

## Rollback strategy

- Deliver Home, Tokens, and Radar as separate commits/releases.
- Keep API contracts unchanged in the initial visual phases.
- Keep the current mascot PNG as the poster/fallback until layered assets pass review.
- Retain previous page templates and page styles until route-specific smoke and screenshot tests pass.
- Disable optional video through configuration without changing page structure.
- If a route regresses, restore that route’s previous template/style/entry point without rolling back the other two pages.

## Definition of done

- The product is recognizable without relying on the mascot alone.
- Home exposes the unique holder-evidence value before a scan.
- Tokens supports fast comparison instead of behaving as two static tables.
- Radar’s scope is both fascinating and semantically understandable.
- All controls remain visible and usable from 320 px through wide desktop.
- Motion communicates state, pauses appropriately, and has a complete reduced-motion experience.
- No temporary data, animation, or visual treatment creates an unsupported safety or performance claim.
- Existing routes, scan behavior, API behavior, theme, i18n, wallet controls, and navigation remain compatible.
