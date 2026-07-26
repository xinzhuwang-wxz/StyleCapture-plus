/**
 * Drops assets the standalone Style Party build never requests.
 *
 * Vite copies all of `public/` verbatim, which would ship the Feed videos and
 * the original illustration cards (the party uses the pre-cut sprites instead).
 * That is ~12 MB of dead weight on a static host.
 */
import { rm, stat } from "node:fs/promises";
import { glob } from "node:fs/promises";

const OUT = new URL("../dist-party/", import.meta.url);
const UNUSED = ["feed", "assets/char-default.png"];

async function size(url) {
  let total = 0;
  for await (const entry of glob("**/*", { cwd: url, withFileTypes: true })) {
    if (entry.isFile()) {
      total += (await stat(new URL(`${entry.parentPath}/${entry.name}`, "file://"))).size;
    }
  }
  return total;
}

const before = await size(OUT);
for (const path of UNUSED) {
  await rm(new URL(path, OUT), { recursive: true, force: true });
}
// The party renders the pre-cut sprites; the source cards are only build input.
for await (const entry of glob("assets/community/pixel-look-*.png", { cwd: OUT })) {
  await rm(new URL(entry, OUT), { force: true });
}
const after = await size(OUT);
console.log(
  `trimmed standalone build: ${(before / 1e6).toFixed(1)} MB -> ${(after / 1e6).toFixed(1)} MB`
);
