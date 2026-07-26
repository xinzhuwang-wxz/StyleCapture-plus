import { expect, test } from "@playwright/test";
import path from "node:path";

const evidence = (name: string) =>
  path.resolve(process.cwd(), `../../docs/evidence/issue-9/${name}`);

async function enterPixelWorld(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "数字衣橱" }).click();
  await page.getByRole("button", { name: "像素世界" }).click();
  await expect(
    page.getByLabel("花房夜宴像素世界，点击地面走动，点击角色查看他的 Look")
  ).toBeVisible();
}

test("a mobile user enters from the product nav, changes Look, moves and returns", async ({
  page
}) => {
  await enterPixelWorld(page);

  await expect(page.getByText(/预设角色非真人 · 非实时社区/)).toBeVisible();
  await expect(page.getByRole("button", { name: "换上甜酷工装" })).toBeVisible();
  await expect(page.getByRole("button", { name: "换上灰调长裙" })).toBeVisible();
  await page.screenshot({
    path: evidence("08-product-pixel-world-entry.png"),
    animations: "disabled"
  });

  await page.getByRole("button", { name: "换上薄荷花园" }).click();
  await expect(page.getByRole("status")).toContainText("已换上：薄荷花园");
  await page
    .getByLabel("花房夜宴像素世界，点击地面走动，点击角色查看他的 Look")
    .click({ position: { x: 250, y: 240 } });

  await page.getByRole("button", { name: "上台走秀" }).click();
  await expect(page.getByRole("status")).toContainText("走秀开始");
  await page.screenshot({ path: evidence("09-product-pixel-world-runway.png") });

  await page.getByRole("button", { name: "进入全屏世界" }).click();
  await expect(page.getByRole("button", { name: "退出全屏世界" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  await page.screenshot({ path: evidence("10-product-pixel-world-fullscreen.png") });
  await page.getByRole("button", { name: "退出全屏世界" }).click();

  await page.getByRole("button", { name: "返回数字衣橱" }).click();
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "主要功能" })).toBeVisible();
});

test("a local pixel Look joins the rail and invalid files recover truthfully", async ({
  page
}) => {
  await enterPixelWorld(page);

  await page.getByLabel("上传我的像素 Look").setInputFiles({
    name: "not-a-look.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("invalid")
  });
  await expect(page.getByRole("status")).toContainText(
    "请选择 JPG、PNG、WebP 或 HEIC 图片"
  );

  await page
    .getByLabel("上传我的像素 Look")
    .setInputFiles(path.resolve(process.cwd(), "public/assets/char-default.png"));
  await expect(page.getByRole("status")).toContainText("已加入衣橱");
  const uploaded = page.getByRole("button", { name: "换上char-default.png" });
  await expect(uploaded).toHaveAttribute("aria-pressed", "false");
  await uploaded.click();
  await expect(uploaded).toHaveAttribute("aria-pressed", "true");
});
