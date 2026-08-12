import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../.."
);
const evidenceDirectory = path.join(
  repositoryRoot,
  "docs/evidence/issue-6/pixel-trial"
);
const fullBodyFixture = path.join(
  repositoryRoot,
  "apps/h5/public/feed/posters/pexels-7681932.jpg"
);
const invalidFixture = path.join(evidenceDirectory, "invalid-upload.txt");

async function saveEvidence(page: Page, name: string) {
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  await page.screenshot({
    path: path.join(evidenceDirectory, `${name}.png`),
    animations: "disabled",
    fullPage: true
  });
}

async function writeRunSummary(name: string, content: string) {
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  fs.writeFileSync(path.join(evidenceDirectory, name), content);
}

async function openProfileFromAddMenu(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible({
    timeout: 20_000
  });
  await page.getByRole("button", { name: "我的", exact: true }).click();
  await expect(page.getByRole("heading", { name: "我的", exact: true })).toBeVisible();
}

test.describe("public profile pixel trial", () => {
  test.beforeEach(async ({ context, page }) => {
    test.setTimeout(480_000);
    page.setDefaultTimeout(20_000);
    await context.tracing.start({ screenshots: true, snapshots: true });
  });

  test.afterEach(async ({ context }, testInfo) => {
    fs.mkdirSync(evidenceDirectory, { recursive: true });
    await context.tracing.stop({
      path: path.join(
        evidenceDirectory,
        `${testInfo.title.replaceAll(/[^a-z0-9]+/gi, "-").toLowerCase()}.zip`
      )
    });
  });

  test("opens the current profile photo and pixel-gallery entry", async ({ page }) => {
    await openProfileFromAddMenu(page);

    await expect(page.getByRole("region", { name: "个人数字资产概览" })).toBeVisible();
    await expect(page.getByText("我的形象照", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "添加形象照" })).toBeVisible();
    await expect(page.getByRole("region", { name: "我的像素小人陈列馆" })).toBeVisible();
    await saveEvidence(page, "01-profile-entry");
  });

  test("adds, selects, and deletes a reusable try-on photo", async ({ page }) => {
    fs.mkdirSync(evidenceDirectory, { recursive: true });
    fs.writeFileSync(invalidFixture, "not an image");

    await openProfileFromAddMenu(page);
    const initialAssetCount = await page.locator(".profile__asset-count").innerText();
    await saveEvidence(page, "02-before-upload");

    await page.getByRole("button", { name: "添加形象照" }).click();
    await expect(page.getByRole("heading", { name: "形象照管理" })).toBeVisible();

    const invalidChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "＋ 上传" }).click();
    const invalidChooser = await invalidChooserPromise;
    await invalidChooser.setFiles(invalidFixture);
    await expect(page.getByText("请选择 JPG、PNG、WebP 或 HEIC 图片")).toBeVisible();
    await saveEvidence(page, "03-invalid-upload-failure");

    const chooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "＋ 上传" }).click();
    const chooser = await chooserPromise;
    await chooser.setFiles(fullBodyFixture);

    const photo = page.getByRole("button", { name: /第 1 张形象照/ });
    await expect(photo).toBeVisible();
    await photo.click();
    await page.getByRole("button", { name: "设为试穿照" }).click();
    await expect(page.getByText("已设为真人试穿参考照")).toBeVisible();
    await photo.click();
    await page.getByRole("button", { name: "删除所选" }).click();
    await expect(page.getByText("还没有形象照")).toBeVisible();
    await saveEvidence(page, "07-deleted");

    await page.getByRole("button", { name: "‹ 返回" }).click();
    await expect(page.locator(".profile__asset-count")).toHaveText(initialAssetCount);

    await writeRunSummary(
      "profile-pixel-trial-summary.md",
      [
        "# Profile Pixel Trial Public Evidence",
        "",
        `Base URL: ${process.env.STYLECAPTURE_E2E_BASE_URL ?? "Playwright baseURL"}`,
        `Viewport: 390x844`,
        `Fixture: ${path.relative(repositoryRoot, fullBodyFixture)}`,
        "",
        "Observed lifecycle:",
        "- The current profile opens reusable try-on photo management.",
        "- Invalid non-image upload shows a recoverable validation failure.",
        "- A valid full-body photo can be selected as the try-on reference.",
        "- Deleting the photo leaves wardrobe item and Look counts unchanged."
      ].join("\n")
    );
  });
});
