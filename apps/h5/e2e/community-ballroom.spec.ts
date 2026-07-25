import { expect, test } from "@playwright/test";
import path from "node:path";

const evidence = (name: string) =>
  path.resolve(process.cwd(), `../../docs/evidence/issue-9/${name}`);

test("a mobile user can enter the ballroom, dance, react, inspect a resident, and download a share card", async ({
  page
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "社区" }).click();

  const map = page.getByLabel("像素舞池地图");
  await expect(map).toBeVisible();
  await page.screenshot({ path: evidence("01-community-initial.png"), animations: "disabled" });

  await map.click({ position: { x: 180, y: 180 } });
  await expect(page.getByRole("status")).toHaveText("舞步已解锁，正在舞池发光");
  await page.screenshot({ path: evidence("02-community-dancing.png"), animations: "disabled" });

  await page.getByRole("button", { name: "闪闪" }).click();
  await expect(page.getByRole("status")).toHaveText("发送了 ✦");

  await page.getByRole("button", { name: "查看紫丁香的公开穿搭" }).click();
  await expect(page.getByRole("dialog", { name: "紫丁香的公开穿搭" })).toContainText("场景居民");
  await page.screenshot({ path: evidence("03-community-resident.png"), animations: "disabled" });
  await page.getByRole("button", { name: "关闭紫丁香的公开穿搭" }).click();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "生成分享卡" }).click();
  const shareCard = await download;
  expect(shareCard.suggestedFilename()).toBe("stylecapture-pixel-ballroom.png");
  await shareCard.saveAs(evidence("07-community-share-card.png"));
  await expect(page.getByRole("status")).toHaveText("分享卡已准备好");
  await page.screenshot({ path: evidence("04-community-share-ready.png"), animations: "disabled" });
});

test("shows a recoverable share-card failure when browser image export is unavailable", async ({ page }) => {
  await page.addInitScript(() => {
    let attempts = 0;
    HTMLCanvasElement.prototype.toDataURL = () => {
      attempts += 1;
      if (attempts === 1) throw new Error("export unavailable");
      return "data:image/png;base64,recovered";
    };
  });
  await page.goto("/");
  await page.getByRole("button", { name: "社区" }).click();
  await page.getByRole("button", { name: "生成分享卡" }).click();

  await expect(page.getByRole("status")).toHaveText("分享卡生成失败，请重试");
  await expect(page.getByRole("button", { name: "重试生成分享卡" })).toBeVisible();
  await page.screenshot({ path: evidence("05-community-share-failure.png"), animations: "disabled" });

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "重试生成分享卡" }).click();
  await download;
  await expect(page.getByRole("status")).toHaveText("分享卡已准备好");
  await page.screenshot({ path: evidence("06-community-share-recovered.png"), animations: "disabled" });
});
