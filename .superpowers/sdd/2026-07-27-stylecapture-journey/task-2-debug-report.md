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

The unique failing symbols are not app-domain symbols. They are TCA transitive modules referenced by macro/property-wrapper expansion:

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

The app source imports `ComposableArchitecture`, and TCA 1.26.1's package manifest declares `ComposableArchitecture` depends on `Dependencies`, `CasePaths`, `Clocks` and other Point-Free packages. But the app target's own object files contain references to `Dependencies` and `CasePathsCore` because `@Dependency`, `@Reducer`, `@ObservableState`, `Scope(state:action:)` and reducer case-path generation expand in the app target, not inside the TCA library binary.

The generated `StyleCaptureJourney.xcodeproj/project.pbxproj` confirms only `ComposableArchitecture`, `GRDB` and `Nuke` are package product dependencies for `StyleCaptureJourney`. There is no direct `Dependencies`, `CasePaths`, or `Clocks` package product linked into the app/test targets.

`Config/Package.resolved` already pins:

- `swift-case-paths` 1.9.1
- `swift-clocks` 1.1.0
- `swift-dependencies` 1.14.1

So the fix can expose these existing pinned packages as root exact requirements without introducing new unpinned code.

## Root causes

1. `project.yml` declares TCA as a direct product but omits TCA transitive products that the app/test target object files reference after macro/property-wrapper expansion. This causes the hosted linker's undefined `Dependencies` and `CasePathsCore` symbols.
2. `AppFeatureTests.swift` passes a predeclared dependency override closure using invalid trailing-label syntax. TCA supports `withDependencies` as an inline trailing closure; the variable must be wrapped in an inline closure such as `{ dependencies(&$0) }`.

## Minimal fix plan

1. Add exact root package declarations for the already-pinned Point-Free products needed by app/test object files:
   - `swift-dependencies` 1.14.1
   - `swift-case-paths` 1.9.1
   - `swift-clocks` 1.1.0
2. Link direct products:
   - app target: `Dependencies`, `CasePaths`
   - unit test target: `Dependencies`, `CasePaths`, `Clocks`
3. Replace the two invalid `} withDependencies: dependencies` lines with inline closures that call the existing shared override:
   - `} withDependencies: { dependencies(&$0) }`

## Expected verification

Hosted iOS CI should progress past:

- `Ld ... StyleCaptureJourney.debug.dylib`
- `SwiftDriver StyleCaptureJourneyTests`

If CI still fails, read the complete new hosted log before making another change.
