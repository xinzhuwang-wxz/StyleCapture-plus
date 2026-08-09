import { expect, test } from "@playwright/test";

async function openWardrobe(page: import("@playwright/test").Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const enterWardrobe = page.getByText("进入数字衣橱", { exact: true });
  if (await enterWardrobe.isVisible().catch(() => false)) {
    await enterWardrobe.click();
  }
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible({
    timeout: 20_000
  });
}

test("previews Look and Item deletion without deleting seeded data", async ({
  page
}) => {
  test.setTimeout(60_000);
  await openWardrobe(page);

  await page.locator(".look-card .item-card__open").first().click();
  const lookDetail = page.getByRole("dialog", { name: "穿搭详情" });
  await expect(lookDetail).toBeVisible();
  await lookDetail.getByRole("button", { name: "删除穿搭" }).click();

  const lookDelete = page.getByRole("alertdialog", { name: "删除这套穿搭" });
  await expect(lookDelete).toBeVisible();
  await expect(lookDelete.getByText("仅删除此搭配")).toBeVisible();
  await expect(lookDelete.getByText("搭配和单品都删除")).toBeVisible();
  await lookDelete.getByRole("button", { name: /仅删除此搭配/ }).click();
  await expect(
    page.getByRole("alertdialog", { name: "确认仅删除此搭配？" })
  ).toBeVisible();
  await page.getByRole("button", { name: "返回选择" }).click();
  await page.getByRole("button", { name: "取消" }).click();
  await expect(page.getByRole("alertdialog")).toBeHidden();
  await lookDetail.getByRole("button", { name: "返回衣橱" }).click();

  await page.getByRole("tab", { name: "按单品" }).click();
  await page.locator(".item-card .item-card__open").first().click();
  const itemDetail = page.getByRole("dialog", { name: "单品详情" });
  await expect(itemDetail).toBeVisible();
  await itemDetail.getByRole("button", { name: "删除单品" }).click();

  const itemDelete = page.getByRole("alertdialog", {
    name: "确认删除这件单品？"
  });
  await expect(itemDelete).toBeVisible();
  await itemDelete.getByRole("button", { name: "取消" }).click();
  await expect(page.getByRole("alertdialog")).toBeHidden();
});
