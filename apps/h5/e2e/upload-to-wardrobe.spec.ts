import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const fixture = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "fixtures",
  "single-sweater-pexels-12944791.jpg"
);

test("uploads a real garment, normalizes its display image, and preserves the asset after source deletion", async ({
  page
}) => {
  test.setTimeout(180_000);
  await page.goto("/");
  await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible();
  await page.getByRole("button", { name: "单品", exact: true }).click();
  await expect(page.locator(".item-card")).toHaveCount(10);
  const existingCount = await page.locator(".item-card").count();

  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "从相册选", exact: true }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles(fixture);

  const confirmation = page.getByRole("dialog", { name: "确认加入衣橱" });
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "单件衣服" }).click();
  await confirmation.getByRole("button", { name: "我的衣服" }).click();
  await confirmation.getByRole("button", { name: "加入单品衣橱" }).click();

  await expect(page.getByText("已安全加入，识别会在后台继续")).toBeVisible();
  await expect(page.getByText("正在理解这件衣服")).toBeVisible();
  await expect(page.getByText("正在理解这件衣服")).not.toBeVisible({
    timeout: 150_000
  });
  await expect(page.locator(".item-card")).toHaveCount(existingCount + 1);

  const uploadedItem = page.locator(".item-card").first();
  await expect(uploadedItem.getByText("可搭配")).toBeVisible({
    timeout: 150_000
  });
  const displayImage = uploadedItem.locator('img[data-image-kind="wardrobe-display"]');
  await expect(displayImage).toBeVisible();
  await expect
    .poll(
      () =>
        displayImage.evaluate(async (image: HTMLImageElement) => {
          const response = await fetch(image.src);
          const blob = await response.blob();
          const bitmap = await createImageBitmap(blob);
          const canvas = document.createElement("canvas");
          canvas.width = bitmap.width;
          canvas.height = bitmap.height;
          const context = canvas.getContext("2d");
          if (!context) return false;
          context.drawImage(bitmap, 0, 0);
          const pixels = context.getImageData(
            0,
            0,
            canvas.width,
            canvas.height
          ).data;
          for (let index = 3; index < pixels.length; index += 64) {
            if (pixels[index] < 250) return blob.type === "image/png";
          }
          return false;
        }),
      { timeout: 10_000 }
    )
    .toBe(true);

  await uploadedItem.locator(".item-card__open").click();
  const detail = page.getByRole("dialog", { name: "单品详情" });
  await expect(detail).toContainText("已完成理解");
  await detail.getByRole("button", { name: "删除原图" }).click();
  await expect(detail.getByRole("alert")).toContainText("删除后原图无法恢复");
  await detail.getByRole("button", { name: "确认删除原图" }).click();

  await expect(detail).toHaveCount(0);
  await expect(page.getByText("原图已删除，文字资产仍保留在衣橱中")).toBeVisible();
  await expect(uploadedItem.locator('img[data-image-kind="wardrobe-display"]')).toBeVisible();
  await uploadedItem.locator(".item-card__open").click();
  await expect(page.getByRole("dialog", { name: "单品详情" })).toContainText(
    "原图已删除，保留的标签和描述仍可继续编辑。"
  );

  await page.screenshot({
    path: path.resolve(
      process.cwd(),
      "../../artifacts/issue-5/upload-normalized-source-deleted-mobile.png"
    ),
    animations: "disabled",
    fullPage: true
  });
});
