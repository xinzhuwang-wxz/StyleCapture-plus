# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: feed-whole-outfit.spec.ts >> Issue 6 public Feed lasso >> saves a whole outfit by right swipe and opens the recovered look in wardrobe
- Location: e2e/feed-whole-outfit.spec.ts:206:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('已存入数字衣橱')
Expected: visible
Timeout: 30000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 30000ms
  - waiting for getByText('已存入数字衣橱')

```

```yaml
- main:
  - region "穿搭灵感":
    - text: STYLECAPTURE
    - strong: 穿搭灵感
    - button "数字衣橱": 进入数字衣橱
    - article "cottonbro studio 的穿搭":
      - strong: "@cottonbro studio"
      - paragraph: 暂停画面，圈住想带进衣橱的单品或整套穿搭
      - link "pexels · Pexels License":
        - /url: https://www.pexels.com/video/fashion-model-walking-in-the-runway-9512048/
      - button "暂停并圈选" [disabled]: 圈选
      - status: 正在安全存入衣橱…
```

# Test source

```ts
  17  |     fullPage: true
  18  |   });
  19  | }
  20  | 
  21  | async function openFeed(page: Page) {
  22  |   await page.goto("/", { waitUntil: "domcontentloaded" });
  23  |   await expect(page.getByTestId("feed")).toBeVisible({
  24  |     timeout: 30_000
  25  |   });
  26  |   await expect(page.getByRole("button", { name: "暂停并圈选" }).first()).toBeEnabled({
  27  |     timeout: 75_000
  28  |   });
  29  | }
  30  | 
  31  | async function openWardrobeAndCountLooks(page: Page) {
  32  |   const looksLoaded = page.waitForResponse(
  33  |     (response) =>
  34  |       response.request().method() === "GET" &&
  35  |       new URL(response.url()).pathname.endsWith("/v1/looks")
  36  |   );
  37  |   await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
  38  |   await expect(page.getByRole("heading", { name: "我的数字衣橱" })).toBeVisible();
  39  |   await looksLoaded;
  40  |   await expect(page.locator(".wardrobe-loading")).toHaveCount(0);
  41  |   return page.locator(".look-card").count();
  42  | }
  43  | 
  44  | async function pauseAndOpenOverlay(page: Page, index = 0) {
  45  |   const circleButton = page.getByRole("button", { name: "暂停并圈选" }).nth(index);
  46  |   let lastClickError: unknown;
  47  |   for (let attempt = 0; attempt < 4; attempt += 1) {
  48  |     await expect(circleButton).toBeEnabled({ timeout: 30_000 });
  49  |     try {
  50  |       await circleButton.click({ timeout: 8_000 });
  51  |       lastClickError = null;
  52  |       break;
  53  |     } catch (error) {
  54  |       lastClickError = error;
  55  |       await page.waitForTimeout(1_000);
  56  |     }
  57  |   }
  58  |   if (lastClickError) {
  59  |     throw lastClickError;
  60  |   }
  61  |   const overlay = page.getByRole("application", { name: "圈选穿搭" });
  62  |   await expect(overlay).toBeVisible({ timeout: 10_000 });
  63  |   return overlay;
  64  | }
  65  | 
  66  | async function drawPolygon(
  67  |   page: Page,
  68  |   overlay: ReturnType<Page["getByRole"]>,
  69  |   scale = 1
  70  | ) {
  71  |   const box = await overlay.boundingBox();
  72  |   expect(box).not.toBeNull();
  73  |   if (!box) return;
  74  |   const centerX = box.x + box.width * 0.5;
  75  |   const centerY = box.y + box.height * 0.45;
  76  |   const halfWidth = box.width * 0.28 * scale;
  77  |   const halfHeight = box.height * 0.24 * scale;
  78  |   const points = [
  79  |     [centerX - halfWidth, centerY - halfHeight],
  80  |     [centerX + halfWidth, centerY - halfHeight],
  81  |     [centerX + halfWidth, centerY + halfHeight],
  82  |     [centerX - halfWidth, centerY + halfHeight],
  83  |     [centerX - halfWidth, centerY - halfHeight]
  84  |   ] as const;
  85  | 
  86  |   await page.mouse.move(...points[0]);
  87  |   await page.mouse.down();
  88  |   for (const point of points.slice(1)) {
  89  |     await page.mouse.move(...point, { steps: 10 });
  90  |   }
  91  |   await page.mouse.up();
  92  | }
  93  | 
  94  | async function swipe(locator: ReturnType<Page["getByRole"]>, direction: "left" | "right") {
  95  |   const box = await locator.boundingBox();
  96  |   expect(box).not.toBeNull();
  97  |   if (!box) return;
  98  |   const startX = box.x + box.width / 2;
  99  |   const y = box.y + box.height / 2;
  100 |   const endX = startX + (direction === "right" ? 150 : -150);
  101 |   const page = locator.page();
  102 |   await page.mouse.move(startX, y);
  103 |   await page.mouse.down();
  104 |   await page.mouse.move(endX, y, { steps: 12 });
  105 |   await page.mouse.up();
  106 | }
  107 | 
  108 | async function saveWholeOutfitBySwipe(page: Page) {
  109 |   const overlay = await pauseAndOpenOverlay(page);
  110 |   await drawPolygon(page, overlay);
  111 |   const liftedSelection = page.getByRole("group", { name: "已圈选的穿搭主体" });
  112 |   await expect(liftedSelection).toBeVisible({ timeout: 5_000 });
  113 |   await expect(page.getByRole("status", { name: "左划取消，右划加入" })).toBeVisible();
  114 |   await page.getByRole("button", { name: "存整套" }).click();
  115 |   await saveEvidence(page, "05-whole-outfit-selected");
  116 |   await swipe(liftedSelection, "right");
> 117 |   await expect(page.getByText("已存入数字衣橱")).toBeVisible({ timeout: 30_000 });
      |                                           ^ Error: expect(locator).toBeVisible() failed
  118 | }
  119 | 
  120 | test.describe("Issue 6 public Feed lasso", () => {
  121 |   test.beforeEach(async ({ page }) => {
  122 |     test.setTimeout(240_000);
  123 |     page.setDefaultTimeout(20_000);
  124 |     await page.setViewportSize({ width: 390, height: 844 });
  125 |   });
  126 | 
  127 |   test("shows lasso guides on the first two feed cards and resumes playback after dismissing the overlay", async ({
  128 |     page
  129 |   }) => {
  130 |     await openFeed(page);
  131 |     const firstVideo = page.getByLabel(/的穿搭视频/).first();
  132 |     await expect(firstVideo).toBeVisible();
  133 | 
  134 |     const firstOverlay = await pauseAndOpenOverlay(page);
  135 |     await expect(page.getByRole("status", { name: "沿着衣服边缘画一圈" })).toBeVisible();
  136 |     await saveEvidence(page, "01-first-card-circle-guide");
  137 | 
  138 |     await firstOverlay.click({ position: { x: 12, y: 12 } });
  139 |     await expect(firstOverlay).toHaveCount(0);
  140 |     await expect
  141 |       .poll(() => firstVideo.evaluate((video: HTMLVideoElement) => video.paused))
  142 |       .toBe(false);
  143 | 
  144 |     const feed = page.getByTestId("feed");
  145 |     await feed.evaluate((element) => {
  146 |       element.scrollTo({ top: element.clientHeight, behavior: "auto" });
  147 |     });
  148 |     await expect
  149 |       .poll(() => feed.evaluate((element) => element.scrollTop), {
  150 |         timeout: 10_000
  151 |       })
  152 |       .toBeGreaterThan(0);
  153 |     const secondButton = page.getByRole("button", { name: "暂停并圈选" }).first();
  154 |     await expect(secondButton).toBeEnabled({ timeout: 20_000 });
  155 |     const secondOverlay = await pauseAndOpenOverlay(page);
  156 |     await expect(page.getByRole("status", { name: "沿着衣服边缘画一圈" })).toBeVisible();
  157 |     await saveEvidence(page, "02-second-card-circle-guide");
  158 |     await secondOverlay.click({ position: { x: 12, y: 12 } });
  159 |     await expect(secondOverlay).toHaveCount(0);
  160 |   });
  161 | 
  162 |   test("keeps a completed lasso visible until the user makes a decision and lets left swipe cancel it", async ({
  163 |     page
  164 |   }) => {
  165 |     await openFeed(page);
  166 |     const overlay = await pauseAndOpenOverlay(page);
  167 |     await drawPolygon(page, overlay);
  168 | 
  169 |     const liftedSelection = page.getByRole("group", { name: "已圈选的穿搭主体" });
  170 |     await expect(liftedSelection).toBeVisible({ timeout: 5_000 });
  171 |     await page.waitForTimeout(1_200);
  172 |     await expect(liftedSelection).toBeVisible();
  173 |     await expect(page.getByRole("status", { name: "左划取消，右划加入" })).toBeVisible();
  174 |     await saveEvidence(page, "03-lasso-stays-lit-before-decision");
  175 | 
  176 |     await swipe(liftedSelection, "left");
  177 |     await expect(page.getByRole("application", { name: "圈选穿搭" })).toHaveCount(0);
  178 |     await expect(page.getByText("已存入数字衣橱")).toHaveCount(0);
  179 |   });
  180 | 
  181 |   test("blocks tiny lassos in the browser instead of sending them to the model", async ({
  182 |     page
  183 |   }) => {
  184 |     const feedIngestRequests: string[] = [];
  185 |     page.on("request", (request) => {
  186 |       if (
  187 |         request.method() !== "GET" &&
  188 |         /\/v1\/(feed|wardrobe|captures|looks|items)/.test(new URL(request.url()).pathname)
  189 |       ) {
  190 |         feedIngestRequests.push(`${request.method()} ${new URL(request.url()).pathname}`);
  191 |       }
  192 |     });
  193 | 
  194 |     await openFeed(page);
  195 |     const overlay = await pauseAndOpenOverlay(page);
  196 |     await drawPolygon(page, overlay, 0.06);
  197 | 
  198 |     await expect(page.getByRole("status", { name: "圈选太小" })).toBeVisible({
  199 |       timeout: 5_000
  200 |     });
  201 |     await expect(page.getByRole("group", { name: "已圈选的穿搭主体" })).toHaveCount(0);
  202 |     expect(feedIngestRequests).toEqual([]);
  203 |     await saveEvidence(page, "04-tiny-lasso-blocked-client-side");
  204 |   });
  205 | 
  206 |   test("saves a whole outfit by right swipe and opens the recovered look in wardrobe", async ({
  207 |     page
  208 |   }) => {
  209 |     await openFeed(page);
  210 |     const existingLooks = await openWardrobeAndCountLooks(page);
  211 |     await page.getByRole("button", { name: "刷灵感 Feed", exact: true }).click();
  212 |     await expect(page.getByTestId("feed")).toBeVisible();
  213 | 
  214 |     await saveWholeOutfitBySwipe(page);
  215 |     await saveEvidence(page, "06-right-swipe-saved-toast");
  216 | 
  217 |     const recoveredLooks = await openWardrobeAndCountLooks(page);
```