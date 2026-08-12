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
  "docs/evidence/design-merge"
);

const BODY_KEY = "stylecapture:body-profile:v1";
const PHOTO_KEY = "stylecapture:reference-photos:v1";

async function saveEvidence(page: Page, name: string) {
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  await page.screenshot({
    path: path.join(evidenceDirectory, `${name}.png`),
    animations: "disabled",
    fullPage: true
  });
}

function writeFinding(name: string, content: string) {
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  fs.writeFileSync(path.join(evidenceDirectory, name), content);
}

async function openProfile(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const enterWardrobe = page.getByText("进入数字衣橱", { exact: true });
  await expect(enterWardrobe).toBeVisible({ timeout: 20_000 });
  await enterWardrobe.click();
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible({
    timeout: 20_000
  });
  await page.getByRole("button", { name: "添加衣服" }).click();
  const addDialog = page.getByRole("dialog", { name: "添加到 StyleCapture" });
  await expect(addDialog).toBeVisible();
  await addDialog.getByText("试试像素形象").click();
  await expect(
    page.getByRole("heading", { name: "我的 StyleCapture" })
  ).toBeVisible();
}

test("body metrics survive a refresh and a corrupted store", async ({ page }) => {
  await openProfile(page);
  await saveEvidence(page, "01-profile-before-metrics");

  await page.getByRole("button", { name: "编辑资料 ›" }).click();
  const sheet = page.getByLabel("我的个人信息");
  await expect(sheet).toBeVisible();
  await saveEvidence(page, "02-body-metrics-sheet");

  // The wheel is also a spinbutton, so the keyboard path is the one under test —
  // it is what a screen-reader user actually has.
  const height = sheet.getByRole("spinbutton", { name: "身高" });
  await height.focus();
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("ArrowUp");
  const chosenHeight = await height.getAttribute("aria-valuenow");

  await sheet.getByRole("button", { name: "沙漏形" }).click();
  await sheet.getByRole("button", { name: "保存资料" }).click();
  await expect(sheet).toBeHidden();

  const summary = page.getByLabel("身材资料");
  await expect(summary).toContainText(`${chosenHeight} cm`);
  await expect(summary).toContainText("沙漏形");
  await saveEvidence(page, "03-body-metrics-saved");

  // Round trip: it has to still be there after a reload, not just in React state.
  await openProfile(page);
  await expect(page.getByLabel("身材资料")).toContainText(`${chosenHeight} cm`);
  await saveEvidence(page, "04-body-metrics-after-refresh");

  const stored = await page.evaluate(
    (key) => window.localStorage.getItem(key),
    BODY_KEY
  );
  expect(stored).toContain("沙漏形");

  // Failure state: a hand-corrupted store must not break startup. Falling back to
  // defaults is the contract; a white screen is not.
  await page.evaluate((key) => {
    window.localStorage.setItem(key, "{ this is not json");
  }, BODY_KEY);
  await openProfile(page);
  await expect(page.getByLabel("身材资料")).toContainText("补全身材数据");
  await saveEvidence(page, "05-body-metrics-recovered-from-corruption");

  writeFinding(
    "body-metrics.json",
    `${JSON.stringify(
      { chosenHeight, storedIncludesShape: stored?.includes("沙漏形") ?? false },
      null,
      2
    )}\n`
  );
});

test("the photo album refuses a non-image and recovers", async ({ page }) => {
  await openProfile(page);
  await page.getByRole("button", { name: "管理 ›" }).click();
  const sheet = page.getByLabel("形象照管理");
  await expect(sheet).toBeVisible();
  await saveEvidence(page, "06-photo-manager-empty");

  await sheet
    .getByLabel("上传形象照")
    .setInputFiles({
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("这不是图片")
    });
  await expect(sheet.getByRole("alert")).toContainText("图片");
  await saveEvidence(page, "07-photo-rejected-non-image");

  // Recovery: a real image right after the rejection must still go in.
  await sheet.getByLabel("上传形象照").setInputFiles({
    name: "reference.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
      "base64"
    )
  });
  await expect(sheet.getByRole("button", { name: /第 1 张形象照/ })).toBeVisible({
    timeout: 10_000
  });
  await saveEvidence(page, "08-photo-accepted-after-rejection");

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByText("进入数字衣橱", { exact: true })).toBeVisible({
    timeout: 20_000
  });
  const persisted = await page.evaluate(
    (key) => window.localStorage.getItem(key),
    PHOTO_KEY
  );
  expect(persisted).toContain("data:image/");
  await saveEvidence(page, "09-photo-persisted-after-refresh");
});

test("a combo can be built without ever dragging", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const enterWardrobe = page.getByText("进入数字衣橱", { exact: true });
  await expect(enterWardrobe).toBeVisible({ timeout: 20_000 });
  await enterWardrobe.click();
  await page.getByRole("tab", { name: "按单品" }).click();

  const addButtons = page.getByRole("button", { name: /加入组合衣柜/ });
  await expect(addButtons.first()).toBeVisible({ timeout: 20_000 });
  await saveEvidence(page, "10-wardrobe-items-with-combo-buttons");

  await addButtons.nth(0).click();
  const basket = page.getByRole("button", { name: /我的组合衣柜/ });
  await expect(basket).toBeVisible();
  await saveEvidence(page, "11-combo-basket-one-item");

  await addButtons.nth(1).click();
  await saveEvidence(page, "12-combo-basket-two-items");

  writeFinding(
    "combo-basket.md",
    [
      "# 组合衣柜 · 无拖拽路径",
      "",
      "全程只用「加入组合衣柜」按钮，没有触发任何指针拖拽。",
      "拖拽是增强，这条路径证明它不是唯一入口。",
      ""
    ].join("\n")
  );
});

test("the combo refuses a conflicting pairing and saves a valid one", async ({
  page
}) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByText("进入数字衣橱", { exact: true }).click();
  await page.getByRole("tab", { name: "按单品" }).click();

  const addButtons = page.getByRole("button", { name: /加入组合衣柜/ });
  await expect(addButtons.first()).toBeVisible({ timeout: 20_000 });

  // Two dresses at once is the conflict the audit exists to catch. It has to be
  // said out loud, not silently dropped or silently allowed.
  // 点完一件，它的按钮就变成「移出组合衣柜」并退出这个 locator，所以
  // .first() 连点两次拿到的自然是两件不同的连衣裙。衣橱里存在描述完全
  // 相同的单品，按名字选不唯一。
  const dresses = page.getByRole("button", { name: /加入组合衣柜.*连衣裙/ });
  await expect(dresses.first()).toBeVisible({ timeout: 20_000 });
  const dressCount = await dresses.count();
  if (dressCount >= 2) {
    await dresses.first().click();
    await dresses.first().click();
    const audit = page.getByRole("status").filter({ hasText: "连衣裙" });
    await expect(audit.first()).toBeVisible();
    await saveEvidence(page, "13-combo-conflict-reported");

    // Recovery: taking one back out must clear the complaint.
    await page.getByRole("button", { name: /移出组合衣柜.*连衣裙/ }).first().click();
    await expect(page.getByRole("status").filter({ hasText: "连衣裙" })).toHaveCount(
      0
    );
    await saveEvidence(page, "14-combo-conflict-cleared");
  } else {
    writeFinding(
      "combo-conflict-skipped.md",
      `衣橱里只有 ${dressCount} 条连衣裙，凑不出重复品类冲突，这一段没有走到。\n`
    );
  }
});

test("the share sheet offers only what an H5 can actually do", async ({
  page
}) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByText("进入数字衣橱", { exact: true }).click();
  const looks = page.locator(".look-card");
  await expect(looks.first()).toBeVisible({ timeout: 20_000 });
  const lookCount = await looks.count();

  // 分享入口只在这套穿搭有生成好的像素封面时出现，所以要逐套找，
  // 不能点第一套发现没有就当作「跳过」——那种绿是空的。
  let share = null;
  for (let index = 0; index < lookCount; index += 1) {
    await looks.nth(index).click();
    const candidate = page.getByRole("button", { name: "分享像素封面" });
    if (await candidate.isVisible().catch(() => false)) {
      share = candidate;
      break;
    }
    await page.getByRole("button", { name: /返回|‹/ }).first().click();
    await expect(looks.first()).toBeVisible({ timeout: 20_000 });
  }

  if (!share) {
    writeFinding(
      "share-sheet-not-reached.md",
      [
        "# 分享图鉴：本机走查未能触达",
        "",
        `衣橱里 ${lookCount} 套穿搭都没有 share_eligible 的像素封面，`,
        "分享入口按设计不出现，所以这条真机链路没有走到。",
        "",
        "覆盖它的是 tests/share-card-sheet.test.tsx 的 8 个单测。",
        "这不是「验证过」，是「没验证到」，如实记在这里。",
        ""
      ].join("\n")
    );
    test.skip(true, "没有可分享的像素封面，跳过而不是假装走过");
    return;
  }

  await share.click();
  const sheet = page.getByRole("dialog", { name: "分享图鉴" });
  await expect(sheet).toBeVisible();
  await saveEvidence(page, "15-share-sheet");

  await expect(sheet.getByRole("button", { name: "分享到…" })).toBeVisible();
  await expect(sheet.getByText(/一键发/)).toHaveCount(0);
  await expect(sheet.getByText(/不含原始穿搭照片/)).toBeVisible();

  await sheet.getByRole("button", { name: "复制链接看同款" }).click();
  await expect(sheet.getByRole("status")).toContainText(/复制/);
  await saveEvidence(page, "16-share-sheet-link-copied");
});
