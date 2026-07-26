# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: feed-whole-outfit.spec.ts >> Issue 6 public Feed lasso >> saves a whole outfit by right swipe and opens the recovered look in wardrobe
- Location: e2e/feed-whole-outfit.spec.ts:207:3

# Error details

```
Error: expect(locator).not.toContainText(expected) failed

Locator: locator('.look-card').first()
Expected substring: not "正在拆解"
Received string: "正在拆解生成中Feed 穿搭灵感原始穿搭已保存，AI 在后台理解"
Timeout: 150000ms

Call log:
  - Expect "not toContainText" with timeout 150000ms
  - waiting for locator('.look-card').first()
    303 × locator resolved to <article class="item-card look-card pixel-card wardrobe-card">…</article>
        - unexpected value "正在拆解生成中Feed 穿搭灵感原始穿搭已保存，AI 在后台理解"

```

```yaml
- article:
  - button "像素穿搭封面生成中 正在拆解 生成中 Feed 穿搭灵感 原始穿搭已保存，AI 在后台理解":
    - img "像素穿搭封面生成中"
    - text: 正在拆解 生成中
    - strong: Feed 穿搭灵感
    - text: 原始穿搭已保存，AI 在后台理解
```

# Test source

```ts
  122 |   test.beforeEach(async ({ page }) => {
  123 |     test.setTimeout(240_000);
  124 |     page.setDefaultTimeout(20_000);
  125 |     await page.setViewportSize({ width: 390, height: 844 });
  126 |   });
  127 | 
  128 |   test("shows lasso guides on the first two feed cards and resumes playback after dismissing the overlay", async ({
  129 |     page
  130 |   }) => {
  131 |     await openFeed(page);
  132 |     const firstVideo = page.getByLabel(/的穿搭视频/).first();
  133 |     await expect(firstVideo).toBeVisible();
  134 | 
  135 |     const firstOverlay = await pauseAndOpenOverlay(page);
  136 |     await expect(page.getByRole("status", { name: "沿着衣服边缘画一圈" })).toBeVisible();
  137 |     await saveEvidence(page, "01-first-card-circle-guide");
  138 | 
  139 |     await firstOverlay.click({ position: { x: 12, y: 12 } });
  140 |     await expect(firstOverlay).toHaveCount(0);
  141 |     await expect
  142 |       .poll(() => firstVideo.evaluate((video: HTMLVideoElement) => video.paused))
  143 |       .toBe(false);
  144 | 
  145 |     const feed = page.getByTestId("feed");
  146 |     await feed.evaluate((element) => {
  147 |       element.scrollTo({ top: element.clientHeight, behavior: "auto" });
  148 |     });
  149 |     await expect
  150 |       .poll(() => feed.evaluate((element) => element.scrollTop), {
  151 |         timeout: 10_000
  152 |       })
  153 |       .toBeGreaterThan(0);
  154 |     const secondButton = page.getByRole("button", { name: "暂停并圈选" }).first();
  155 |     await expect(secondButton).toBeEnabled({ timeout: 20_000 });
  156 |     const secondOverlay = await pauseAndOpenOverlay(page);
  157 |     await expect(page.getByRole("status", { name: "沿着衣服边缘画一圈" })).toBeVisible();
  158 |     await saveEvidence(page, "02-second-card-circle-guide");
  159 |     await secondOverlay.click({ position: { x: 12, y: 12 } });
  160 |     await expect(secondOverlay).toHaveCount(0);
  161 |   });
  162 | 
  163 |   test("keeps a completed lasso visible until the user makes a decision and lets left swipe cancel it", async ({
  164 |     page
  165 |   }) => {
  166 |     await openFeed(page);
  167 |     const overlay = await pauseAndOpenOverlay(page);
  168 |     await drawPolygon(page, overlay);
  169 | 
  170 |     const liftedSelection = page.getByRole("group", { name: "已圈选的穿搭主体" });
  171 |     await expect(liftedSelection).toBeVisible({ timeout: 5_000 });
  172 |     await page.waitForTimeout(1_200);
  173 |     await expect(liftedSelection).toBeVisible();
  174 |     await expect(page.getByRole("status", { name: "左划取消，右划加入" })).toBeVisible();
  175 |     await saveEvidence(page, "03-lasso-stays-lit-before-decision");
  176 | 
  177 |     await swipe(liftedSelection, "left");
  178 |     await expect(page.getByRole("application", { name: "圈选穿搭" })).toHaveCount(0);
  179 |     await expect(page.getByText("已存入数字衣橱")).toHaveCount(0);
  180 |   });
  181 | 
  182 |   test("blocks tiny lassos in the browser instead of sending them to the model", async ({
  183 |     page
  184 |   }) => {
  185 |     const feedIngestRequests: string[] = [];
  186 |     page.on("request", (request) => {
  187 |       if (
  188 |         request.method() !== "GET" &&
  189 |         /\/v1\/(feed|wardrobe|captures|looks|items)/.test(new URL(request.url()).pathname)
  190 |       ) {
  191 |         feedIngestRequests.push(`${request.method()} ${new URL(request.url()).pathname}`);
  192 |       }
  193 |     });
  194 | 
  195 |     await openFeed(page);
  196 |     const overlay = await pauseAndOpenOverlay(page);
  197 |     await drawPolygon(page, overlay, 0.06);
  198 | 
  199 |     await expect(page.getByRole("status", { name: "圈选太小" })).toBeVisible({
  200 |       timeout: 5_000
  201 |     });
  202 |     await expect(page.getByRole("group", { name: "已圈选的穿搭主体" })).toHaveCount(0);
  203 |     expect(feedIngestRequests).toEqual([]);
  204 |     await saveEvidence(page, "04-tiny-lasso-blocked-client-side");
  205 |   });
  206 | 
  207 |   test("saves a whole outfit by right swipe and opens the recovered look in wardrobe", async ({
  208 |     page
  209 |   }) => {
  210 |     await openFeed(page);
  211 |     const existingLooks = await openWardrobeAndCountLooks(page);
  212 |     await page.getByRole("button", { name: "刷灵感 Feed", exact: true }).click();
  213 |     await expect(page.getByTestId("feed")).toBeVisible();
  214 | 
  215 |     await saveWholeOutfitBySwipe(page);
  216 |     await saveEvidence(page, "06-right-swipe-saved-toast");
  217 | 
  218 |     const recoveredLooks = await openWardrobeAndCountLooks(page);
  219 |     expect(recoveredLooks).toBeGreaterThan(existingLooks);
  220 |     const savedLook = page.locator(".look-card").first();
  221 |     await expect(savedLook).toContainText("Feed 穿搭灵感");
> 222 |     await expect(savedLook).not.toContainText("正在拆解", { timeout: 150_000 });
      |                                 ^ Error: expect(locator).not.toContainText(expected) failed
  223 |     await expect(savedLook).toContainText(/搭配已解析|已收藏 · 待补全|解析失败/);
  224 |     await savedLook.click();
  225 |     await expect(page.getByText("Feed 穿搭灵感").first()).toBeVisible();
  226 |     await saveEvidence(page, "07-wardrobe-recovered-look");
  227 |   });
  228 | });
  229 | 
```