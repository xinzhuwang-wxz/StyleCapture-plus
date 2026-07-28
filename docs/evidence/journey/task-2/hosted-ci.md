# Task 2 hosted CI evidence

Date: 2026-07-28
Branch: `codex/stylecapture-journey`
Verified HEAD: `055e11a5113a418898b2b308766dbe9d148cf9d9`
Workflow run: `30317565521`
Run URL: `https://github.com/xinzhuwang-wxz/StyleCapture-plus/actions/runs/30317565521`

## Final green run

| Job | Job ID | Result | Duration | Evidence scope |
| --- | --- | --- | --- | --- |
| `product` | `90146355217` | success | 2m49s | Python architecture/behavior, generated API contract, H5/mobile typecheck/test/build, Docker Compose config, backend image build |
| `ios` | `90146355277` | success | 10m24s | XcodeGen 2.46.0 bootstrap, OpenAPI build-plugin input check, Xcode hosted simulator `xcodebuild test`, SwiftPM lock integrity check, privacy manifest presence, boundary check |

The iOS job passed the critical `Test iOS foundation` step and the follow-up `Inspect iOS privacy manifest and boundaries` step on GitHub-hosted `macos-26`.

Local heavy verification was intentionally not run because the laptop was hot. The hosted run is the compile/test authority for this slice.

## Verification range

The green hosted run proves the Task 2 iOS foundation currently:

- generates the Xcode project through the pinned XcodeGen bootstrap;
- resolves exact SwiftPM pins from the committed lock seed;
- compiles the native SwiftUI/TCA app shell;
- compiles the Apple Swift OpenAPI generated client target;
- runs the unit and launch-test scheme on an installed GitHub-hosted iOS simulator;
- executes TCA `TestStore` coverage for app launch, navigation restoration/deep link and cancellable Journey loading;
- executes GRDB migration/outbox round-trip tests;
- executes background/privacy seam tests;
- runs post-build SwiftPM lock byte-integrity checking;
- keeps the privacy manifest present and the existing boundary checker green.

It does not prove real-device behavior, Apple sandbox commerce, TestFlight installability, visual screenshots, production provider behavior, M0 market validity, or App Store readiness.

## Failure-to-green convergence chain

Bulky raw logs are not tracked; the failure chain is recorded by run/job IDs and summarized here. Earlier raw iOS job logs were removed in review-fix round 1 because they were ~20MB of transient CI output and contradicted this evidence policy.

1. `30314994452` / iOS job `90138576607` failed before compile because Xcode rejected the exact-pinned Apple OpenAPI build plugin in non-interactive CI. Fix: allow non-interactive plugin/macro validation bypass only after exact `Package.resolved` seeding and post-resolution byte checking.
2. `30316514572` / iOS job `90143100108` failed in `Test iOS foundation` with:
   - undefined `Dependencies` / `CasePathsCore` linker symbols from app object files in this XcodeGen + Xcode 26 project;
   - invalid `TestStore` dependency override syntax using `} withDependencies: dependencies`.
   Fix: expose exact already-pinned `Dependencies`, `CasePaths`, and `Clocks` products as direct project products for this generated project and wrap the shared dependency override in a valid inline closure.
3. Dependency review approved the project-level link fix but required the debug report to avoid claiming that TCA 1.26.1 generally requires explicit transitive-product linking. The report now scopes the finding to this repo's XcodeGen + Xcode 26 link command.
4. `30317188420` / iOS job `90145170332` advanced past the linker and failed on Swift 6 XCTest actor/autoclosure rules: `await recorder.events()` appeared inside an `XCTAssertEqual` autoclosure. Fix: await the actor value into a local `events` binding before the assertion.
5. `30317565521` passed both `product` and `ios`.

## Quality gate added by this failure chain

- A source-only iOS review cannot be marked clear before a hosted or local Swift compile/test run proves the source compiles.
- After three consecutive hosted iOS failures, further changes require a fresh debugger pass with full-log root-cause mapping before any fix.
- Dependency-boundary fixes that expose package products must receive independent dependency review before being treated as architectural precedent.

## Review-fix round 1 RED / GREEN chain

- RED commit: `2708778b74d9d499ec17dee3068a890462068204`.
- RED run: `30318648806`, URL `https://github.com/xinzhuwang-wxz/StyleCapture-plus/actions/runs/30318648806`.
- Confirmed RED failure: `product` job `90149673962` failed in `Verify Python architecture and behavior` after `scripts/check_ios_privacy_manifest.py` detected that `NavigationSnapshotClient.swift` uses `UserDefaults` while `PrivacyInfo.xcprivacy` lacked `NSPrivacyAccessedAPICategoryUserDefaults` reason `CA92.1`.
- Navigation RED test was committed before the reducer fix, but the first RED action shape used `Result<Void, AppError>` and failed Swift `Equatable` synthesis before behavior execution. The GREEN fix replaces it with an explicit `NavigationPersistenceResponse` enum so the regression is a compile-safe behavior test going forward. The root behavior being guarded remains the old reducer sending `.navigationPersisted` after `try? await navigationSnapshotClient.save(snapshot)`.
- Superseded GREEN attempt: run `30319082666`, URL `https://github.com/xinzhuwang-wxz/StyleCapture-plus/actions/runs/30319082666`, at HEAD `e738da598a2f740630b6a7da1a471cd47f0d4310`.
  - `product` job `90150979893` passed in 3m10s.
  - `ios` job `90150979880` was intentionally cancelled while its monolithic `Test iOS foundation` step was still running. The cancellation was agent-requested after adding a more diagnosable replacement CI split; the log contains `##[error]The operation was canceled.` and no `timed out`, `Testing failed`, or Swift compile error. This run is therefore not counted as a code failure or GREEN proof.
- Final GREEN run: `30319519482`, URL `https://github.com/xinzhuwang-wxz/StyleCapture-plus/actions/runs/30319519482`, at HEAD `045974480dc82d53ddc546a97850b8c6859e5277`.
  - `product` job `90152256536`: success in 3m27s.
  - `ios` job `90152256473`: success in 12m23s.
  - Evidence scope: product checks remained green; iOS passed the split `Resolve iOS package dependencies`, `Verify iOS package graph`, hosted simulator `xcodebuild test`, SwiftPM lock byte check, privacy manifest validator and boundary checks.
- Process correction: after dispatching a GREEN candidate, freeze HEAD and CI workflow until the candidate completes. Run `30319082666` was cancelled before a documented timeout/no-log threshold, so its cancellation is recorded as a process error and not as product evidence.

## Xcode-project SwiftPM evidence policy

This project intentionally has no `Package.swift`; dependencies are declared in XcodeGen `project.yml` and resolved by Xcode. Task 2 therefore uses the following deployment-equivalent evidence instead of `swift package show-dependencies`:

- hosted `xcodebuild -resolvePackageDependencies` on the generated `.xcodeproj`;
- exact top-level package versions and revisions in `apps/ios/StyleCaptureJourney/Config/Package.resolved`;
- generated `project.pbxproj` product-reference checks for TCA, direct Point-Free support packages, GRDB, Nuke and Apple OpenAPI products/plugins;
- post-resolution `scripts/bootstrap_ios.sh --check-package-resolved` byte check.
