# Feed Capture Pipeline Recovery

## User outcome

After a user right-swipes a selected Feed frame, the capture is durably accepted, its processing state is immediately visible in the wardrobe, and the latest API/worker code owns the asynchronous pipeline. Real AI processing must fail honestly when the hosted-provider credential is absent and resume once that server-only credential is configured.

## Progress

- [x] Trace the browser submit, Product API, database job, worker dispatch, and LiteLLM boundary.
- [x] Confirm the reported swipe reached the backend and identify its trace/job evidence.
- [x] Identify the active-runtime drift and provider-credential failure.
- [x] Add a behavior-first regression test for a Feed item capture becoming visible on wardrobe entry.
- [x] Implement the minimum wardrobe-view handoff for newly accepted Feed item captures.
- [x] Run targeted frontend verification and operate the mobile journey in the in-app browser.
- [x] Recreate the local API/worker from the latest checkout without losing named-volume data.
- [x] Record the credential-gated real-provider smoke result.

## Surprises & discoveries

- The right swipe did reach Celery as job `243f1d35-...`; the task retried and ended as `vision_unavailable`.
- The running API/worker were created from a July checkout, not the current August checkout. The worker registered only `stylecapture.capture.process`, so newer presentation/render tasks were unavailable.
- LiteLLM rejected the vision request because no provider API key was configured. Host variables and both candidate `.env` files are empty/missing.
- A Feed capture without `look_id` is an Item capture. The UI stores it in `pending`, but the wardrobe opens on the Looks view whenever any older Look exists, hiding the processing Item card behind the Items tab.

## Decision log

- Treat runtime freshness, provider credentials, and UI visibility as separate checks. A successful enqueue is not a successful AI pipeline.
- Preserve the product rule that Feed saving never waits for AI. Carry only a one-time preferred wardrobe view after a newly accepted Item capture; do not merge Item cards into the Looks collection.
- Do not add a mock or deterministic AI success path. Missing hosted-provider credentials remain an explicit, truthful processing failure.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source/license |
|---|---|---|---|---|
| Feed acceptance and pending persistence | Existing `FeedVideo`, `App`, `PendingItemCard`, React Query invalidation | Direct reuse | Submission and polling already exist; only navigation/view intent is missing | This repository, current branch, project license |
| Wardrobe view selection | Existing `WardrobeScreen` tab state | Adapted reuse | Make the existing view state controllable from the owning application instead of adding another list or route | This repository, current branch, project license |
| Async processing | Existing Product API, Celery worker, LiteLLM gateway | Direct reuse | Runtime is stale; no new backend pipeline is needed for the first-step defect | This repository, current branch, project license |

## Verification evidence

- `tests/app.test.tsx`: 28/28 passed, including the new Feed Item -> Items view regression.
- `tsc -b --noEmit`: passed.
- Product API: `GET http://127.0.0.1:8002/healthz` returned `{"status":"ok"}` after the current checkout was mounted into the recreated API/worker containers.
- Celery registered `stylecapture.capture.process`, `stylecapture.item_presentation.process`, `stylecapture.pixel_trial.process`, and `stylecapture.render.process`.
- Browser, whole outfit: the count changed from 12 to 13 and the new first card showed `待补全` / `穿搭已保存 · 正在整理`. Trace `d399dfea-a7c5-47e9-8448-02f9a286ea77` reached the current worker and failed honestly as `grounding_unavailable` because the hosted-provider credential is absent.
- Browser, Item: after save, wardrobe opened with `按单品` selected instead of hiding the result behind `按穿搭`. Trace `5178e729-f793-4e3c-ab41-39251df3584b` reached the current worker and failed honestly as `vision_unavailable` for the same credential reason.
- Host checks found no non-empty `STYLECAPTURE_AI_API_KEY`, `ARK_API_KEY`, or `OPENAI_API_KEY`; no `.env` exists in either the current or stale checkout. No mock fallback was introduced.
