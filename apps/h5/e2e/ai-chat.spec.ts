import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const outDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../docs/evidence/ai-chat"
);

async function shot(page: Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: path.join(outDir, `${name}.png`),
    animations: "disabled",
    fullPage: true
  });
}

async function openAI(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /AI/ }).first().click();
  await expect(page.getByText("从真实衣橱开始搭")).toBeVisible({
    timeout: 20_000
  });
}

test("chips fill the box, and the thread stays open for more turns", async ({
  page
}) => {
  await openAI(page);
  await shot(page, "01-ai-entry");

  await page.getByRole("button", { name: /通勤面试/ }).click();
  await page.getByRole("button", { name: "温和" }).click();
  const box = page.getByLabel("穿搭需求");
  await expect(box).toHaveValue(/通勤面试.*温和/);
  await shot(page, "02-chips-filled-the-box");

  await page.getByRole("button", { name: "生成穿搭推荐" }).click();
  await expect(page.getByText(/按你说的挑了/)).toBeVisible({ timeout: 120_000 });
  // 发完要清空，否则说不了下一句。
  await expect(box).toHaveValue("");
  await shot(page, "03-first-answer");

  await box.fill("鞋子换成平底");
  await page.getByRole("button", { name: "生成穿搭推荐" }).click();
  await expect(page.getByText("鞋子换成平底")).toBeVisible({ timeout: 120_000 });
  await shot(page, "04-second-turn");
});

test("the top-right opens the conversation log, not the feed", async ({
  page
}) => {
  await openAI(page);
  await expect(page.getByRole("button", { name: "对话记录 ›" })).toBeVisible();
  // 顶栏在 AI 页不该还是「刷灵感 Feed」。
  await expect(page.getByRole("button", { name: "刷灵感 Feed" })).toHaveCount(0);

  const box = page.getByLabel("穿搭需求");
  await box.fill("周末约会");
  await page.getByRole("button", { name: "生成穿搭推荐" }).click();
  await expect(page.getByText(/按你说的挑了/)).toBeVisible({ timeout: 120_000 });

  await page.getByRole("button", { name: "对话记录 ›" }).click();
  const log = page.getByLabel("对话记录");
  await expect(log).toBeVisible();
  await expect(log.getByText("周末约会")).toBeVisible();
  await shot(page, "05-conversation-log");

  // 刷新后仍在：它存在本机，不是这次渲染的产物。
  await page.reload({ waitUntil: "domcontentloaded" });
  await openAI(page);
  await page.getByRole("button", { name: "对话记录 ›" }).click();
  await expect(page.getByLabel("对话记录").getByText("周末约会")).toBeVisible();
  await shot(page, "06-log-survives-refresh");
});
