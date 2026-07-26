# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: upload-to-wardrobe.spec.ts >> uploads a real garment, normalizes its display image, and preserves the asset after source deletion
- Location: e2e/upload-to-wardrobe.spec.ts:106:1

# Error details

```
Error: page.goto: net::ERR_CONNECTION_RESET at https://119.45.216.38/
Call log:
  - navigating to "https://119.45.216.38/", waiting until "domcontentloaded"

```

# Test source

```ts
  1   | import { expect, test } from "@playwright/test";
  2   | import fs from "node:fs";
  3   | import path from "node:path";
  4   | import { fileURLToPath } from "node:url";
  5   | 
  6   | const testDirectory = path.dirname(fileURLToPath(import.meta.url));
  7   | const repositoryRoot = path.resolve(testDirectory, "../../..");
  8   | const evidenceDirectory = path.join(repositoryRoot, "docs/evidence/issue-6/upload");
  9   | const jpegFixture = path.join(
  10  |   testDirectory,
  11  |   "fixtures",
  12  |   "single-sweater-pexels-12944791.jpg"
  13  | );
  14  | const heicFixture = path.join(testDirectory, "fixtures", "single-garment.heic");
  15  | const uploadFixture = fs.existsSync(heicFixture) ? heicFixture : jpegFixture;
  16  | 
  17  | async function saveEvidence(page: import("@playwright/test").Page, name: string) {
  18  |   fs.mkdirSync(evidenceDirectory, { recursive: true });
  19  |   await page.screenshot({
  20  |     path: path.join(evidenceDirectory, `${name}.png`),
  21  |     animations: "disabled",
  22  |     fullPage: true
  23  |   });
  24  | }
  25  | 
  26  | async function enterWardrobeFromCurrentFeed(page: import("@playwright/test").Page) {
  27  |   await expect(page.locator('[aria-label="穿搭灵感 Feed"]')).toBeVisible({
  28  |     timeout: 20_000
  29  |   });
  30  |   await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
  31  |   await expect(page.getByRole("heading", { name: "我的数字衣橱" })).toBeVisible({
  32  |     timeout: 20_000
  33  |   });
  34  |   await page.getByRole("tab", { name: "按单品", exact: true }).click();
  35  |   await expect(page.locator(".item-card").first()).toBeVisible({
  36  |     timeout: 20_000
  37  |   });
  38  | }
  39  | 
  40  | async function openWardrobeFromFeed(page: import("@playwright/test").Page) {
> 41  |   await page.goto("/", { waitUntil: "domcontentloaded" });
      |              ^ Error: page.goto: net::ERR_CONNECTION_RESET at https://119.45.216.38/
  42  |   await enterWardrobeFromCurrentFeed(page);
  43  | }
  44  | 
  45  | async function reloadWithRecovery(page: import("@playwright/test").Page) {
  46  |   try {
  47  |     await page.reload({ waitUntil: "domcontentloaded", timeout: 30_000 });
  48  |     return true;
  49  |   } catch {
  50  |     await page.goto("/", { waitUntil: "domcontentloaded", timeout: 30_000 });
  51  |     return false;
  52  |   }
  53  | }
  54  | 
  55  | async function hasTransparentPixels(
  56  |   image: import("@playwright/test").Locator
  57  | ): Promise<boolean> {
  58  |   return image.evaluate((element: HTMLImageElement) => {
  59  |     try {
  60  |       if (!element.complete || element.naturalWidth === 0 || element.naturalHeight === 0) {
  61  |         return false;
  62  |       }
  63  |       const canvas = document.createElement("canvas");
  64  |       canvas.width = element.naturalWidth;
  65  |       canvas.height = element.naturalHeight;
  66  |       const context = canvas.getContext("2d");
  67  |       if (!context) return false;
  68  |       context.drawImage(element, 0, 0);
  69  |       const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
  70  |       for (let index = 3; index < pixels.length; index += 4) {
  71  |         if (pixels[index] < 250) return true;
  72  |       }
  73  |       return false;
  74  |     } catch {
  75  |       return false;
  76  |     }
  77  |   });
  78  | }
  79  | 
  80  | async function openCardNames(page: import("@playwright/test").Page) {
  81  |   return page.locator(".item-card__open").evaluateAll((buttons) =>
  82  |     buttons.map((button) =>
  83  |       (button.getAttribute("aria-label") ?? button.textContent ?? "")
  84  |         .replace(/\s+/g, " ")
  85  |         .trim()
  86  |     )
  87  |   );
  88  | }
  89  | 
  90  | function findAddedCard(
  91  |   before: readonly string[],
  92  |   after: readonly string[]
  93  | ): { index: number; name: string } {
  94  |   const beforeCounts = new Map<string, number>();
  95  |   for (const name of before) {
  96  |     beforeCounts.set(name, (beforeCounts.get(name) ?? 0) + 1);
  97  |   }
  98  |   for (const [index, name] of after.entries()) {
  99  |     const remaining = beforeCounts.get(name) ?? 0;
  100 |     if (remaining === 0) return { index, name };
  101 |     beforeCounts.set(name, remaining - 1);
  102 |   }
  103 |   throw new Error("Uploaded wardrobe card was not found in the refreshed card list");
  104 | }
  105 | 
  106 | test("uploads a real garment, normalizes its display image, and preserves the asset after source deletion", async ({
  107 |   page
  108 | }) => {
  109 |   test.setTimeout(300_000);
  110 |   page.setDefaultTimeout(20_000);
  111 | 
  112 |   fs.mkdirSync(evidenceDirectory, { recursive: true });
  113 |   fs.writeFileSync(
  114 |     path.join(evidenceDirectory, "upload-fixture.json"),
  115 |     JSON.stringify(
  116 |       {
  117 |         fixture: path.basename(uploadFixture),
  118 |         heicFixtureAvailable: fs.existsSync(heicFixture),
  119 |         viewport: { width: 390, height: 844 }
  120 |       },
  121 |       null,
  122 |       2
  123 |     )
  124 |   );
  125 | 
  126 |   await openWardrobeFromFeed(page);
  127 |   await saveEvidence(page, "01-feed-to-wardrobe-items");
  128 | 
  129 |   const existingCount = await page.locator(".item-card").count();
  130 |   const existingCardNames = await openCardNames(page);
  131 | 
  132 |   const chooserPromise = page.waitForEvent("filechooser");
  133 |   await page
  134 |     .getByRole("button", { name: "添加衣服或试试像素形象" })
  135 |     .click();
  136 |   const addDialog = page.getByRole("dialog", { name: "添加到 StyleCapture" });
  137 |   await expect(addDialog).toBeVisible();
  138 |   await saveEvidence(page, "02-add-entry-open");
  139 |   await addDialog.getByText("从相册导入").click();
  140 |   const chooser = await chooserPromise;
  141 |   await chooser.setFiles(uploadFixture);
```