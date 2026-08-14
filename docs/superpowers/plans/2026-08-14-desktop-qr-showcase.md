# Desktop QR Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add equal-sized website and experience-group QR cards beside the existing desktop phone simulator without changing mobile behavior.

**Architecture:** Extend the existing `PhoneFrame` presentation boundary with two static, semantic QR cards. Bundle the supplied images as H5 assets and use responsive CSS to show them only on wide browser viewports.

**Tech Stack:** React 19, TypeScript, CSS media queries, Vitest, Testing Library, Vite.

## Global Constraints

- Keep the centered 390×844 phone simulator unchanged.
- Left label is exactly `网站`; right label is exactly `体验群`.
- Hide both QR cards below 1180px.
- Do not add a dependency, alter README, or change business behavior.
- Deploy the exact merged `origin/main` commit and run public smoke tests.

---

### Task 1: Lock the desktop showcase structure

**Files:**
- Create: `apps/h5/tests/phone-frame.test.tsx`
- Modify: `apps/h5/src/components/PhoneFrame.tsx`
- Create: `apps/h5/src/assets/stylecapture-website-qr.jpg`
- Create: `apps/h5/src/assets/stylecapture-experience-group-qr.jpg`

**Interfaces:**
- Consumes: `PhoneFrame({ children }: { children: ReactNode })`
- Produces: two complementary `<figure>` landmarks labelled `网站` and `体验群`

- [ ] **Step 1: Write the failing test**

Render `PhoneFrame`, assert the phone child remains present, and assert two labelled QR figures and images with descriptive alt text.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @stylecapture/h5 exec vitest run tests/phone-frame.test.tsx`
Expected: FAIL because the QR figures do not exist.

- [ ] **Step 3: Write minimal implementation**

Import the two supplied assets and render the two figures as siblings of `.pixel-frame`, keeping the existing frame markup unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @stylecapture/h5 exec vitest run tests/phone-frame.test.tsx`
Expected: PASS.

### Task 2: Add responsive presentation styling

**Files:**
- Modify: `apps/h5/src/app/pixel-theme.css`

**Interfaces:**
- Consumes: `.showcase-qr`, `.showcase-qr__viewport`, `.showcase-qr__image`
- Produces: symmetric wide-screen cards hidden below 1180px

- [ ] **Step 1: Add default-hidden card styles**

Use `display: none` outside the wide-screen media query so mobile behavior is unchanged.

- [ ] **Step 2: Add wide-screen grid placement and equal QR sizing**

At `min-width: 1180px`, position the cards on either side of the fixed phone frame with the same width and square QR viewport.

- [ ] **Step 3: Crop only the website source caption**

Scale and position the website source inside its square viewport so the QR remains intact while its embedded caption is hidden; render both labels through the same component markup.

- [ ] **Step 4: Run targeted and full verification**

Run: `pnpm --filter @stylecapture/h5 test`, `pnpm --filter @stylecapture/h5 typecheck`, and `pnpm --filter @stylecapture/h5 build`.

### Task 3: Visual QA and deployment

**Files:**
- Create: `docs/evidence/desktop-qr-showcase/desktop.png`
- Create: `docs/evidence/desktop-qr-showcase/mobile.png`
- Create: `docs/evidence/desktop-qr-showcase/README.md`

**Interfaces:**
- Consumes: built H5 and existing deployment workflow
- Produces: visual verdict >= 90 and verified public deployment

- [ ] **Step 1: Capture local screenshots**

Capture 2048×1270 and 390×844 screenshots from the production preview.

- [ ] **Step 2: Run visual verdict**

Compare desktop composition against the approved request and mobile composition against the existing centered-phone behavior; require no P0/P1 and score at least 90.

- [ ] **Step 3: Commit, push, review, and merge**

Use a Lore-compliant commit, open a PR, confirm CI and review the diff before merge.

- [ ] **Step 4: Deploy exact origin/main and smoke test**

Confirm cloud commit equals `origin/main`, then verify `/healthz`, `/readyz`, `/docs`, H5 desktop, H5 390×844, and QR visibility/scannability.
