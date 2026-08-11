# Profile Pixel Trial Public Evidence

Base URL: https://119.45.216.38/
Viewport: 390x844
Fixture: apps/h5/public/feed/posters/pexels-7681932.jpg

Observed lifecycle:
- PR12 add menu opens the profile pixel trial entry.
- Invalid non-image upload shows a recoverable validation failure.
- Valid full-body upload enters processing and survives leaving the page.
- Generated pixel result appears without changing item/look counts.
- Deleting the draft resets pixel avatar state without changing wardrobe assets.
