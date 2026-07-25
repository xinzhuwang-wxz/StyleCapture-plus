import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../.."
);
const fullBodyFixture = path.join(
  repositoryRoot,
  "services/backend/src/stylecapture_backend/demo_assets/look-city-commute.jpg"
);
const evidenceDirectory = path.join(
  repositoryRoot,
  "artifacts/issue-5"
);

test("plans progressively, saves a real look, and generates a personal try-on", async ({
  page
}) => {
  test.setTimeout(210_000);
  await page.goto("/");

  await page.getByRole("button", { name: "AI", exact: true }).click();
  await page.getByRole("button", { name: "通勤面试", exact: true }).click();

  const firstPlan = page.getByRole("article", { name: "搭配方案 1" });
  await expect(firstPlan).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("AI 已结合场景理解完成重排。")).toBeVisible({
    timeout: 75_000
  });

  await firstPlan.getByRole("button", { name: "保存这套" }).click();
  const openSaved = firstPlan.getByRole("button", {
    name: "已存入衣橱 · 查看"
  });
  await expect(openSaved).toBeVisible({ timeout: 15_000 });
  await openSaved.click();

  const detail = page.getByRole("dialog", { name: "穿搭详情" });
  await expect(detail.getByText("AI 搭配保存")).toBeVisible();
  const components = detail.getByRole("region", { name: "这套里的单品" });
  const componentCards = components.getByRole("article");
  await expect(componentCards.first()).toBeVisible();
  const componentCount = await componentCards.count();
  expect(componentCount).toBeGreaterThanOrEqual(3);
  expect(componentCount).toBeLessThanOrEqual(6);
  await expect(components.getByText(`${componentCount} 件`)).toBeVisible();
  await detail.getByRole("tab", { name: "真人试穿" }).click();

  const chooserPromise = page.waitForEvent("filechooser");
  await detail
    .getByRole("button", { name: "拍照或上传全身照" })
    .click();
  const chooser = await chooserPromise;
  await chooser.setFiles(fullBodyFixture);
  await expect(
    detail.getByRole("img", { name: "待确认的试穿全身照" })
  ).toBeVisible();
  await expect(detail.getByText("原照仅用于本次私人生成")).toBeVisible();
  await detail.getByRole("button", { name: "确认生成" }).click();

  await expect(
    page.getByText("全身照已安全上传，真人试穿正在后台生成")
  ).toBeVisible({ timeout: 15_000 });
  await expect(
    detail.getByText(
      "这张效果图基于你刚刚上传的全身照和本套真实单品生成，仅自己可见。"
    )
  ).toBeVisible({ timeout: 150_000 });
  await expect(detail.getByRole("img", { name: "我的真人试穿" })).toBeVisible();
  await expect(
    page.getByText("全身照已安全上传，真人试穿正在后台生成")
  ).not.toBeVisible({ timeout: 10_000 });

  await page.screenshot({
    path: path.join(evidenceDirectory, "personal-try-on-mobile.png"),
    animations: "disabled",
    fullPage: true
  });

  await detail.getByRole("button", { name: "删除本次全身原照" }).click();
  await expect(page.getByText("试穿原照已删除，生成结果仍保留")).toBeVisible();
  await expect(
    detail.getByRole("button", { name: "删除本次全身原照" })
  ).not.toBeVisible();
  await expect(detail.getByRole("img", { name: "我的真人试穿" })).toBeVisible();
});
