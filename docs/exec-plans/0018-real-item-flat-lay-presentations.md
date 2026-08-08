# Real Item Flat-Lay Presentations ExecPlan

**Goal:** For a newly captured real outfit, let the flat-lay workflow produce one private pure-white 3:4 collage and one private pure-white 3:4 image for every resolved Item, without replacing source or existing display assets.

## Observable outcome

1. The Skill requests the existing `collage` render for the Look, then requests one `flat_lay_item` presentation for each distinct Look component Item.
2. A flat-lay presentation is deterministic Pillow output from that Item's ready `display_object_key`; it never crops the completed collage or invokes an image model.
3. The H5 Item detail requests the private presentation on demand. On success it uses the 3:4 image as the hero and retains an expandable source-image entry; while queued or failed it keeps the existing hero image.
4. A missing ready display asset fails the derived artifact safely and leaves the source and Item facts unchanged.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason |
|---|---|---|---|
| Asynchronous private Item image | `item_presentation` | Adapt | Already owns Item-scoped idempotency, state, storage, and authenticated image access. |
| White 3:4 composition | `PillowLookCollageRenderer` | Direct reuse | A single image already yields a 768×1024 white canvas with contained real-item pixels and shadow. |
| Item source asset | `WardrobeItem.display_object_key` | Direct reuse | It is the existing normalized/segmented real Item display asset; source upload remains untouched. |
| H5 image fallback | `ItemDetail` and `useDisplayImage` | Adapt | Keeps the current source/display preview as the honest fallback and source entry. |

## Verification

- `node --test skills/real-photo-flat-lay-collage/tests/render.test.js`
- `python -m compileall services/backend/src/stylecapture_backend`
- Backend item-presentation HTTP and processing tests, including 768×1024 white-corner output and no provider call.
- H5 typecheck and a mobile Item detail journey: fallback → queued → white 3:4 success → inspect source → failed fallback.

## Decision log

- 2026-08-08: Keep flat-lay images separate from `Item.display_object_key`; displaying them as a successful-detail hero does not mutate the source or display asset.
- 2026-08-08: Render each Item from its own ready display asset rather than cropping the completed collage, preserving image fidelity and making the artifact independently reusable.
