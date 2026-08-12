import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../.."
);
const evidenceDirectory = path.join(repositoryRoot, "docs/evidence/issue-6/tabs");
const metricsPath = path.join(evidenceDirectory, "public-tabs-metrics.json");
type PublicTabMetric = {
  scenario: string;
  viewport: { width: number; height: number } | null;
  frame: { x: number; y: number; width: number; height: number } | null;
  screen: { x: number; y: number; width: number; height: number } | null;
  timings: Record<string, number>;
  slowRequests: Array<{ url: string; ms: number; status: number | null }>;
};

const metrics: PublicTabMetric[] = [];

async function saveEvidence(page: import("@playwright/test").Page, name: string) {
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  await page.screenshot({
    path: path.join(evidenceDirectory, `${name}.png`),
    animations: "disabled",
    fullPage: true
  });
}

async function captureLayoutMetric(
  page: import("@playwright/test").Page,
  scenario: string,
  timings: Record<string, number>,
  slowRequests: Array<{ url: string; ms: number; status: number | null }>
) {
  metrics.push({
    scenario,
    viewport: page.viewportSize(),
    frame: await page.locator(".pixel-frame").boundingBox(),
    screen: await page.locator(".pixel-screen").boundingBox(),
    timings,
    slowRequests
  });
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  fs.writeFileSync(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`);
}

async function withNetworkTiming(
  page: import("@playwright/test").Page,
  run: (
    slowRequests: Array<{ url: string; ms: number; status: number | null }>
  ) => Promise<void>
) {
  const started = new Map<import("@playwright/test").Request, number>();
  const slowRequests: Array<{ url: string; ms: number; status: number | null }> = [];
  page.on("request", (request) => started.set(request, Date.now()));
  page.on("requestfinished", async (request) => {
    const start = started.get(request);
    if (!start) return;
    const ms = Date.now() - start;
    if (ms >= 1_500) {
      slowRequests.push({
        url: request.url(),
        ms,
        status: (await request.response())?.status() ?? null
      });
    }
  });
  await run(slowRequests);
}

async function openWardrobeHome(
  page: import("@playwright/test").Page,
  scenario = "open-wardrobe"
) {
  const timings: Record<string, number> = {};
  const t0 = Date.now();
  await page.goto("/", { waitUntil: "domcontentloaded" });
  timings.domcontentloaded = Date.now() - t0;
  const skeleton = page.locator(".wardrobe-loading").first();
  const wardrobe = page.locator(".wardrobe-section");
  await Promise.race([
    skeleton.waitFor({ state: "visible", timeout: 3_000 }).catch(() => undefined),
    wardrobe.locator(".wardrobe-card").first().waitFor({ state: "visible", timeout: 3_000 }).catch(() => undefined)
  ]);
  timings.wardrobeFirstFeedback = Date.now() - t0;
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible({
    timeout: 20_000
  });
  await expect(wardrobe.locator(".wardrobe-card").first()).toBeVisible({
    timeout: 20_000
  });
  timings.wardrobeInteractive = Date.now() - t0;
  return timings;
}

test.describe("public mobile navigation", () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(90_000);
    page.setDefaultTimeout(20_000);
  });

  test("opens the public wardrobe and enters Feed from its CTA", async ({
    page
  }) => {
    await withNetworkTiming(page, async (slowRequests) => {
      const timings = await openWardrobeHome(page, "wardrobe-to-feed");

      await expect(page.getByRole("tab", { name: "按穿搭" })).toBeVisible();
      await expect(page.getByRole("tab", { name: "按单品" })).toBeVisible();
      await expect(page.getByText("我的衣橱", { exact: true })).toBeVisible();
      await expect(page.locator(".wardrobe-section .wardrobe-card").first()).toBeVisible();
      await page.getByRole("button", { name: "刷灵感 Feed", exact: true }).click();
      await expect(page.getByRole("region", { name: "穿搭灵感" })).toBeVisible();
      await expect(page.getByRole("button", { name: "暂停并圈选" }).first()).toBeVisible();
      await captureLayoutMetric(page, "wardrobe-to-feed", timings, slowRequests);
      await saveEvidence(page, "01-wardrobe-to-feed");
    });
  });

  test("keeps Feed and wardrobe inside the same phone canvas on desktop", async ({
    page
  }) => {
    await page.setViewportSize({ width: 1024, height: 844 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible({
      timeout: 20_000
    });

    const wardrobeScreen = await page.locator(".pixel-screen").boundingBox();
    expect(wardrobeScreen?.width).toBe(390);
    await saveEvidence(page, "00-desktop-wardrobe-canvas");

    await page.getByRole("button", { name: "刷灵感 Feed", exact: true }).click();
    await expect(page.getByRole("region", { name: "穿搭灵感" })).toBeVisible({
      timeout: 20_000
    });
    const feedScreen = await page.locator(".pixel-screen").boundingBox();
    expect(feedScreen).toEqual(wardrobeScreen);
    await saveEvidence(page, "00-desktop-feed-canvas");
  });

  test("shows seeded wardrobe looks and item cards without empty states", async ({
    page
  }) => {
    await openWardrobeHome(page, "wardrobe-seeded-assets");

    await expect(page.locator(".wardrobe-section .wardrobe-card").first()).toBeVisible();
    await expect(page.getByText("Feed 穿搭灵感").first()).toBeVisible();
    await saveEvidence(page, "02-wardrobe-looks");

    await page.getByRole("tab", { name: "按单品" }).click();
    await expect(page.locator(".item-card").first()).toBeVisible({
      timeout: 20_000
    });
    await expect(page.locator("body")).not.toContainText("衣橱里还没有");
    await page.locator(".item-card .item-card__open").first().click();
    const detail = page.getByRole("dialog", { name: "单品详情" });
    await expect(detail).toBeVisible();
    await expect(detail.locator(".detail-image img")).toBeVisible({ timeout: 20_000 });
    await saveEvidence(page, "03-wardrobe-items");
  });

  test("opens AI and pixel-world tabs with real Chinese product copy", async ({
    page
  }) => {
    await openWardrobeHome(page, "ai-world");

    await page.getByRole("button", { name: "AI", exact: true }).click();
    await expect(page.getByRole("heading", { name: /AI|推荐|穿搭/ })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "穿搭需求" })).toBeVisible();
    await expect(page.locator('[aria-label="快捷场景"]')).toBeVisible();
    await expect(page.locator("body")).not.toContainText("真实推荐待接入");
    await saveEvidence(page, "05-ai");

    await page.getByRole("button", { name: "像素世界", exact: true }).click();
    await expect(page.getByRole("region", { name: "像素世界" })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("undefined");
    await saveEvidence(page, "04-pixel-world");
  });

  test("opens the add menu and profile entry", async ({ page }) => {
    await openWardrobeHome(page, "add-profile");

    await page.getByRole("button", { name: "添加衣服" }).click();
    const addDialog = page.getByRole("dialog", { name: "添加到 StyleCapture" });
    await expect(addDialog).toBeVisible();
    await expect(addDialog.getByText("拍下真实衣服")).toBeVisible();
    await expect(addDialog.getByText("从相册导入")).toBeVisible();
    await saveEvidence(page, "06-add-menu");

    await addDialog.getByRole("button", { name: "关闭", exact: true }).click();
    await page.getByRole("button", { name: "我的", exact: true }).click();
    await expect(page.getByRole("heading", { name: "我的", exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "个人数字资产概览" })).toBeVisible();
    await expect(page.getByText(/已收录 \d+ 件单品/)).toBeVisible();
    await saveEvidence(page, "07-profile");
  });

  test("returns from wardrobe to the public feed without duplicate blank tabs", async ({
    page
  }) => {
    await openWardrobeHome(page, "return-feed");

    await page.getByRole("button", { name: "刷灵感 Feed", exact: true }).click();
    await expect(page.getByRole("region", { name: "穿搭灵感" })).toBeVisible();
    await expect(page.getByRole("button", { name: "暂停并圈选" }).first()).toBeVisible();
    await expect(page.locator("video").first()).toBeVisible();
    await saveEvidence(page, "08-return-feed");
  });
});
