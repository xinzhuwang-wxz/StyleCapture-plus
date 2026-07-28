# Task 2 iOS CI systematic debug report

Date: 2026-07-28
Worktree: `/Users/bamboo/Githubs/StyleCapture-plus-commercial-app`
Branch: `codex/stylecapture-journey`
CI evidence: GitHub Actions job `90143100108` in run `30316514572`
(`https://github.com/xinzhuwang-wxz/StyleCapture-plus/actions/runs/30316514572/job/90143100108`).
The 6.8 MB raw log was inspected locally and then discarded to avoid committing bulky
transient evidence.

## Phase 1: reproduction and full error reading

Reproduction source is the hosted GitHub Actions iOS job log. Local reproduction with `xcodebuild`, SwiftPM or Simulator was intentionally not run because the laptop was already hot and the project guardrails forbid trading sustained local load for speed.

The run reaches Xcode's `Test iOS foundation` step, resolves packages, compiles many package targets, then fails in two places:

1. App target link failure at CI log lines 21410-21549.
2. Unit test target Swift parse failure at CI log lines 21554-21597.

The unique failing symbols are not app-domain symbols. They are Point-Free support modules that this generated app/test build ended up referencing from local object files:

- `Dependencies.Dependency.wrappedValue.getter`
- `Dependencies.Dependency.init(...)`
- `Dependencies.DependencyKey`
- `Dependencies.TestDependencyKey`
- `Dependencies.DependencyValues.continuousClock`
- `CasePathsCore.AnyCasePath`
- `CasePathsCore.Case`

The test compiler then fails on exactly two source lines:

- `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/AppFeatureTests.swift:68`
- `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/AppFeatureTests.swift:78`

Both lines use:

```swift
} withDependencies: dependencies
```

Swift parses the `TestStore { ... } withDependencies: { ... }` trailing-label form when the dependency override is an inline trailing closure, as shown in the official TCA 1.26.1 README. It does not parse attaching the label to a predeclared closure variable after the reducer trailing closure.

## Phase 2: pattern analysis

### TCA source/API pattern

Official TCA 1.26.1 documentation shows:

```swift
let store = TestStore(initialState: Feature.State()) {
  Feature()
} withDependencies: {
  $0.numberFact.fetch = { "..." }
}
```

The existing tests already use that valid inline form at:

- `StyleCaptureJourneyTests/AppFeatureTests.swift:8-20`
- `StyleCaptureJourneyTests/JourneyFeatureTests.swift:19-23`

The broken form is only the two uses that pass a variable directly after the trailing label.

### XcodeGen/package pattern

`apps/ios/StyleCaptureJourney/project.yml` currently links only these package products into the main app target:

- `ComposableArchitecture`
- `GRDB`
- `Nuke`

The app source imports `ComposableArchitecture`, and TCA 1.26.1's package manifest declares `ComposableArchitecture` depends on `Dependencies`, `CasePaths`, `Clocks` and other Point-Free packages. This report does not claim TCA 1.26.1 generally requires applications to list all of those transitive products explicitly. The current failure is narrower: this repository's XcodeGen-generated Xcode 26 project produced a link command that did not bring in the products needed by this app target's own object files, even though those object files directly referenced `Dependencies` and `CasePathsCore` symbols after macro/property-wrapper expansion.

The generated `StyleCaptureJourney.xcodeproj/project.pbxproj` confirms only `ComposableArchitecture`, `GRDB` and `Nuke` are package product dependencies for `StyleCaptureJourney`. In this generated project, there is no direct `Dependencies`, `CasePaths`, or `Clocks` package product linked into the app/test targets.

`Config/Package.resolved` already pins:

- `swift-case-paths` 1.9.1
- `swift-clocks` 1.1.0
- `swift-dependencies` 1.14.1

So the fix can expose these existing pinned packages as root exact requirements without introducing new unpinned code.

## Root causes

1. In this XcodeGen + Xcode 26 generated project, `project.yml` declares the TCA umbrella product but the resulting link command does not include the exact products needed by app/test object files that directly reference `Dependencies` and `CasePathsCore` symbols. Explicit root products are therefore the smallest fix for this project boundary, not a general TCA rule.
2. `AppFeatureTests.swift` passes a predeclared dependency override closure using invalid trailing-label syntax. TCA supports `withDependencies` as an inline trailing closure; the variable must be wrapped in an inline closure such as `{ dependencies(&$0) }`.

## Minimal fix plan

1. Add exact root package declarations for the already-pinned Point-Free products needed by this generated project's app/test link commands:
   - `swift-dependencies` 1.14.1
   - `swift-case-paths` 1.9.1
   - `swift-clocks` 1.1.0
2. Link direct products in this project:
   - app target: `Dependencies`, `CasePaths`
   - unit test target: `Dependencies`, `CasePaths`, `Clocks`
3. Replace the two invalid `} withDependencies: dependencies` lines with inline closures that call the existing shared override:
   - `} withDependencies: { dependencies(&$0) }`

## Expected verification

Hosted iOS CI should progress past:

- `Ld ... StyleCaptureJourney.debug.dylib`
- `SwiftDriver StyleCaptureJourneyTests`

If CI still fails, read the complete new hosted log before making another change.

## Follow-up CI run 30317188420

Status: failed in iOS job `90145170332`, but with different evidence.

What changed:

- The prior undefined `Dependencies` and `CasePathsCore` linker errors are gone.
- The hosted log shows `CasePaths` and `Clocks` package product frameworks being code signed into the app bundle.
- The app link command for `StyleCaptureJourney.debug.dylib` proceeds past the previous failure point.

New root cause:

- `StyleCaptureJourneyTests/PrivacyAndBackgroundTests.swift:77` calls `await recorder.events()` as the first argument of `XCTAssertEqual`.
- XCTest assertion arguments are autoclosures. Swift 6 does not allow `await` inside that synchronous autoclosure, so the compiler reports:
  - `call to actor-isolated instance method 'events()' in a synchronous nonisolated context`
  - `'await' in an autoclosure that does not support concurrency`

Pattern check:

- `rg` found no other `XCT...(... await ...)` pattern in the iOS test targets.
- The same recorder method is only used at this failing assertion.

Minimal fix:

- Read actor-isolated events into a local value before the assertion:

```swift
let events = await recorder.events()
XCTAssertEqual(events, [...])
```
