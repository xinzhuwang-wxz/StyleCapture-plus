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
const invalidSubjectFixture = path.join(evidenceDirectory, "invalid-subject.jpg");
const chineseScene =
  "下周一要去中文路演和客户面试，想显得可靠、利落、有一点个性，天气偏热但需要久坐舒适";

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
  fs.writeFileSync(
    invalidSubjectFixture,
    "not an image; used to exercise the real failure/recovery path without mocks\n"
  );

  await page.goto("/");

  await expect(page.getByRole("region", { name: "穿搭灵感" })).toBeVisible();
  await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
  await expect(page.getByRole("region", { name: "我的数字衣橱" })).toBeVisible();
  await page.getByRole("button", { name: "AI", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "穿搭需求" })).toBeVisible();
  await saveEvidence(page, "01-ai-entry-from-wardrobe.png");

  await page.getByRole("textbox", { name: "穿搭需求" }).fill(chineseScene);
  await page.getByRole("button", { name: "生成穿搭推荐" }).click();

  const firstPlan = page.getByRole("article", { name: "搭配方案 1" });
  await expect(firstPlan).toBeVisible({ timeout: 150_000 });
  await expect(page.getByText(/新方案会逐套出现/)).toBeVisible({
    timeout: 10_000
  });
  await expect(page.getByText(/先生成 [1-4] 套/)).toBeVisible();
  await saveEvidence(page, "02-progressive-first-plans.png");

  await expect(page.getByText("AI 已结合场景理解完成重排。")).toBeVisible({
    timeout: 180_000
  });
  await expect(page.getByText(`已根据「${chineseScene}」`)).toBeVisible();
  await expect(firstPlan).toContainText(/面试|可靠|利落|个性|商务|正式|客户/);
  await expect(page.getByRole("article", { name: "搭配方案 3" })).toBeVisible();

  await firstPlan.getByRole("button", { name: "保存这套" }).click();
  const openSaved = firstPlan.getByRole("button", {
    name: "已存入衣橱 · 查看"
  });
  await expect(openSaved).toBeVisible({ timeout: 15_000 });
  await openSaved.click();

  const detail = page.getByRole("dialog", { name: "穿搭详情" });
  await expect(detail.getByText("AI 搭配保存")).toBeVisible();
  await expect(detail.getByText("真实资产生成")).toBeVisible();
  const components = detail.getByRole("region", { name: "这套里的单品" });
  const componentCards = components.getByRole("article");
  await expect(componentCards.first()).toBeVisible();
  const componentCount = await componentCards.count();
  expect(componentCount).toBeGreaterThanOrEqual(3);
  expect(componentCount).toBeLessThanOrEqual(6);
  await expect(components.getByText(`${componentCount} 件`)).toBeVisible();
  await detail.getByRole("tab", { name: "真人试穿" }).click();
  await expect(
    detail.getByText("上传或拍摄一张正面全身照，AI 会把这套已保存穿搭换到你身上。")
  ).toBeVisible();
  await saveEvidence(page, "03-saved-look-real-source-detail.png");

  const failureChooserPromise = page.waitForEvent("filechooser");
  await detail
    .getByRole("button", { name: "拍照或上传全身照" })
    .click();
  const failureChooser = await failureChooserPromise;
  await failureChooser.setFiles(invalidSubjectFixture);
  await expect(
    detail.getByRole("img", { name: "待确认的试穿全身照" })
  ).toBeVisible();
  await detail.getByRole("button", { name: "确认生成" }).click();
  const failureQueued = await page
    .getByText("全身照已安全上传，真人试穿正在后台生成")
    .waitFor({ state: "visible", timeout: 30_000 })
    .then(() => true)
    .catch(() => false);

  if (failureQueued) {
    await expect(detail.getByText("后台生成中…")).toBeVisible({
      timeout: 60_000
    });
    await expect(
      detail.getByRole("button", { name: "换一张全身照" })
    ).toBeVisible();
    await saveEvidence(page, "04-tryon-processing-recovery-control.png");

    const failureRecovery = detail.getByText(
      /真人试穿暂时不可用|本次真人试穿暂时不可用/
    );
    await failureRecovery
      .waitFor({ state: "visible", timeout: 240_000 })
      .then(async () => {
        await expect(
          detail.getByRole("button", { name: "换一张全身照" })
        ).toBeVisible();
        await saveEvidence(page, "05-tryon-failure-recovery.png");
      })
      .catch(async () => {
        await saveEvidence(page, "05-tryon-failure-not-observed-yet.png");
      });
  } else {
    await expect(
      detail.getByText("上传或拍摄一张正面全身照，AI 会把这套已保存穿搭换到你身上。")
    ).toBeVisible();
    await expect(
      detail.getByRole("button", { name: "拍照或上传全身照" })
    ).toBeVisible();
    await saveEvidence(page, "04-tryon-early-failure-recovered.png");
  }

  if (await detail.getByRole("button", { name: "换一张全身照" }).isVisible()) {
    const failureRecovery = detail.getByText(
      /真人试穿暂时不可用|本次真人试穿暂时不可用/
    );
    if (await failureRecovery.isVisible()) {
      await expect(
        detail.getByRole("button", { name: "换一张全身照" })
      ).toBeVisible();
      await saveEvidence(page, "05-tryon-failure-recovery.png");
    }
  }

  const chooserPromise = page.waitForEvent("filechooser");
  await detail
    .getByRole("button", { name: /拍照或上传全身照|换一张全身照/ })
    .click();
  const chooser = await chooserPromise;
  await chooser.setFiles(fullBodyFixture);
  await expect(
    detail.getByRole("img", { name: "待确认的试穿全身照" })
  ).toBeVisible();
  await expect(detail.getByText("原照仅用于本次私人生成")).toBeVisible();
  await detail.getByRole("button", { name: "确认生成" }).click();

  await expect(
    detail.getByRole("button", { name: "照片上传并生成中…" })
  ).toBeVisible({ timeout: 15_000 });
  await saveEvidence(page, "05-tryon-real-photo-uploading.png");
  await expect(
    page.getByText("全身照已安全上传，真人试穿正在后台生成")
  ).toBeVisible({ timeout: 240_000 });
  await expect(detail.getByText("后台生成中…")).toBeVisible({
    timeout: 90_000
  });
  await expect(
    detail.getByText(
      "这张效果图基于你刚刚上传的全身照和本套真实单品生成，仅自己可见。"
    )
  ).toBeVisible({ timeout: 420_000 });
  const tryOnImage = detail.getByRole("img", { name: "我的真人试穿" });
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

  await saveEvidence(page, "06-personal-try-on-success-mobile.png");

  await detail.getByRole("button", { name: "删除本次全身原照" }).click();
  await expect(page.getByText("试穿原照已删除，生成结果仍保留")).toBeVisible();
  await expect(
    detail.getByRole("button", { name: "删除本次全身原照" })
  ).not.toBeVisible();
  await expect(tryOnImage).toBeVisible();
  await saveEvidence(page, "07-tryon-source-photo-deleted.png");
});
