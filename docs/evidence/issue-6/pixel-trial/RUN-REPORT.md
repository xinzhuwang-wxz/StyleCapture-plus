# Issue #6 Profile Pixel Trial — final public run

Date: 2026-07-26  
Base URL: `https://119.45.216.38/`  
Viewport: `390x844`  
Result: **passed**

The final run used a real uploaded full-body image and the production image-generation
capability. It verified:

- the PR12 add menu exposes `试试像素形象`;
- an invalid file returns a recoverable Chinese validation message;
- a valid image creates a real asynchronous pixel task;
- leaving and returning preserves the processing state;
- the generated pixel image is decoded and displayed;
- deleting the result removes the trial artifact; and
- item/Look counts do not change, so Try does not silently write to the wardrobe.

Evidence: `01-profile-entry.png` through `07-deleted.png` and the retained Playwright
trace in this directory. No mock, fixed result, or Codex-authored runtime output was
used.
