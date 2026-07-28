# Task 2 Report: iOS Foundation And Generated Contract

Status: hosted macOS verification passing at HEAD `055e11a5113a418898b2b308766dbe9d148cf9d9`.

Local xcodebuild/SwiftPM/Simulator/Docker verification was intentionally not run after the laptop thermal warning. GitHub-hosted macOS is the compile/test authority for this Task 2 slice.

## RED / GREEN Evidence

- Intended RED test added first: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/AppDatabaseTests.swift`.
- Invalid RED attempts: `docs/evidence/journey/task-2/red-app-database-tests.log`, `docs/evidence/journey/task-2/red-app-database-true.log`.
  - Result: xcodebuild stopped during SwiftPM resolution before compiling the test.
  - Failure: `swift-openapi-generator` 1.13.0 disabled default traits on `swift-openapi-runtime` 1.9.0, which declares no traits.
  - Conclusion: not a valid TDD RED; AppDatabase RED/GREEN remains pending.
- Dependency root cause: `docs/evidence/journey/task-2/openapi-runtime-traits-root-cause.txt`.
  - Official manifests show generator 1.13.0 requires runtime from 1.11.0 with `traits: []`.
  - Runtime 1.11.0 introduces `FullFoundation` default trait.
  - Correction applied: runtime exact pin changed to 1.11.0; generator remains 1.13.0; URLSession remains 1.1.0.
- Package resolution after correction: passed and generated `apps/ios/StyleCaptureJourney/Config/Package.resolved`.
- Local simulator execution blocker after correction:
  - `xcrun simctl list runtimes` returns no runtimes.
  - `xcrun simctl list devices available` returns no devices.
  - Targeted xcodebuild and generic `build-for-testing` both stop with `Unable to find a destination... iOS 26.5 is not installed`.
  - Conclusion: no valid RED/GREEN behavior cycle could be executed on this host without installing an iOS simulator runtime; hosted macOS verification later replaced the local device proof for this slice.
- Hosted GREEN proof:
  - Run `30317565521`, URL `https://github.com/xinzhuwang-wxz/StyleCapture-plus/actions/runs/30317565521`.
  - HEAD `055e11a5113a418898b2b308766dbe9d148cf9d9`.
  - `product` job `90146355217`: success in 2m49s.
  - `ios` job `90146355277`: success in 10m24s.
  - Evidence summary: `docs/evidence/journey/task-2/hosted-ci.md`.

## Changed Files

- `apps/ios/StyleCaptureJourney/project.yml` — XcodeGen project, exact SwiftPM packages, shared scheme.
- `apps/ios/StyleCaptureJourney/.gitignore` — ignores generated project/build outputs.
- `apps/ios/StyleCaptureJourney/Config/Package.resolved` — versioned SwiftPM lock generated from corrected exact pins.
- `apps/ios/StyleCaptureJourney/StyleCaptureAPI/GeneratedClientFactory.swift` — compile-probe factory that instantiates generated `Client` with Apple OpenAPI URLSession transport.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/App/*` — TCA app entry, app reducer, SwiftUI shell.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Journey/*` — empty Journey reducer/view and cancellable loading effect.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/*` — API, database, entitlement, photos, background, notification, design-token and logger dependency clients.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Resources/*` — Info.plist, InfoPlist.xcstrings permission localization, privacy manifest and localized Journey strings.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/*` — AppFeature, JourneyFeature, database, privacy/background tests.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourneyUITests/LaunchTests.swift` — empty shell launch assertion.
- `apps/ios/StyleCaptureJourney/OpenAPI/*` — deterministic schema copy and generator config.
- `apps/ios/StyleCaptureJourney/StoreKit/StyleCaptureJourney.storekit` — sandbox Journey pack configuration.
- `apps/ios/StyleCaptureJourney/ci_scripts/ci_post_clone.sh` — Xcode Cloud post-clone project generation gate.
- `scripts/bootstrap_ios.sh` — Xcode/Swift/XcodeGen version gate and project generation.
- `scripts/generate_ios_openapi_client.sh` — OpenAPI build-plugin input check; compile proof remains xcodebuild.
- `scripts/export_openapi.py` — repeatable multi-output `--output` and `--check`.
- `scripts/check_boundaries.py` — iOS source boundary scan.
- `.github/workflows/product-ci.yml` — separate macOS iOS job with throttled xcodebuild flags.
- `docs/exec-plans/0043-stylecapture-journey-commercial-app.md` — Task 2 progress and OpenAPI runtime pin decision.
- `docs/evidence/journey/task-2/*` — local evidence logs.
- `docs/evidence/journey/task-2/hosted-ci.md` — final hosted green CI evidence and failure-to-green convergence chain.

## Dependency Pins

- XcodeGen: 2.46.0.
- TCA: 1.26.1; expected tag commit `ead11e04e5011c437722c1990d22f80d87056978`.
- GRDB: 7.11.1.
- Nuke: 13.0.6.
- Apple Swift OpenAPI Generator: 1.13.0; tag commit `af9a2a1f5dcfb00a278d4bb29c6d75080932e99e`.
- Apple Swift OpenAPI Runtime: 1.11.0.
- Apple Swift OpenAPI URLSession: 1.1.0.

## Commands / Results

- `brew upgrade xcodegen` -> upgraded XcodeGen 2.45.4 to 2.46.0.
- `bash scripts/bootstrap_ios.sh --check` -> passed; evidence `docs/evidence/journey/task-2/bootstrap-check.log`.
- `uv run python scripts/export_openapi.py --output apps/h5/openapi.json --output apps/ios/StyleCaptureJourney/OpenAPI/openapi.json --check` -> passed before fix round 1; after fix round 1 this mode is strictly read-only and fails on missing or stale outputs.
- `bash scripts/generate_ios_openapi_client.sh --check` -> OpenAPI build-plugin inputs passed; this is not generated-client compile evidence. Evidence `docs/evidence/journey/task-2/openapi-client-check.log`.
- `uv run python scripts/check_boundaries.py services/backend/src` -> passed; evidence `docs/evidence/journey/task-2/boundary-check.log`.
- `plutil -lint apps/ios/StyleCaptureJourney/StyleCaptureJourney/Resources/Info.plist apps/ios/StyleCaptureJourney/StyleCaptureJourney/Resources/PrivacyInfo.xcprivacy` -> passed.
- `python3 -m json.tool` on `Localizable.xcstrings`, `InfoPlist.xcstrings`, and StoreKit JSON -> passed.
- `python3 -m py_compile` on touched Python scripts/tests -> passed.
- `python3 scripts/check_boundaries.py services/backend/src` -> passed after fix round 1.
- `git diff --check` -> passed after fix round 1.
- `uv run pytest -q` -> 318 passed; evidence `docs/evidence/journey/task-2/pytest.log`.
- `pnpm test` -> 228 Vitest tests, 5 scene-outfit node tests, 6 Doubao skill tests passed; evidence `docs/evidence/journey/task-2/pnpm-test.log`.
- `uv run ruff check scripts/export_openapi.py scripts/check_boundaries.py` -> passed; evidence `docs/evidence/journey/task-2/ruff-touched-check.log`.
- `uv run ruff format --check scripts/export_openapi.py scripts/check_boundaries.py` -> passed; evidence `docs/evidence/journey/task-2/ruff-touched-format-check.log`.
- `uv run mypy services/backend/src services/backend/tests scripts` -> passed; evidence `docs/evidence/journey/task-2/mypy.log`.
- `git diff --check` -> passed.
- `xcodebuild ... -only-testing:StyleCaptureJourneyTests/AppDatabaseTests test` with `-jobs 2 -parallel-testing-enabled NO` -> package resolution passed after runtime 1.11.0, then failed before compile/test because no simulator destination exists.
- `xcodebuild ... build-for-testing` with `-jobs 2 -parallel-testing-enabled NO` -> failed before compile for the same missing simulator destination.
- `swift package show-dependencies` -> not applicable; no Package.swift in the XcodeGen project. The accepted Xcode-project equivalent is hosted `xcodebuild -resolvePackageDependencies`, exact `Config/Package.resolved` version/revision checks, generated `project.pbxproj` package-product checks and post-resolution lock byte checking.
- `uv run ruff format scripts/journey_validation_metrics.py services/backend/tests/scripts/test_journey_validation_metrics.py` -> 2 pre-existing M0 files reformatted as prerequisite CI cleanup; not Task 2 behavior evidence.
- Hosted GitHub Actions `product-ci` run `30317565521`:
  - `product` job `90146355217` -> success; Python architecture/behavior, generated API contract, H5/mobile typecheck/test/build, Docker Compose config and backend image passed.
  - `ios` job `90146355277` -> success; XcodeGen bootstrap, OpenAPI build-plugin inputs, hosted simulator `xcodebuild test`, SwiftPM lock integrity, privacy manifest inspection and boundary checks passed.

## Fix Round 1 Notes

- `scripts/export_openapi.py --check` is now read-only: missing and differing requested outputs fail without creating directories or overwriting files. Focused tests were added but not executed locally because the resource guardrail forbids pytest runs in this round.
- The generated client compile probe is source-only until xcodebuild runs: `StyleCaptureAPI.GeneratedClientFactory.make(serverURL:)` instantiates the generated `Client` with `URLSessionTransport`, and Core/API calls that factory without exposing generated DTOs.
- Navigation snapshot persistence uses a TCA dependency backed by `UserDefaults` for non-sensitive metadata. Reducer tests now describe relaunch restore against a shared fake persistence store.
- Nuke and MetricKit are isolated in thin Core clients; feature code remains free of those imports.
- Background task seams now expose typed request kinds, typed scheduling/registration failures, and registration/execution/expiration/completion lifecycle hooks without a custom scheduler.
- CI now has `workflow_dispatch` so the iOS compile/test gate can be run on GitHub-hosted macOS rather than this overheated local machine.
- TCA 2.0 audit note: before M2 feature expansion, re-audit TCA 2.0 migration/deprecation guidance and decide whether to stay pinned on 1.26.1 for P0 or upgrade with a dedicated migration slice.
- Review fix round 1 RED commit `2708778b74d9d499ec17dee3068a890462068204` added a failing navigation-persistence test and iOS privacy-manifest validator before implementation. Hosted RED run `30318648806` confirmed the privacy validator fails against the old manifest. The navigation RED was invalid as behavior evidence because `Result<Void, AppError>` blocked `Action: Equatable` synthesis before XCTest could execute; GREEN replaces it with an explicit `NavigationPersistenceResponse` enum.

## Hosted CI Fix Chain

- `30314994452` / iOS job `90138576607`: failed on non-interactive Apple OpenAPI build-plugin trust. CI now skips package plugin/macro validation only under exact lock seeding and post-build lock byte checking.
- `30316514572` / iOS job `90143100108`: failed on this XcodeGen + Xcode 26 project's missing link products for app object-file `Dependencies`/`CasePathsCore` references and two invalid `TestStore` dependency override lines.
- Independent dependency review approved the direct product exposure as this project's minimum fix, while requiring the report to avoid generalizing the rule to all TCA 1.26.1 apps.
- `30317188420` / iOS job `90145170332`: advanced past the linker and failed on Swift 6 XCTest actor/autoclosure rules.
- `30317565521`: passed both product and iOS jobs.

## Pending Verification Beyond Task 2

- Real-device behavior remains pending for later milestones.
- Apple sandbox commerce remains pending for the StoreKit entitlement slice.
- TestFlight installability remains pending.
- Visual screenshots remain pending for the first user-visible milestone that requires screenshot evidence.
- Release archive privacy report remains pending because archive/build cannot proceed on this host.

## Concerns

- Earlier source/static review was too weak: it missed Swift compile failures and therefore should not have been called source-clear.
- New gate: uncompiled Swift is never source-clear. Three or more consecutive hosted failures require fresh debugger + full-log root-cause map before another fix, and dependency boundary fixes require independent dependency review before becoming precedent.
