import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../.."
);
const fullBodyFixture = path.join(
  repositoryRoot,
  "apps/h5/e2e/fixtures/garment.jpg"
);
const evidenceDirectory = path.join(
  repositoryRoot,
  "docs/evidence/issue-6/ai-tryon"
);
const chineseScene =
  "下周一要去中文路演和客户面试，想显得可靠、利落、有一点个性，天气偏热但需要久坐舒适";
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

async function saveEvidence(page: Parameters<typeof expect>[0], name: string) {
  await page.screenshot({
    path: path.join(evidenceDirectory, name),
    animations: "disabled",
    fullPage: true
  });
}

test("plans progressively, saves a real look, and generates a personal try-on", async ({
  page
}) => {
  test.setTimeout(900_000);
  page.setDefaultTimeout(20_000);
  fs.mkdirSync(evidenceDirectory, { recursive: true });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible({
    timeout: 20_000
  });
  await expect(page.locator(".wardrobe-section .wardrobe-card").first()).toBeVisible({
    timeout: 20_000
  });
  await page.getByRole("button", { name: "AI", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "穿搭需求" })).toBeVisible();
  await saveEvidence(page, "01-ai-entry-from-wardrobe.png");

  await page.getByRole("textbox", { name: "穿搭需求" }).fill(chineseScene);
  await page.getByRole("button", { name: "生成穿搭推荐" }).click();

  const firstPlan = page.getByRole("article", { name: "搭配方案 1" });
  await expect(firstPlan).toBeVisible({ timeout: 150_000 });
  await saveEvidence(page, "02-progressive-first-plans.png");

  await expect(page.getByText("AI 已完成分析与重排")).toBeVisible({
    timeout: 180_000
  });
  await expect(page.getByText(new RegExp(`已根据「${chineseScene}」生成`))).toBeVisible();
  await expect(firstPlan).toContainText(/面试|可靠|利落|个性|商务|正式|客户/);
  await expect(page.getByRole("article", { name: "搭配方案 3" })).toBeVisible();

  const savedLookResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith("/save-look"),
    { timeout: 60_000 }
  );
  await firstPlan.getByRole("button", { name: "保存这套" }).click();
  const savedLookResponse = await savedLookResponsePromise;
  expect(savedLookResponse.status()).toBe(201);
  const savedLookPayload = (await savedLookResponse.json()) as { look_id: string };
  savedLookToCleanUp = savedLookPayload.look_id;
  const openSaved = firstPlan.getByRole("button", {
    name: "已存入衣橱 · 查看"
  });
  await expect(openSaved).toBeVisible({ timeout: 15_000 });
  await openSaved.click();

  const detail = page.getByRole("dialog", { name: "穿搭详情" });
  await expect(detail).toBeVisible();
  const components = detail.getByRole("region", { name: "套装所含单品" });
  const componentCards = components.getByRole("button", {
    name: /查看单品操作/
  });
  await expect(componentCards.first()).toBeVisible();
  const componentCount = await componentCards.count();
  expect(componentCount).toBeGreaterThanOrEqual(3);
  expect(componentCount).toBeLessThanOrEqual(6);
  await expect(components.getByText(`${componentCount} 件`)).toBeVisible();
  await expect(detail.getByText("查看真人试穿效果")).toBeVisible();
  await saveEvidence(page, "03-saved-look-real-source-detail.png");

  await detail.getByRole("button", { name: "查看效果" }).click();
  const photoPicker = page.getByRole("dialog", { name: "选择试穿形象" });
  await expect(photoPicker).toBeVisible();
  const chooserPromise = page.waitForEvent("filechooser");
  await photoPicker.getByText("从相册上传").click();
  const chooser = await chooserPromise;
  await chooser.setFiles(fullBodyFixture);
  await expect(photoPicker.getByRole("radio", { name: /第 1 张形象照/ })).toBeVisible();
  const tryOnQueuedPromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/v1\/looks\/[^/]+\/renders$/.test(new URL(response.url()).pathname),
    { timeout: 60_000 }
  );
  await photoPicker.getByRole("button", { name: "使用这张形象试穿" }).click();
  const tryOnQueued = await tryOnQueuedPromise;
  expect(tryOnQueued.status()).toBe(202);
  await saveEvidence(page, "04-tryon-real-photo-uploading.png");
  await expect(
    page.getByText("全身照已安全上传，真人试穿正在后台生成")
  ).toBeVisible({ timeout: 240_000 });
  await expect(detail.getByRole("status").getByText("后台生成中")).toBeVisible({
    timeout: 90_000
  });
  await expect(detail.getByText("AI试穿效果")).toBeVisible({ timeout: 420_000 });
  const tryOnImage = detail.getByRole("img", { name: "真人试穿穿搭卡片" });
  await expect(tryOnImage).toBeVisible();
  await expect
    .poll(() =>
      tryOnImage.evaluate(
        (image: HTMLImageElement) =>
          image.complete && image.naturalWidth > 0 && image.naturalHeight > 0
      )
    )
    .toBe(true);
  await expect(
    page.getByText("全身照已安全上传，真人试穿正在后台生成")
  ).not.toBeVisible({ timeout: 10_000 });

  await saveEvidence(page, "05-personal-try-on-success-mobile.png");

  await detail.getByRole("button", { name: "删除本次全身原照" }).click();
  await expect(page.getByText("试穿原照已删除，生成结果仍保留")).toBeVisible();
  await expect(
    detail.getByRole("button", { name: "删除本次全身原照" })
  ).not.toBeVisible();
  await expect(tryOnImage).toBeVisible();
  await saveEvidence(page, "06-tryon-source-photo-deleted.png");
});
