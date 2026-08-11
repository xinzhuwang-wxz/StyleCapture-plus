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
  const enterWardrobe = page.getByText("进入数字衣橱", { exact: true });
  await expect(enterWardrobe).toBeVisible({ timeout: 20_000 });
  await enterWardrobe.click();
  await expect(page.getByRole("heading", { name: "我的数字衣橱" })).toBeVisible({
    timeout: 20_000
  });
  await page
    .getByRole("button", { name: "添加衣服或试试像素形象" })
    .click();
  const addDialog = page.getByRole("dialog", { name: "添加到 StyleCapture" });
  await expect(addDialog).toBeVisible();
  await addDialog.getByText("试试像素形象").click();
  await expect(page.getByRole("heading", { name: "我的 StyleCapture" })).toBeVisible();
}

async function wardrobeCounts(page: Page) {
  const stats = page.locator('[aria-label="衣橱统计"]');
  await expect(stats).toBeVisible();
  const values = await stats.locator("b").allTextContents();
  return {
    items: values[0]?.trim() ?? "",
    looks: values[1]?.trim() ?? "",
    pixelAvatars: values[2]?.trim() ?? "",
    processing: values[3]?.trim() ?? ""
  };
}

async function waitForSeededCounts(page: Page) {
  await expect
    .poll(async () => wardrobeCounts(page), { timeout: 30_000 })
    .toMatchObject({ items: "20", looks: "6" });
  return wardrobeCounts(page);
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

  test("opens the profile pixel trial entry from the PR12 add menu", async ({
    page
  }) => {
    await openProfileFromAddMenu(page);

    await expect(page.getByText("只生成像素图，不写入数字衣橱")).toBeVisible();
    await expect(page.getByRole("button", { name: "拍一张全身照" })).toBeVisible();
    await expect(page.getByRole("button", { name: "从相册试试" })).toBeVisible();
    await expect(
      page.getByText("这条链路只用于快速体验“真人照片 → 像素形象”")
    ).toBeVisible();
    await saveEvidence(page, "01-profile-entry");
  });

  test("generates and deletes a pixel trial without adding wardrobe assets", async ({
    page
  }) => {
    fs.mkdirSync(evidenceDirectory, { recursive: true });
    fs.writeFileSync(invalidFixture, "not an image");

    await openProfileFromAddMenu(page);
    const initialCounts = await waitForSeededCounts(page);
    await saveEvidence(page, "02-before-upload");

    const invalidChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "从相册试试" }).click();
    const invalidChooser = await invalidChooserPromise;
    await invalidChooser.setFiles(invalidFixture);
    await expect(page.getByText("请选择 JPG、PNG、WebP 或 HEIC 图片")).toBeVisible();
    expect(await wardrobeCounts(page)).toEqual(initialCounts);
    await saveEvidence(page, "03-invalid-upload-failure");

    const createTrialResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/v1/pixel-trials") &&
        response.request().method() === "POST",
      { timeout: 120_000 }
    );
    const chooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "从相册试试" }).click();
    const chooser = await chooserPromise;
    await chooser.setFiles(fullBodyFixture);

    await expect(page.getByRole("img", { name: "本次上传的全身照预览" })).toBeVisible();
    const createTrialResponse = await createTrialResponsePromise;
    expect(createTrialResponse.status()).toBe(202);
    await expect(page.getByText("生成中", { exact: true })).toBeVisible({
      timeout: 30_000
    });
    await expect(page.getByText("不会加入数字衣橱")).toBeVisible();
    expect(await wardrobeCounts(page)).toMatchObject({
      items: initialCounts.items,
      looks: initialCounts.looks
    });
    await saveEvidence(page, "04-processing");

    await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
    await expect(page.getByRole("heading", { name: "我的数字衣橱" })).toBeVisible();
    await page.getByRole("button", { name: "我的", exact: true }).click();
    await expect(page.getByRole("heading", { name: "我的 StyleCapture" })).toBeVisible();
    await expect(page.locator(".profile__edit")).toContainText(
      /生成中，可以切走页面|已生成，可作为展示形象/
    );
    expect(await wardrobeCounts(page)).toMatchObject({
      items: initialCounts.items,
      looks: initialCounts.looks
    });
    await saveEvidence(page, "05-exit-and-return");

    await expect(page.getByRole("img", { name: "像素形象生成结果" })).toBeVisible({
      timeout: 360_000
    });
    await expect(page.getByText("生成完成")).toBeVisible();
    expect(await wardrobeCounts(page)).toMatchObject({
      items: initialCounts.items,
      looks: initialCounts.looks,
      pixelAvatars: "1",
      processing: "0"
    });
    await saveEvidence(page, "06-success");

    await page.getByRole("button", { name: "删除草稿" }).click();
    await expect(page.getByText("像素形象草稿已删除，衣橱资产没有变化")).toBeVisible();
    await expect(page.getByText("未上传")).toBeVisible();
    expect(await wardrobeCounts(page)).toEqual(initialCounts);
    await saveEvidence(page, "07-deleted");

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
        "- PR12 add menu opens the profile pixel trial entry.",
        "- Invalid non-image upload shows a recoverable validation failure.",
        "- Valid full-body upload enters processing and survives leaving the page.",
        "- Generated pixel result appears without changing item/look counts.",
        "- Deleting the draft resets pixel avatar state without changing wardrobe assets."
      ].join("\n")
    );
  });
});
