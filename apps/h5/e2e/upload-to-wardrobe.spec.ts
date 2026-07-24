import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const fixture = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "fixtures",
  "garment.jpg"
);

test("uploads a real garment and exposes honest retryable processing", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible();
  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "从相册选", exact: true }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles(fixture);

  const confirmation = page.getByRole("dialog", { name: "确认加入衣橱" });
  await expect(confirmation).toBeVisible();
  const submit = confirmation.getByRole("button", { name: "加入衣橱" });
  await expect(submit).toBeDisabled();

  await confirmation
    .getByRole("button", {
      name: "我的衣服 已经拥有，可以直接参与搭配",
      exact: true
    })
    .click();
  await submit.click();

  await expect(page.getByText("已安全加入，识别会在后台继续")).toBeVisible();
  await expect(page.getByText("正在理解这件衣服")).toBeVisible();
  await expect(page.getByText("识别失败")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "重新识别" })).toBeVisible();

  const failedItem = page.locator(".item-card").filter({ hasText: "识别失败" }).first();
  await failedItem.locator(".item-card__open").click();

  const detail = page.getByRole("dialog", { name: "单品详情" });
  await expect(detail).toBeVisible();
  await detail.getByRole("button", { name: "删除原图" }).click();
  await expect(detail.getByRole("alert")).toContainText("删除后原图无法恢复");
  await detail.getByRole("button", { name: "确认删除原图" }).click();

  await expect(detail).toHaveCount(0);
  await expect(page.getByText("原图已删除，文字资产仍保留在衣橱中")).toBeVisible();
  await expect(page.getByLabel("原图不可用")).toBeVisible();

  await page.reload();
  const deletedItem = page.locator(".item-card").filter({ has: page.getByLabel("原图不可用") });
  await expect(deletedItem).toContainText("识别失败", { timeout: 20_000 });
  await expect(deletedItem.getByRole("button", { name: "重新识别" })).toHaveCount(0);
  await deletedItem.locator(".item-card__open").click();
  const deletedDetail = page.getByRole("dialog", { name: "单品详情" });
  await expect(deletedDetail).toContainText(
    "原图已删除，保留的标签和描述仍可继续编辑。"
  );
  await expect
    .poll(async () => (await deletedDetail.boundingBox())?.x ?? Number.POSITIVE_INFINITY)
    .toBeLessThan(1);
  await page.screenshot({
    path: path.resolve(
      process.cwd(),
      "../../artifacts/issue-1/08-source-deleted-reload-mobile.png"
    ),
    animations: "disabled"
  });
});
