# Manage, API, and About Frontend Refactor Plan

**Date:** 2026-10-29
**Scope:** `/token-management`, `/api`, and `/about`
**Reference:** [Frontend structure plan](./FRONTEND_STRUCTURE_PLAN.md) and the isolated visual language in [Replay](./replay.html)

## Summary

Refactor the three informational/conversion pages into a coherent **FoxScanner Signal Room**: a trader-focused interface built around wallet evidence, risk signals, and verifiable product boundaries rather than generic crypto marketing cards.

The work remains a server-rendered, multi-page vanilla HTML/CSS/JavaScript implementation. It must preserve the Python hosting model, shared navigation, theme, language controls, wallet controls, asset versioning, and existing URLs.

All current prices, token identities, plan limits, review states, and paid actions are temporary. The refactor must identify them as demo or preview content until production data and transaction flows exist. It must not present mock values as live facts.

## Investigation Findings

### Shared findings

- The three pages use the shared server-rendered shell, but their page styles still live inside the monolithic `static/css/app.css`.
- API and About load only the legacy shared `api.js` and `app.js`; neither has a page-owned interaction module.
- Manage has a page-owned script, but it still depends on the transitional `window.FS` global for translation and toast behavior.
- The visual language is primarily headings, cards, bullet lists, and repeated mascot artwork. It does not yet communicate how FoxScanner discovers risk.
- The existing 681 KB mascot raster is reused repeatedly instead of using responsive formats or page-specific visual evidence.
- At a 390px viewport, the shared navigation overflows on all three pages.
- Reduced-motion handling exists globally, but there is no page-level motion model or explicit static fallback for data visualizations.

### Manage (`/token-management`)

- Five large two-column cards repeat the same mock token identity and similar bullet structures.
- The first address form is useful, but the page does not establish a lifecycle: scan → verify ownership → publish trust signals → maintain metadata.
- Prices and paid actions appear actionable even though their data and transaction flows are temporary.
- At 390px, the page is approximately 3,358px tall. Stacking every preview above every description makes comparison and prioritization difficult.
- The strongest current concept is the side-by-side token preview, which should become one persistent live preview rather than five repeated mockups.

### API (`/api`)

- The page is marketing-led rather than developer-led: four pricing cards come before a meaningful request/response example.
- The same mascot image is repeated across the hero and feature sections.
- Endpoint documentation is a static list with no parameters, response shape, error behavior, copy action, or runnable example.
- All account CTAs lead to X, which creates a mismatch between “Create an account” and the actual destination.
- At 390px, the page is approximately 4,284px tall; pricing alone becomes about 1,401px.
- The page has a strong opportunity to show a unique live “risk signal pipeline” from token address to holder graph to verdict.

### About (`/about`)

- The page states origins, mission, and commitment, but provides little visual evidence of methodology or product boundaries.
- The mascot section is decorative and does not explain the scanner’s differentiator.
- “What we check” and “what we do not check” are buried in prose, which can create incorrect user expectations.
- Data-source names are presented as plain text rather than a transparent evidence chain.
- Mobile length is reasonable compared with the other pages, but the three-column introduction and source strip become generic stacked content.

## Product and Experience Requirements

- **REQ-101 — Distinctive identity:** Use a recognizable “Signal Room” visual system based on wallet clusters, evidence trails, scan timestamps, and risk bands. Avoid generic neon/glass crypto styling.
- **REQ-102 — Honest temporary content:** Clearly mark temporary prices, token examples, plan limits, and unsupported actions as demo/preview content. Do not fabricate live activity or performance claims.
- **REQ-103 — Manage workflow:** Reframe Manage as a token-owner lifecycle with one address context and a persistent token preview.
- **REQ-104 — Developer-first API:** Lead API visitors through request → processing → response → integration, with accessible code examples and accurate endpoint contracts.
- **REQ-105 — Trust-focused About:** Explain methodology, evidence sources, scoring boundaries, and independence in a visual, scannable narrative.
- **REQ-106 — Responsive behavior:** Support 360px through wide desktop without horizontal page or navigation overflow, clipped controls, or hover-only functionality.
- **REQ-107 — Purposeful motion:** Use animation to explain scanning and signal flow; support `prefers-reduced-motion` and static fallbacks.
- **REQ-108 — Accessible interaction:** Preserve semantic headings, keyboard navigation, visible focus, 44px touch targets, readable contrast, and translated UI strings.
- **REQ-109 — Performance:** Keep critical content usable before animation loads; optimize images/video and avoid layout shifts or blocking third-party assets.
- **REQ-110 — Compatibility:** Preserve current routes, shared shell, theme, language, wallet integration, asset versioning, and Python-only deployment.
- **REQ-111 — Regression prevention:** Add rendered-page, responsive, interaction, accessibility, and visual checks for all three pages.

## Design Direction: FoxScanner Signal Room

### Core visual language

1. **Evidence over decoration.** The primary motifs should be wallet nodes, transfer paths, launch timestamps, concentration bars, and risk verdict bands.
2. **Fox as scout, not wallpaper.** Use the mascot once per page as a guide or observer. Product evidence should carry the remaining visual weight.
3. **Semantic color discipline.** BNB yellow identifies active scanning and primary actions; red indicates observed danger; green indicates validated low-risk evidence; muted gray indicates unknown or unavailable data.
4. **Operational typography.** Keep expressive display type for page statements, but use the mono face for addresses, timestamps, endpoints, limits, and evidence labels.
5. **No fake dashboards.** Demo values must carry a visible `DEMO` label and explanatory copy. Unknown states should display “Not connected” or “Example data,” not plausible live values.

### Shared page frame

- Add a compact page-specific signal strip beneath the shared header:
  - Manage: `TOKEN OWNER WORKFLOW · DEMO DATA`
  - API: `INTEGRATION SIGNAL · API PREVIEW`
  - About: `EVIDENCE, NOT VIBES`
- Add a reusable section heading pattern: eyebrow, concise statement, one-line proof or limitation.
- Replace repeated generic cards with three reusable visual primitives:
  - `signal-panel`: evidence or live preview
  - `action-rail`: ordered user actions
  - `proof-strip`: compact methodology/source facts
- Keep dark and light themes, but ensure risk colors retain meaning in both themes.

## Page Refactor Specifications

### 1. Manage — Token Control Room

#### Information architecture

1. **Hero and token context**
   - Headline: “Turn a token page into a verified signal.”
   - Address input, chain indicator, and “Inspect token” action.
   - Explicit `Example data until an address is loaded` state.
2. **Persistent token preview**
   - Desktop: sticky preview panel occupying the left 38–42% of the content area.
   - Mobile: compact summary card above the workflow; expands into a bottom sheet or inline disclosure.
   - Preview updates from one shared demo model instead of five repeated `MY TOKEN` fragments.
3. **Owner lifecycle rail**
   - Step 1: Inspect score — free, no wallet.
   - Step 2: Prove ownership — wallet signature.
   - Step 3: Publish trust — badge, links, creator message.
   - Step 4: Maintain identity — metadata and domain updates.
4. **Action detail panels**
   - Use accordions/disclosures on mobile and compact rows on desktop.
   - Separate prerequisites, outcome, cost preview, and current availability.
   - Disabled or unsupported actions must say `Preview` rather than initiating a fake purchase.
5. **Trust boundary**
   - Explain what verification proves and what it does not prove.
   - Never imply that payment improves the risk score.

#### Distinctive visual

- A wallet-signature “trust chain” SVG connects owner wallet → verified token → published identity.
- The preview transitions between `unverified`, `signature detected`, and `verified` demo states.
- A narrow evidence ledger shows timestamped actions instead of generic success badges.

### 2. API — Risk Signal Lab

#### Information architecture

1. **Developer-first hero**
   - Token address input or prefilled clearly labeled demo address.
   - Request sample and response verdict visible above pricing.
   - Primary CTA: “View integration example”; secondary CTA: “Request API access.”
   - Do not label an X link “Create an account.”
2. **Signal pipeline**
   - Four stages: address → launch context → holder graph → verdict.
   - Each stage reveals the fields it contributes to the response.
3. **Interactive code explorer**
   - Tabs for cURL, JavaScript, and Python.
   - Copy button with accessible confirmation.
   - Response tabs for success, validation error, rate limit, and pending scan.
   - Endpoint navigation remains usable without JavaScript.
4. **Use-case matrix**
   - Trading bot, token terminal, wallet warning, research feed.
   - Each use case maps required endpoints and update frequency without invented customer claims.
5. **Plans and limits**
   - Move after the integration story.
   - Load temporary plans from one configuration object and label the section `Preview pricing`.
   - On mobile, use a plan selector plus one detail panel instead of four long cards.
6. **Contract boundaries**
   - Show what holder-risk scoring covers and explicitly exclude owner, tax, honeypot, and mint checks where applicable.

#### Distinctive visual

- A lightweight SVG “signal packet” travels through the pipeline and resolves into the same risk band users see on scan results.
- A compact event tape can show deterministic demo events such as `launch located`, `holders grouped`, and `verdict ready`; it must be labeled simulation.
- Code lines reveal by grouped blocks, not a fake typewriter effect.

### 3. About — Evidence, Not Vibes

#### Information architecture

1. **Manifesto hero**
   - Headline: “A risk verdict should show its work.”
   - Short explanation of the holder-focused scope.
   - One mascot composition paired with a wallet-cluster evidence visual.
2. **How the scan works**
   - A four-step evidence trail: launch → transfers → wallet relationships → verdict.
   - Each step includes the actual user-facing output it influences.
3. **What we check / what we do not check**
   - Two explicit columns on desktop; segmented disclosure on mobile.
   - This section is mandatory trust content, not footer copy.
4. **Scoring principles**
   - Same inputs, same rules.
   - Payment does not change the holder-risk verdict.
   - Unknown data remains unknown rather than being scored optimistically.
5. **Evidence sources**
   - Present launchpads, chain data, and market sources as a flow with purpose labels.
   - Avoid partner-logo presentation unless brand usage is approved.
6. **Contact and accountability**
   - Separate product support, data correction, and partnership contact intents.

#### Distinctive visual

- A scroll-linked—but not scroll-locked—wallet constellation progressively groups related nodes as the methodology is explained.
- An evidence ribbon shows `transaction`, `wallet`, `cluster`, and `verdict` states using real interface tokens.
- The mascot can cast a subtle scan cone across the graph; the graph remains understandable when animation is disabled.

## Image and Video Recommendations

| Page | Asset | Recommendation | Format and budget |
| --- | --- | --- | --- |
| Manage | Trust-chain diagram | Custom SVG showing wallet signature, token identity, and published proof | SVG, under 80 KB |
| Manage | Token preview artwork | Generated identicon/initials from the demo address; no external token logo required | CSS/SVG, under 20 KB |
| API | Signal-pipeline diagram | Custom SVG with four processing stages and field labels | SVG, under 100 KB |
| API | Code-response visual | Real HTML/code component, not a raster screenshot | HTML/CSS |
| About | Wallet constellation | Custom SVG with accessible text alternative | SVG, under 120 KB |
| About | Optional methodology loop | 6–8 second silent loop of scan cone grouping wallet nodes; no stock trading footage | WebM plus MP4 fallback, poster image, combined initial load under 1.5 MB |
| Shared | Mascot | Export responsive 320/640/960 WebP and AVIF variants with PNG fallback | Prefer under 180 KB at common desktop size |

Do not use candlestick stock footage, anonymous hackers, spinning coins, or unrelated exchange dashboards. Those assets are common across rug scanners and weaken product credibility.

## Motion and Interaction Plan

### Shared motion tokens

- Micro interaction: 120–180ms, ease-out.
- Panel transition: 220–320ms, cubic-bezier tuned for quick deceleration.
- Explanatory loop: 2.4–4.5 seconds, never blocking interaction.
- Animate only `transform`, `opacity`, and SVG stroke properties where practical.

### Effects

- **Signal sweep:** a low-opacity yellow scan line crosses evidence panels when they enter the viewport once.
- **Node grouping:** wallet nodes translate into clusters and connecting paths draw in sequence.
- **Risk resolve:** neutral evidence chips resolve to a risk band after the final stage; no flashing red backgrounds.
- **Card focus:** border and internal evidence highlight on keyboard focus or pointer hover; no essential content hidden behind hover.
- **Copy confirmation:** icon and live-region text update for 1.5 seconds.
- **Section reveal:** short opacity/translate reveal triggered with `IntersectionObserver`; content remains visible when JavaScript is unavailable.
- **Sticky context:** Manage preview and API code sample remain contextually visible on desktop, but release before colliding with the footer.

### Reduced-motion behavior

- Disable sweeps, node travel, parallax, count-up, and automatic code sequencing.
- Render final graph and verdict states immediately.
- Preserve focus, expanded/collapsed state, and copy confirmations without motion dependency.
- Do not autoplay video under reduced motion; show the poster image with a play control.

## Responsive Approach

### Breakpoints and layout intent

| Range | Layout behavior |
| --- | --- |
| 360–479px | Single-column content, 16px page gutters, compact typography, full-width primary actions, accordion/detail disclosures, no decorative asset above primary task |
| 480–767px | Single column with richer previews, 20px gutters, two-up compact facts where labels remain readable |
| 768–1023px | Tablet layout; two-column sections only when both columns remain at least 320px; two-up pricing or workflow summaries |
| 1024–1439px | Desktop layout with sticky preview/code panel and 12-column content grid |
| 1440px+ | Content remains capped near 1200px; increase whitespace rather than stretching cards and line lengths |

### Shared navigation

- Replace the overflowing mobile link row with a menu button and accessible disclosure/drawer below 800px.
- Keep wallet, theme, and language controls reachable without horizontal scrolling.
- Lock body scroll only while the mobile menu is open and restore focus to the menu trigger on close.

### Manage responsive behavior

- Desktop: sticky preview plus workflow rail.
- Tablet: preview and current step in two columns; remaining steps below.
- Mobile: address form first, compact token summary second, action accordions third.
- Keep cost/status labels adjacent to their action; never place price on a detached line that can be mistaken for another action.
- Use a sticky bottom action only after a valid address is present, with safe-area padding.

### API responsive behavior

- Desktop: request controls and response/code panel side by side.
- Tablet: code panel follows request controls and remains horizontally scrollable internally.
- Mobile: language tabs become a horizontally scrollable tablist; code blocks scroll internally without widening the page.
- Replace four stacked pricing cards with a plan selector and one active plan detail panel.
- Endpoint navigation becomes an accordion or select-like list with deep-link anchors preserved.

### About responsive behavior

- Desktop: alternating evidence narrative and wallet graph.
- Mobile: graph becomes a compact static overview followed by the four methodology steps.
- “Check / do not check” becomes a segmented control or two always-visible stacked panels; do not hide limitations by default.
- Source labels wrap as cards, not a long bordered text strip.

### Responsive acceptance criteria

- No horizontal document overflow at 360, 390, 768, 1024, or 1440px.
- No line of prose exceeds approximately 70 characters on wide screens.
- Interactive targets are at least 44×44 CSS pixels on touch layouts.
- The primary task is visible within the first viewport at 390×844 for Manage and API.
- Mobile navigation works with keyboard, touch, Escape, and focus restoration.
- Zooming to 200% does not hide actions or require two-dimensional page scrolling.

## Technical Context

- **Runtime:** Python server-rendered HTML with native ES modules; no SPA or Node runtime required in production.
- **Current source pages:** `token-management.html`, `api.html`, and `about.html`.
- **Current shared styles:** `static/css/app.css`.
- **Current entries:** `static/js/entries/token-management.js`, `static/js/entries/api.js`, and `static/js/entries/about.js`.
- **Current Manage behavior:** `static/js/pages/token-management.js`.
- **Constraints:** preserve server-side asset hashing, static MIME handling, theme/i18n events, wallet controls, and current route contracts.

## Target Project Structure

```text
frontend/
  token-management.html
  api.html
  about.html
  static/
    css/
      components/
        signal-panel.css
        action-rail.css
        code-explorer.css
        evidence-graph.css
      pages/
        token-management.css
        api.css
        about.css
    js/
      components/
        disclosure.js
        mobile-navigation.js
        signal-animation.js
        code-explorer.js
        copy-control.js
      data/
        marketing-preview.js
      pages/
        token-management.js
        api.js
        about.js
      entries/
        token-management.js
        api.js
        about.js
    img/
      pages/
        manage-trust-chain.svg
        api-signal-pipeline.svg
        about-wallet-constellation.svg
        about-methodology-poster.webp
    video/
      about-methodology.webm
      about-methodology.mp4
```

The optional video files should be added only after a static SVG implementation passes accessibility and performance review.

## Implementation Plan and Tasks

### Phase 1 — Baseline and content contract

#### Plan 1.1 — Freeze current behavior and temporary-content rules

**Requirements:** REQ-102, REQ-110, REQ-111

- [ ] T001 [Plan:1.1] Document current route, DOM, interaction, theme, language, and wallet contracts for `frontend/token-management.html`, `frontend/api.html`, and `frontend/about.html`.
- [ ] T002 [P] [Plan:1.1] Capture desktop and mobile visual baselines at 390×844, 768×1024, and 1440×1000.
- [ ] T003 [Plan:1.1] Inventory every temporary price, plan limit, token identity, review state, and CTA destination; classify each as `demo`, `preview`, `production`, or `remove`.
- [ ] T004 [Plan:1.1] Define approved copy for demo labels, unsupported actions, product boundaries, and X/contact CTAs.

**Acceptance criteria:** no temporary value enters the redesign without an explicit classification and visible presentation rule.

### Phase 2 — Shared responsive and visual foundations

#### Plan 2.1 — Build the Signal Room primitives

**Requirements:** REQ-101, REQ-106, REQ-108, REQ-109, REQ-110

- [ ] T005 [Plan:2.1] Extract the Manage, API, and About selectors from `frontend/static/css/app.css` into page-owned stylesheets without changing unrelated pages. [Source: frontend/static/css/app.css]
- [ ] T006 [P] [Plan:2.1] Add shared `signal-panel`, `action-rail`, `code-explorer`, and `evidence-graph` component styles under `frontend/static/css/components/`.
- [ ] T007 [Plan:2.1] Extend the server page metadata/template contract to load one page stylesheet per route while preserving content-hash versioning. [Source: backend/foxscanner/server.py#render_site_page]
- [ ] T008 [Plan:2.1] Implement responsive mobile navigation in `frontend/static/js/components/mobile-navigation.js` and shared header markup/styles.
- [ ] T009 [P] [Plan:2.1] Add shared disclosure, copy confirmation, and reduced-motion-safe signal animation modules under `frontend/static/js/components/`.
- [ ] T010 [Plan:2.1] Add deterministic preview content in `frontend/static/js/data/marketing-preview.js`; prohibit random or time-varying fake activity.

**Acceptance criteria:** all three pages share the same evidence vocabulary, have no navigation overflow at 360px, and remain fully readable with JavaScript or animation disabled.

### Phase 3 — Manage user story

#### Plan 3.1 — Convert Manage into an owner workflow

**Requirements:** REQ-102, REQ-103, REQ-106, REQ-107, REQ-108

- [ ] T011 [US1] [Plan:3.1] Rebuild `frontend/token-management.html` around token context, one persistent preview, lifecycle rail, action details, and trust boundary copy. [Source: frontend/token-management.html]
- [ ] T012 [P] [US1] [Plan:3.1] Implement the trust-chain SVG in `frontend/static/img/pages/manage-trust-chain.svg` with accessible fallback text.
- [ ] T013 [US1] [Plan:3.1] Refactor `frontend/static/js/pages/token-management.js` to use explicit imports, one preview model, validation states, disclosures, and preview-only action handling. [Source: frontend/static/js/pages/token-management.js]
- [ ] T014 [P] [US1] [Plan:3.1] Implement desktop sticky preview, tablet split layout, and mobile accordion/bottom-action behavior in `frontend/static/css/pages/token-management.css`.
- [ ] T015 [US1] [Plan:3.1] Update `frontend/static/js/entries/token-management.js` to initialize only required shared and page controllers.

**Acceptance criteria:** a user can understand the owner lifecycle in one scan, load or validate an address, distinguish free versus wallet-required steps, and identify every temporary action before interacting.

### Phase 4 — API user story

#### Plan 4.1 — Build the Risk Signal Lab

**Requirements:** REQ-102, REQ-104, REQ-106, REQ-107, REQ-108, REQ-109

- [ ] T016 [US2] [Plan:4.1] Reorder `frontend/api.html` around request, signal pipeline, response, use cases, endpoint contracts, and preview pricing. [Source: frontend/api.html]
- [ ] T017 [P] [US2] [Plan:4.1] Create `frontend/static/img/pages/api-signal-pipeline.svg` with static and animated states.
- [ ] T018 [US2] [Plan:4.1] Implement accessible cURL/JavaScript/Python tabs, response-state tabs, and copy controls in `frontend/static/js/pages/api.js` and shared code-explorer modules.
- [ ] T019 [P] [US2] [Plan:4.1] Implement desktop request/response split, mobile code overflow containment, endpoint disclosures, and plan selector in `frontend/static/css/pages/api.css`.
- [ ] T020 [US2] [Plan:4.1] Replace misleading “Create an account” links with accurate access/contact actions and preserve external-link security attributes.
- [ ] T021 [US2] [Plan:4.1] Update `frontend/static/js/entries/api.js` to initialize only API page controllers.

**Acceptance criteria:** a developer sees a valid request and representative response before pricing, can copy examples with keyboard or touch, can inspect common error contracts, and never mistakes preview limits for an active account offer.

### Phase 5 — About user story

#### Plan 5.1 — Explain methodology and trust boundaries

**Requirements:** REQ-101, REQ-102, REQ-105, REQ-106, REQ-107, REQ-108, REQ-109

- [ ] T022 [US3] [Plan:5.1] Rebuild `frontend/about.html` around manifesto, methodology, check/do-not-check boundaries, scoring principles, evidence sources, and contact intents. [Source: frontend/about.html]
- [ ] T023 [P] [US3] [Plan:5.1] Create `frontend/static/img/pages/about-wallet-constellation.svg` with meaningful node labels and a static final state.
- [ ] T024 [P] [US3] [Plan:5.1] Implement the evidence narrative and responsive graph layout in `frontend/static/css/pages/about.css`.
- [ ] T025 [US3] [Plan:5.1] Implement one-time methodology reveals and reduced-motion fallbacks in `frontend/static/js/pages/about.js`.
- [ ] T026 [US3] [Plan:5.1] Update `frontend/static/js/entries/about.js` to initialize only About page controllers.
- [ ] T027 [US3] [Plan:5.1] Evaluate the optional methodology video only after SVG performance review; if accepted, add WebM, MP4, poster, captions/transcript, and explicit playback controls.

**Acceptance criteria:** a visitor can explain what FoxScanner measures, what it does not measure, how evidence becomes a verdict, and why payment cannot alter the score.

### Phase 6 — Optimization and validation

#### Plan 6.1 — Accessibility, performance, and regression gates

**Requirements:** REQ-106, REQ-107, REQ-108, REQ-109, REQ-110, REQ-111

- [ ] T028 [Plan:6.1] Export responsive AVIF/WebP mascot variants and update image markup with dimensions, `srcset`, `sizes`, and appropriate loading priority.
- [ ] T029 [P] [Plan:6.1] Add rendered-page tests for page stylesheets, module entries, temporary-data labels, accessible controls, and missing asset references.
- [ ] T030 [P] [Plan:6.1] Add browser smoke tests at 390, 768, 1024, and 1440px for navigation, overflow, disclosures, copy controls, theme, language, wallet handoff, and reduced motion.
- [ ] T031 [P] [Plan:6.1] Add automated accessibility checks for heading order, landmarks, labels, focus order, contrast, keyboard operation, live regions, and 200% zoom.
- [ ] T032 [Plan:6.1] Enforce budgets: no horizontal overflow, no unexpected layout shift, page-owned CSS/JS loaded only where needed, optimized initial media under agreed limits, and animations maintaining responsive interaction.
- [ ] T033 [Plan:6.1] Run the existing backend/frontend suites and compare desktop/mobile screenshots before removing superseded selectors from `frontend/static/css/app.css`.

**Acceptance criteria:** all three routes pass responsive, keyboard, reduced-motion, rendered-asset, and visual regression gates with no changes to backend API contracts.

## Testing Strategy

- **Application type:** server-rendered multi-page frontend with significant client-side interaction.
- **Critical journeys:**
  1. Mobile visitor opens/closes navigation, changes theme/language, and reaches each page without overflow.
  2. Token owner enters an address, receives validation feedback, inspects the preview, and distinguishes preview actions from available actions.
  3. Developer switches API language/response tabs, copies an example, and follows an endpoint anchor.
  4. About visitor reviews methodology and check/do-not-check boundaries with motion enabled and reduced motion enabled.
  5. All pages remain readable and structurally complete when page JavaScript fails to initialize.
- **Primary browser validation:** Playwright with Chromium at the defined viewport matrix.
- **Fallback:** current Python rendered-page and HTTP tests plus integrated-browser manual validation when Node/Playwright is unavailable; document the missing automated interaction and visual coverage.
- **Test data:** deterministic, clearly labeled preview fixtures; no dependence on live token values, external APIs, or wallet balances.
- **Pass criteria:** all critical journeys succeed, no console errors or missing assets occur, no document-level horizontal overflow exists, and reduced-motion mode exposes the final meaningful state.

## Rollout and Rollback

1. Ship shared responsive navigation and CSS loading support before page redesigns.
2. Release one page at a time: About → API → Manage. Manage is last because it has wallet-adjacent interactions.
3. Keep each previous page body and page CSS available until its visual and behavior checks pass.
4. Do not combine the refactor with payment processing, account creation, pricing activation, or backend contract changes.
5. If a page fails validation, restore only that page’s previous HTML, entry module, and stylesheet; shared server and API behavior remain unchanged.

## Requirement Mapping

| Requirement | Plan items | Completion evidence |
| --- | --- | --- |
| REQ-101 Distinctive identity | 2.1, 4.1, 5.1 | Shared signal components, API pipeline, About evidence graph |
| REQ-102 Honest temporary content | 1.1, 3.1, 4.1, 5.1 | Content inventory, demo labels, preview fixtures, corrected CTA language |
| REQ-103 Manage workflow | 3.1 | Rebuilt Manage HTML, preview model, lifecycle rail, trust chain |
| REQ-104 Developer-first API | 4.1 | Request/response hero, code explorer, error states, endpoint navigation |
| REQ-105 Trust-focused About | 5.1 | Methodology trail, scope boundaries, principles, evidence sources |
| REQ-106 Responsive behavior | 2.1, 3.1, 4.1, 5.1, 6.1 | Mobile navigation, page layouts, viewport smoke tests |
| REQ-107 Purposeful motion | 3.1, 4.1, 5.1, 6.1 | Signal animation module, static fallbacks, reduced-motion tests |
| REQ-108 Accessible interaction | 2.1, 3.1, 4.1, 5.1, 6.1 | Semantic controls, keyboard behavior, focus management, accessibility checks |
| REQ-109 Performance | 2.1, 4.1, 5.1, 6.1 | Responsive assets, media budgets, page-owned loading, layout-shift checks |
| REQ-110 Compatibility | 1.1, 2.1, 6.1 | Stable routes, template integration, versioned assets, existing suite results |
| REQ-111 Regression prevention | 1.1, 6.1 | Baseline captures, rendered-page tests, browser smoke and visual checks |

## Definition of Done

- Manage, API, and About use page-owned styles and entry modules.
- The shared mobile navigation no longer overflows at 390px.
- Temporary values and unsupported operations are visibly identified.
- Each page has a distinctive evidence-based visual instead of repeated mascot cards.
- Desktop and mobile layouts prioritize the page’s primary user task.
- Animations explain state or process and have complete reduced-motion fallbacks.
- No route, theme, translation, wallet, static asset, or API contract regression is introduced.
- Automated and manual checks cover the responsive viewport matrix and critical journeys.
