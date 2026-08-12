import { expect, test } from "@playwright/test";
import fs from "node:fs";

const heicFixture = process.env.STYLECAPTURE_HEIC_FIXTURE ?? "";
let uploadedItemToCleanUp: string | null = null;

test.afterEach(async ({ page }) => {
  if (uploadedItemToCleanUp === null) return;
  await page
    .evaluate(async (itemId) => {
      await fetch(`/v1/items/${itemId}`, { method: "DELETE" });
    }, uploadedItemToCleanUp)
    .catch(() => undefined);
  uploadedItemToCleanUp = null;
});

test("accepts a real iPhone HEIC upload through the public wardrobe flow", async ({
  page
}) => {
  test.skip(!heicFixture || !fs.existsSync(heicFixture), "Set STYLECAPTURE_HEIC_FIXTURE");
  test.setTimeout(300_000);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible();

  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "添加衣服" }).click();
  await page.getByRole("dialog", { name: "添加到 StyleCapture" }).getByText("从相册导入").click();
  const chooser = await chooserPromise;
  await chooser.setFiles(heicFixture);

  const confirmation = page.getByRole("dialog", { name: "确认加入衣橱" });
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "单件衣服" }).click();
  await confirmation.getByRole("button", { name: "已拥有" }).click();
  const accepted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/v1/captures"
  );
  await confirmation.getByRole("button", { name: "加入单品衣橱" }).click();
  const acceptedResponse = await accepted;
  expect(acceptedResponse.status()).toBe(202);
  const acceptedPayload = (await acceptedResponse.json()) as {
    capture_id: string;
  };

  await expect(page.getByRole("alert")).toContainText("已安全加入，识别会在后台继续");
  await expect(page.getByLabel("1 个处理中")).toBeVisible();
  await expect(page.getByText("不支持的文件格式")).toHaveCount(0);

  await expect
    .poll(
      () =>
        page.evaluate(async (captureId) => {
          const response = await fetch("/v1/items");
          if (!response.ok) return null;
          const payload = (await response.json()) as {
            items: Array<{ id: string; capture_id: string; status: string }>;
          };
          const item = payload.items.find(
            (candidate) => candidate.capture_id === captureId
          );
          return item?.status === "ready" ? item.id : null;
        }, acceptedPayload.capture_id),
      { timeout: 150_000 }
    )
    .not.toBeNull();

  uploadedItemToCleanUp = await page.evaluate(async (captureId) => {
    const response = await fetch("/v1/items");
    const payload = (await response.json()) as {
      items: Array<{ id: string; capture_id: string }>;
    };
    return payload.items.find((candidate) => candidate.capture_id === captureId)!.id;
  }, acceptedPayload.capture_id);
  await expect(
    page.locator(`.item-card[data-item-id="${uploadedItemToCleanUp}"]`)
  ).toContainText("已整理");
});
