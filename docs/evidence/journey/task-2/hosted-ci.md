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

Raw logs were not committed to avoid bulky transient evidence files. The failure chain is recorded by run/job IDs and summarized here.

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
