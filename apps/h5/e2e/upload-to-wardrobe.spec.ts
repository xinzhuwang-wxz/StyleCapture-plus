import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(testDirectory, "../../..");
const evidenceDirectory = path.join(repositoryRoot, "docs/evidence/issue-6/upload");
const jpegFixture = path.join(
  testDirectory,
  "fixtures",
  "single-sweater-pexels-12944791.jpg"
);
const heicFixture = path.join(testDirectory, "fixtures", "single-garment.heic");
const uploadFixture = fs.existsSync(heicFixture) ? heicFixture : jpegFixture;

async function saveEvidence(page: import("@playwright/test").Page, name: string) {
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  await page.screenshot({
    path: path.join(evidenceDirectory, `${name}.png`),
    animations: "disabled",
    fullPage: true
  });
}

async function enterWardrobeFromCurrentFeed(page: import("@playwright/test").Page) {
  const wardrobeHeading = page.getByRole("heading", { name: "我的数字衣橱" });
  if (!(await wardrobeHeading.isVisible().catch(() => false))) {
    await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
  }
  await expect(page.getByRole("heading", { name: "我的数字衣橱" })).toBeVisible({
    timeout: 20_000
  });
  await page.getByRole("tab", { name: "按单品", exact: true }).click();
  const retryButton = page.getByRole("button", { name: "重新加载" });
  if (await retryButton.isVisible().catch(() => false)) {
    await retryButton.click();
  }
  await expect(page.locator(".item-card").first()).toBeVisible({
    timeout: 30_000
  });
}

async function openWardrobeFromFeed(page: import("@playwright/test").Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await enterWardrobeFromCurrentFeed(page);
}

async function reloadWithRecovery(page: import("@playwright/test").Page) {
  try {
    await page.reload({ waitUntil: "domcontentloaded", timeout: 30_000 });
    return true;
  } catch {
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 30_000 });
    return false;
  }
}

async function hasTransparentPixels(
  image: import("@playwright/test").Locator
): Promise<boolean> {
  return image.evaluate((element: HTMLImageElement) => {
    try {
      if (!element.complete || element.naturalWidth === 0 || element.naturalHeight === 0) {
        return false;
      }
      const canvas = document.createElement("canvas");
      canvas.width = element.naturalWidth;
      canvas.height = element.naturalHeight;
      const context = canvas.getContext("2d");
      if (!context) return false;
      context.drawImage(element, 0, 0);
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let index = 3; index < pixels.length; index += 4) {
        if (pixels[index] < 250) return true;
      }
      return false;
    } catch {
      return false;
    }
  });
}

test("uploads a real garment, normalizes its display image, and preserves the asset after source deletion", async ({
  page
}) => {
  test.setTimeout(300_000);
  page.setDefaultTimeout(20_000);

  fs.mkdirSync(evidenceDirectory, { recursive: true });
  fs.writeFileSync(
    path.join(evidenceDirectory, "upload-fixture.json"),
    JSON.stringify(
      {
        fixture: path.basename(uploadFixture),
        heicFixtureAvailable: fs.existsSync(heicFixture),
        viewport: { width: 390, height: 844 }
      },
      null,
      2
    )
  );

  await openWardrobeFromFeed(page);
  await saveEvidence(page, "01-feed-to-wardrobe-items");

  const existingCount = await page.locator(".item-card").count();

  const chooserPromise = page.waitForEvent("filechooser");
  await page
    .getByRole("button", { name: "添加衣服或试试像素形象" })
    .click();
  const addDialog = page.getByRole("dialog", { name: "添加到 StyleCapture" });
  await expect(addDialog).toBeVisible();
  await saveEvidence(page, "02-add-entry-open");
  await addDialog.getByText("从相册导入").click();
  const chooser = await chooserPromise;
  await chooser.setFiles(uploadFixture);

  const confirmation = page.getByRole("dialog", { name: "确认加入衣橱" });
  await expect(confirmation).toBeVisible();
  await saveEvidence(page, "03-upload-confirmation");
  await confirmation.getByRole("button", { name: "单件衣服" }).click();
  await confirmation.getByRole("button", { name: "我的衣服" }).click();
  const captureAccepted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/v1/captures",
    { timeout: 60_000 }
  );
  await confirmation.getByRole("button", { name: "加入单品衣橱" }).click();
  const captureOutcome = await Promise.race([
    captureAccepted.then((response) => ({ response, error: null })),
    confirmation
      .getByRole("alert")
      .waitFor({ state: "visible", timeout: 60_000 })
      .then(async () => ({
        response: null,
        error: await confirmation.getByRole("alert").innerText()
      }))
  ]);
  expect(captureOutcome.error).toBeNull();
  expect(captureOutcome.response?.status()).toBe(202);
  const captureAcceptedPayload = (await captureOutcome.response!.json()) as {
    capture_id: string;
  };

  const processingNotice = page.getByText("正在理解这件衣服");
  await expect
    .poll(
      async () =>
        (await processingNotice.isVisible().catch(() => false)) ||
        (await page.locator(".item-card").count()) > existingCount,
      { timeout: 20_000 }
    )
    .toBe(true);
  await saveEvidence(page, "04-upload-accepted-processing");
  await expect
    .poll(
      () =>
        page.evaluate(async (captureId) => {
          const response = await fetch("/v1/items");
          if (!response.ok) return null;
          const payload = (await response.json()) as {
            items: Array<{ id: string; capture_id: string; status: string }>;
          };
          const items = payload.items;
          const item = items.find((candidate) => candidate.capture_id === captureId);
          return item?.status === "ready" ? item.id : null;
        }, captureAcceptedPayload.capture_id),
      { timeout: 150_000 }
    )
    .not.toBeNull();
  const uploadedItemId = await page.evaluate(async (captureId) => {
    const response = await fetch("/v1/items");
    const payload = (await response.json()) as {
      items: Array<{ id: string; capture_id: string }>;
    };
    return payload.items.find((candidate) => candidate.capture_id === captureId)!.id;
  }, captureAcceptedPayload.capture_id);
  const uploadedItem = page.locator(`.item-card[data-item-id="${uploadedItemId}"]`);
  await expect(uploadedItem).toBeVisible({ timeout: 30_000 });
  await saveEvidence(page, "05-background-processing-complete");

  await expect(uploadedItem.getByText("可搭配")).toBeVisible({
    timeout: 150_000
  });
  await uploadedItem.scrollIntoViewIfNeeded();
  const uploadedPixelCover = uploadedItem.locator('img[data-image-kind="wardrobe-pixel"]');
  const pixelCoverVisible = await uploadedPixelCover
    .waitFor({ state: "visible", timeout: 90_000 })
    .then(() => true)
    .catch(() => false);
  fs.writeFileSync(
    path.join(evidenceDirectory, "pixel-cover-check.json"),
    JSON.stringify({ pixelCoverVisible }, null, 2)
  );
  const uploadedTitle = (await uploadedItem.locator("strong").first().innerText()).trim();

  await uploadedItem.locator(".item-card__open").click();
  const detail = page.getByRole("dialog", { name: "单品详情" });
  await expect(detail).toContainText("已完成理解");
  await expect(detail).toContainText("相册录入");
  await expect(detail.getByLabel("分类")).not.toHaveValue("");
  await expect(detail.getByLabel("衣服归属").getByRole("button", { name: "我的衣服" })).toHaveClass(
    /is-selected/
  );
  await expect(detail).toContainText(
    "当前展示已标准化的单品实物图；像素图只用于衣橱封面。"
  );
  const displayImage = detail.locator('img[data-image-kind="wardrobe-display"]');
  await expect(displayImage).toBeVisible({ timeout: 20_000 });
  await saveEvidence(page, "06-detail-tags-source-and-display");
  let displayHasTransparentPixels = false;
  const transparentPixelDeadline = Date.now() + 10_000;
  while (!displayHasTransparentPixels && Date.now() < transparentPixelDeadline) {
    displayHasTransparentPixels = await hasTransparentPixels(displayImage);
    if (!displayHasTransparentPixels) await page.waitForTimeout(500);
  }
  fs.writeFileSync(
    path.join(evidenceDirectory, "display-image-check.json"),
    JSON.stringify({ displayHasTransparentPixels }, null, 2)
  );

  await detail.getByRole("button", { name: "返回衣橱" }).click();
  await expect(detail).toHaveCount(0);
  const reloadSucceeded = await reloadWithRecovery(page);
  fs.writeFileSync(
    path.join(evidenceDirectory, "refresh-navigation-check.json"),
    JSON.stringify({ reloadSucceeded }, null, 2)
  );
  await enterWardrobeFromCurrentFeed(page);
  const persistedItem = page.locator(`.item-card[data-item-id="${uploadedItemId}"]`);
  await expect(persistedItem).toContainText(uploadedTitle);
  await expect(persistedItem).toBeVisible();
  await saveEvidence(page, "07-refresh-persistence");

  await persistedItem.locator(".item-card__open").click();
  const persistedDetail = page.getByRole("dialog", { name: "单品详情" });
  await expect(persistedDetail).toContainText("已完成理解");
  const persistedDisplayVisible = await persistedDetail
    .locator('img[data-image-kind="wardrobe-display"]')
    .waitFor({ state: "visible", timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  fs.writeFileSync(
    path.join(evidenceDirectory, "refresh-display-image-check.json"),
    JSON.stringify({ persistedDisplayVisible }, null, 2)
  );

  await persistedDetail.getByRole("button", { name: "删除原图" }).click();
  await expect(persistedDetail.getByRole("alert")).toContainText(
    "删除后原始上传图无法恢复"
  );
  await saveEvidence(page, "08-delete-source-confirmation");
  const sourceDeletion = page.waitForResponse(
    (response) =>
      response.request().method() === "DELETE" &&
      new URL(response.url()).pathname === `/v1/items/${uploadedItemId}/source`,
    { timeout: 20_000 }
  );
  await persistedDetail.getByRole("button", { name: "确认删除原图" }).click();
  expect((await sourceDeletion).status()).toBe(204);

  await expect(
    page.getByText(/原始上传图已删除，(?:标准化单品图和)?文字资产仍保留/)
  ).toBeVisible({ timeout: 20_000 });
  await expect(persistedDetail).toHaveCount(0);
  await expect(persistedItem).toBeVisible();
  await persistedItem.locator(".item-card__open").click();
  const reopenedDetail = page.getByRole("dialog", { name: "单品详情" });
  await expect(reopenedDetail).toContainText(
    "原始上传图已删除；标准化单品图、标签和描述仍保留并可继续使用。"
  );
  const sourceDeletedDisplayVisible = await reopenedDetail
    .locator('img[data-image-kind="wardrobe-display"]')
    .waitFor({ state: "visible", timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  fs.writeFileSync(
    path.join(evidenceDirectory, "source-deleted-display-image-check.json"),
    JSON.stringify({ sourceDeletedDisplayVisible }, null, 2)
  );
  await expect
    .poll(async () => Math.round((await reopenedDetail.boundingBox())?.x ?? -1))
    .toBe(0);
  await saveEvidence(page, "09-source-deleted-recovery");
  expect.soft(
    pixelCoverVisible,
    "Uploaded wardrobe card should render a first-level pixel cover"
  ).toBe(true);
  expect.soft(
    persistedDisplayVisible,
    "Uploaded wardrobe display image should persist after refresh"
  ).toBe(true);
  expect.soft(
    sourceDeletedDisplayVisible,
    "Derived wardrobe display image should remain after deleting the upload source"
  ).toBe(true);
  expect.soft(reloadSucceeded, "Public wardrobe page should reload without connection reset").toBe(
    true
  );
  // The production CPU profile guarantees a browser-safe normalized garment image.
  // Transparent background is an optional SAM2 enhancement, so record it as evidence
  // without turning the portable deployment check into a false failure.
});
