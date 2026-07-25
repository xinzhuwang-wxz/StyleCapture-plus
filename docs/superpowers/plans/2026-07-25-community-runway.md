# Community Pixel Runway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an interactive mobile pixel runway where every visible person is a pixel
avatar and the user can take a runway turn, react, inspect public resident style tags, and
download a scene-faithful card.

**Architecture:** Extend the existing pure `communityScene` model with runway state and
deterministic audience data. `CommunityScreen` renders this state through CSS/DOM, while
its existing hidden Canvas exports only public display state. The H5 shell stays unchanged
apart from the existing Community route.

**Tech Stack:** React 18, TypeScript, existing CSS, Vitest/Testing Library, Playwright.

## Global Constraints

- Do not add dependencies, iframe, game server, live-user claims, or original reference images.
- Every visible person must be a pixel avatar; only public resident tags may be exposed.
- Preserve movement, keyboard fallback, modal accessibility, share retry, and reduced motion.
- Use behavior-first tests and capture fresh 390×844 browser evidence.

---

### Task 1: Model the runway show

**Files:**
- Modify: `apps/h5/src/features/community/communityScene.ts`
- Test: `apps/h5/tests/community-scene.test.ts`

**Interfaces:**
- Produces `RunwayState`, `sendAvatarToRunway(scene)`, `returnAvatarBackstage(scene)`, and
  `selectReaction(scene, reaction)` with applause state.
- Consumed by `CommunityScreen`.

- [ ] **Step 1: Write failing tests**

```ts
expect(sendAvatarToRunway(createCommunityScene()).runway).toMatchObject({
  featuredAvatar: "me",
  applause: 12,
  isShowing: true
});
expect(returnAvatarBackstage(sendAvatarToRunway(createCommunityScene())).runway.isShowing).toBe(false);
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pnpm --filter @stylecapture/h5 test -- community-scene.test.ts`

- [ ] **Step 3: Add the smallest pure state transition**

```ts
export function sendAvatarToRunway(scene: CommunityScene): CommunityScene {
  return { ...scene, runway: { featuredAvatar: "me", applause: 12, isShowing: true } };
}
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `pnpm --filter @stylecapture/h5 test -- community-scene.test.ts`

### Task 2: Render a dense all-pixel runway and its controls

**Files:**
- Modify: `apps/h5/src/features/community/CommunityScreen.tsx`
- Modify: `apps/h5/src/app/styles.css`
- Test: `apps/h5/tests/community-screen.test.tsx`

**Interfaces:**
- Consumes `CommunityScene.runway`, `sendAvatarToRunway`, and `returnAvatarBackstage`.
- Produces accessible `轮到我上台` / `回到后台` controls, a live lookboard, pixel crowd,
  and resident pixel-avatar buttons.

- [ ] **Step 1: Write failing component assertions**

```tsx
await user.click(screen.getByRole("button", { name: "轮到我上台" }));
expect(screen.getByRole("status")).toHaveTextContent("正在走秀");
expect(screen.getByText("喝彩 12")).toBeInTheDocument();
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pnpm --filter @stylecapture/h5 test -- community-screen.test.tsx`

- [ ] **Step 3: Render the runway state and only pixel occupants**

```tsx
<button type="button" onClick={takeRunwayTurn}>
  {scene.runway.isShowing ? "回到后台" : "轮到我上台"}
</button>
<div aria-label="像素观众" className="runway-audience">...</div>
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `pnpm --filter @stylecapture/h5 test -- community-screen.test.tsx`

### Task 3: Make sharing represent the runway moment

**Files:**
- Modify: `apps/h5/src/features/community/CommunityScreen.tsx`
- Test: `apps/h5/tests/community-screen.test.tsx`
- Test: `apps/h5/e2e/community-ballroom.spec.ts`

**Interfaces:**
- `drawShareCard` consumes `scene.runway` and `scene.avatar.reaction`.
- Browser download remains `stylecapture-pixel-ballroom.png` and retains error retry.

- [ ] **Step 1: Write a failing test that asserts runway card drawing**

```ts
await user.click(screen.getByRole("button", { name: "轮到我上台" }));
await user.click(screen.getByRole("button", { name: "生成分享卡" }));
expect(drawImage).toHaveBeenCalled();
expect(screen.getByRole("status")).toHaveTextContent("分享卡已准备好");
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pnpm --filter @stylecapture/h5 test -- community-screen.test.tsx`

- [ ] **Step 3: Add public runway/applause/reaction text to the existing card renderer**

```ts
context.fillText(`喝彩 ${scene.runway.applause}`, 64, 918);
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `pnpm --filter @stylecapture/h5 test -- community-screen.test.tsx`

### Task 4: Capture and verify the full mobile experience

**Files:**
- Modify: `apps/h5/e2e/community-ballroom.spec.ts`
- Modify: `docs/evidence/issue-9/README.md`
- Modify: `docs/exec-plans/0009-community-dance-demo.md`

- [ ] **Step 1: Extend the Playwright journey**

```ts
await page.getByRole("button", { name: "轮到我上台" }).click();
await expect(page.getByRole("status")).toContainText("正在走秀");
await page.screenshot({ path: evidence("08-community-runway.png"), animations: "disabled" });
```

- [ ] **Step 2: Run the browser test and check the new screenshot**

Run: `STYLECAPTURE_E2E_BASE_URL=http://127.0.0.1:5174 pnpm exec playwright test e2e/community-ballroom.spec.ts`

- [ ] **Step 3: Run final verification**

Run: `pnpm --filter @stylecapture/h5 test && pnpm --filter @stylecapture/h5 typecheck && pnpm --filter @stylecapture/h5 build`

- [ ] **Step 4: Record current evidence and update Issue #9/PR #10**

Record screenshots, visual verdict, verification results, and the public RenderArtifact
handoff boundary.
