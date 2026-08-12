import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../.."
);
const evidenceDirectory = path.join(repositoryRoot, "docs/evidence/issue-6/feed");
let savedLookToCleanUp: string | null = null;

test.afterEach(async ({ page }) => {
  if (savedLookToCleanUp === null) return;
  await page
    .evaluate(async (lookId) => {
      await fetch(`/v1/looks/${lookId}?delete_items=true`, { method: "DELETE" });
    }, savedLookToCleanUp)
    .catch(() => undefined);
  savedLookToCleanUp = null;
});

async function saveEvidence(page: Page, name: string) {
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  await page.screenshot({
    path: path.join(evidenceDirectory, `${name}.png`),
    animations: "disabled",
    fullPage: true
  });
}

async function openFeed(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const feedEntry = page.getByRole("button", {
    name: "刷灵感 Feed",
    exact: true
  });
  if (await feedEntry.isVisible().catch(() => false)) {
    await feedEntry.click();
  }
  await expect(page.getByTestId("feed")).toBeVisible({
    timeout: 30_000
  });
  await expect(page.getByRole("button", { name: "暂停并圈选" }).first()).toBeEnabled({
    timeout: 75_000
  });
}

async function openWardrobeAndCountLooks(page: Page) {
  const looksLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname.endsWith("/v1/looks"),
    { timeout: 15_000 }
  ).catch(() => null);
  await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible();
  await looksLoaded;
  await expect(page.locator(".wardrobe-loading")).toHaveCount(0);
  return page.locator(".look-card").count();
}

async function pauseAndOpenOverlay(page: Page, index = 0) {
  const circleButton = page.getByRole("button", { name: "暂停并圈选" }).nth(index);
  let lastClickError: unknown;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    await expect(circleButton).toBeEnabled({ timeout: 30_000 });
    try {
      await circleButton.click({ timeout: 8_000 });
      lastClickError = null;
      break;
    } catch (error) {
      lastClickError = error;
      await page.waitForTimeout(1_000);
    }
  }
  if (lastClickError) {
    throw lastClickError;
  }
  const overlay = page.getByRole("application", { name: "圈选穿搭" });
  await expect(overlay).toBeVisible({ timeout: 10_000 });
  return overlay;
}

async function drawPolygon(
  page: Page,
  overlay: ReturnType<Page["getByRole"]>,
  scale = 1
) {
  const box = await overlay.boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;
  const centerX = box.x + box.width * 0.5;
  const centerY = box.y + box.height * 0.45;
  const halfWidth = box.width * 0.28 * scale;
  const halfHeight = box.height * 0.24 * scale;
  const points = [
    [centerX - halfWidth, centerY - halfHeight],
    [centerX + halfWidth, centerY - halfHeight],
    [centerX + halfWidth, centerY + halfHeight],
    [centerX - halfWidth, centerY + halfHeight],
    [centerX - halfWidth, centerY - halfHeight]
  ] as const;

  await page.mouse.move(...points[0]);
  await page.mouse.down();
  for (const point of points.slice(1)) {
    await page.mouse.move(...point, { steps: 10 });
  }
  await page.mouse.up();
}

async function swipe(locator: ReturnType<Page["getByRole"]>, direction: "left" | "right") {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;
  const startX = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  const endX = startX + (direction === "right" ? 150 : -150);
  const page = locator.page();
  await page.mouse.move(startX, y);
  await page.mouse.down();
  await page.mouse.move(endX, y, { steps: 12 });
  await page.mouse.up();
}

async function saveWholeOutfitBySwipe(page: Page) {
  const overlay = await pauseAndOpenOverlay(page);
  await drawPolygon(page, overlay);
  const liftedSelection = page.getByRole("group", { name: "已圈选的穿搭主体" });
  await expect(liftedSelection).toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole("status", { name: "左划取消，右划加入" })).toBeVisible();
  await page.getByRole("button", { name: "存整套" }).click();
  await saveEvidence(page, "05-whole-outfit-selected");
  const captureAccepted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/v1/captures",
    { timeout: 90_000 }
  );
  await swipe(liftedSelection, "right");
  const response = await captureAccepted;
  expect(response.status()).toBe(202);
  const payload = (await response.json()) as { look_id: string | null };
  expect(payload.look_id).not.toBeNull();
  await expect(page.getByText("已存入数字衣橱")).toBeVisible({ timeout: 90_000 });
  return payload.look_id!;
}

test.describe("Issue 6 public Feed lasso", () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(240_000);
    page.setDefaultTimeout(20_000);
    await page.setViewportSize({ width: 390, height: 844 });
  });

  test("shows lasso guides on the first two feed cards and resumes playback after dismissing the overlay", async ({
    page
  }) => {
    await openFeed(page);
    const firstVideo = page.getByLabel(/的穿搭视频/).first();
    await expect(firstVideo).toBeVisible();

    const firstOverlay = await pauseAndOpenOverlay(page);
    await expect(page.getByRole("status", { name: "沿着衣服边缘画一圈" })).toBeVisible();
    await saveEvidence(page, "01-first-card-circle-guide");

    await firstOverlay.click({ position: { x: 12, y: 12 } });
    await expect(firstOverlay).toHaveCount(0);
    await expect
      .poll(() => firstVideo.evaluate((video: HTMLVideoElement) => video.paused))
      .toBe(false);

    const feed = page.getByTestId("feed");
    await feed.evaluate((element) => {
      element.scrollTo({ top: element.clientHeight, behavior: "auto" });
    });
    await expect
      .poll(() => feed.evaluate((element) => element.scrollTop), {
        timeout: 10_000
      })
      .toBeGreaterThan(0);
    const secondButton = page.getByRole("button", { name: "暂停并圈选" }).first();
    await expect(secondButton).toBeEnabled({ timeout: 20_000 });
    const secondOverlay = await pauseAndOpenOverlay(page);
    await expect(page.getByRole("status", { name: "沿着衣服边缘画一圈" })).toBeVisible();
    await saveEvidence(page, "02-second-card-circle-guide");
    await secondOverlay.click({ position: { x: 12, y: 12 } });
    await expect(secondOverlay).toHaveCount(0);
  });

  test("keeps a completed lasso visible until the user makes a decision and lets left swipe cancel it", async ({
    page
  }) => {
    await openFeed(page);
    const overlay = await pauseAndOpenOverlay(page);
    await drawPolygon(page, overlay);

    const liftedSelection = page.getByRole("group", { name: "已圈选的穿搭主体" });
    await expect(liftedSelection).toBeVisible({ timeout: 5_000 });
    await page.waitForTimeout(1_200);
    await expect(liftedSelection).toBeVisible();
    await expect(page.getByRole("status", { name: "左划取消，右划加入" })).toBeVisible();
    await saveEvidence(page, "03-lasso-stays-lit-before-decision");

    await swipe(liftedSelection, "left");
    await expect(page.getByRole("application", { name: "圈选穿搭" })).toHaveCount(0);
    await expect(page.getByText("已存入数字衣橱")).toHaveCount(0);
  });

  test("blocks tiny lassos in the browser instead of sending them to the model", async ({
    page
  }) => {
    const feedIngestRequests: string[] = [];
    page.on("request", (request) => {
      if (
        request.method() !== "GET" &&
        /\/v1\/(feed|wardrobe|captures|looks|items)/.test(new URL(request.url()).pathname)
      ) {
        feedIngestRequests.push(`${request.method()} ${new URL(request.url()).pathname}`);
      }
    });

    await openFeed(page);
    const overlay = await pauseAndOpenOverlay(page);
    await drawPolygon(page, overlay, 0.06);

    await expect(page.getByRole("status", { name: "圈选太小" })).toBeVisible({
      timeout: 5_000
    });
    await expect(page.getByRole("group", { name: "已圈选的穿搭主体" })).toHaveCount(0);
    expect(feedIngestRequests).toEqual([]);
    await saveEvidence(page, "04-tiny-lasso-blocked-client-side");
  });

  test("saves a whole outfit by right swipe and opens the recovered look in wardrobe", async ({
    page
  }) => {
    await openFeed(page);
    const existingLooks = await openWardrobeAndCountLooks(page);
    await page.getByRole("button", { name: "刷灵感 Feed", exact: true }).click();
    await expect(page.getByTestId("feed")).toBeVisible();

    const savedLookId = await saveWholeOutfitBySwipe(page);
    savedLookToCleanUp = savedLookId;
    await saveEvidence(page, "06-right-swipe-saved-toast");

    await openWardrobeAndCountLooks(page);
    const savedLook = page.locator(`.look-card[data-look-id="${savedLookId}"]`);
    await expect(savedLook).toBeVisible({ timeout: 30_000 });
    await expect
      .poll(() => page.locator(".look-card").count(), { timeout: 30_000 })
      .toBeGreaterThan(existingLooks);
    await expect(savedLook).toContainText("Feed 穿搭灵感");
    await expect(savedLook).not.toContainText("正在整理", { timeout: 150_000 });
    await expect(savedLook).toContainText("灵感收藏 · 已整理");
    await savedLook.click();
    await expect(page.getByText("Feed 穿搭灵感").first()).toBeVisible();
    await saveEvidence(page, "07-wardrobe-recovered-look");
  });
});
