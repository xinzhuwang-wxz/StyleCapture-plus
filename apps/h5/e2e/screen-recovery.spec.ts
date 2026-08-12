import { expect, test } from "@playwright/test";

test("a failed screen chunk degrades to a retry, not a blank page", async ({
  page
}) => {
  // 真机上遇到过：详情页的分块取不到，整页变白，刷新也没用。
  await page.route("**/LookDetail*", (route) => route.abort());

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "我的衣橱" })).toBeVisible({
    timeout: 20_000
  });
  await page.locator(".look-card").first().click();

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("没能加载出来", { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "重新加载" })).toBeVisible();

  const text = (await page.locator("body").textContent()) ?? "";
  expect(text.trim().length).toBeGreaterThan(10);
});
