# Task 3 iOS Release-Surface Checklist

This checklist separates repository-verifiable release configuration from Apple-account and signed-distribution evidence. It does not claim that an archive was signed, exported, uploaded, or processed by TestFlight.

## Repository-verifiable evidence

- [x] `StyleCaptureJourney.entitlements` declares `com.apple.developer.applesignin = [Default]`.
- [x] `project.yml` sets `CODE_SIGN_ENTITLEMENTS` and the `com.apple.SignInWithApple` target `SystemCapabilities` flag while leaving `CODE_SIGN_STYLE: Automatic` and the development team unspecified. XcodeGen 2.46.0 serializes a nested target attribute as a string, so its post-generation hook runs the narrow `patch_ios_system_capabilities.py` normalizer; the generated-project validator rejects the stringified form.
- [x] `scripts/check_ios_package_graph.py` enforces exact equality for all 25 identities, versions, and revisions in `Config/Package.resolved`, including transitive pins. The direct package requirements remain exact, including `swift-composable-architecture` `1.26.1`.
- [x] The application target explicitly links the exact-pinned `swift-http-types` `HTTPTypes` product. This preserves the `HTTPResponse` equality symbol used when `ProductAuthAPI` inspects `OpenAPIRuntime.ClientError.response` in hosted linking.
- [x] The generated-project check requires the entitlement, SIWA capability, and bundled `ThirdPartyNotices.txt` references.
- [x] `ThirdPartyNotices.txt` is under the application target's `Resources` directory and records all 25 exact pins plus the applicable MIT, Apache-2.0, and Swift Runtime Library Exception terms.
- [x] The audited source-package cache contains privacy manifests for GRDB, swift-composable-architecture, and swift-sharing. `scripts/check_ios_privacy_manifest.py --source-packages .build/ios-task3/SourcePackages` validates their paths and required-reason declarations.
- [x] The application privacy manifest declares no tracking, declares linked non-tracking `NSPrivacyCollectedDataTypeUserID` for `NSPrivacyCollectedDataTypePurposeAppFunctionality` to cover Sign in with Apple/backend account subject alignment, and declares no app-owned accessed API categories. The app no longer declares `NSPrivacyAccessedAPICategoryUserDefaults` reason `CA92.1` because application Swift sources no longer directly use `UserDefaults`.

## Auth release-surface reuse decisions

| Surface | Current repository evidence | Official source | Reuse decision |
| --- | --- | --- | --- |
| Sign in with Apple button | `AppleSignInTriggerButton` is a thin SwiftUI `UIViewRepresentable` wrapper around `ASAuthorizationAppleIDButton(type: .signIn, style: .black)`. It wires accessibility values and a tap target only; it does not redraw or reimplement the Apple button. | <https://developer.apple.com/documentation/authenticationservices/asauthorizationappleidbutton> and <https://developer.apple.com/documentation/signinwithapple/displaying-sign-in-with-apple-buttons-in-your-app> | Direct Apple framework reuse with a feature-local wrapper for SwiftUI/TCA event routing. |
| Auth orchestration | `AuthFeature` owns restore, sign-in, refresh, logout, deletion confirmation, local cleanup, credential-state checks, and cancellation through TCA state, dependencies, effects, and cancellation IDs. | TCA exact pin remains `swift-composable-architecture` `1.26.1` / `ead11e04e5011c437722c1990d22f80d87056978` under MIT as recorded in the Task 2 package audit. Versioned source: <https://github.com/pointfreeco/swift-composable-architecture/tree/1.26.1>. | Direct reuse of the pinned TCA app-shell pattern; no parallel ViewModel, app router, DI container, or effect runner is introduced. |
| Navigation restoration | `AppFeature.State` holds `@Shared var navigationSnapshot`, initialized with `Shared(wrappedValue: NavigationSnapshot(), .fileStorage(.styleCaptureNavigationSnapshot))`. `NavigationSnapshot` is a pure `Codable` value, and `AppFeature` applies/restores selected tab and deep-linked Journey ID in reducer actions. The old `NavigationSnapshotClient`, app-owned `UserDefaults` store, persistence effect, and persistence status are removed. | Point-Free TCA sharing-state docs source for `1.26.1`: <https://github.com/pointfreeco/swift-composable-architecture/blob/1.26.1/Sources/ComposableArchitecture/Documentation.docc/Articles/SharingState.md>. Local package pin: `swift-composable-architecture` `1.26.1` / `ead11e04e5011c437722c1990d22f80d87056978`. | Direct TCA Sharing file-storage reuse. Do not invent `StackState` for the current shell because there is no pushed navigation stack yet. |
| Duplicate session abstraction | The duplicate `Core/Auth/AuthSession.swift` abstraction has been deleted. Its token persistence, refresh, logout, and deletion responsibilities now remain behind `AuthClient` and `ProductAuthAPI` boundaries used by TCA. | Repository-local reuse decision; no Apple source applies. | Delete and consolidate instead of maintaining a second auth session owner. |
| Credential revocation | `AppleCredentialStateDependency` calls `ASAuthorizationAppleIDProvider.getCredentialState(forUserID:completion:)` and bridges `ASAuthorizationAppleIDProvider.credentialRevokedNotification` through `NotificationCenter.notifications(named:)` as an async sequence. | <https://developer.apple.com/documentation/authenticationservices/asauthorizationappleidprovider/getcredentialstate(foruserid:completion:)>, <https://developer.apple.com/documentation/authenticationservices/asauthorizationappleidprovider/credentialrevokednotification>, and <https://developer.apple.com/documentation/foundation/notificationcenter/notifications> | Direct Apple/Foundation reuse; no custom observer registry or polling loop. |
| Deletion retry and restart | `KeychainTokenStore` keeps the normal token item separate from a secret-free deletion-intent marker. `AuthClient` reuses one stored idempotency key, retains credentials only while retry authentication is possible, removes them after accepted processing, and restores into typed reconciliation/cleanup state instead of the authenticated shell. | Apple Keychain Services plus the generated Product API/TCA dependency boundaries already selected above. | Adapted reuse at the application boundary; no custom credential database, request scheduler or second auth state owner. |
| Privacy manifest user identifier | `PrivacyInfo.xcprivacy` declares linked, non-tracking `NSPrivacyCollectedDataTypeUserID` for app functionality because Sign in with Apple and backend sessions align to an account subject. | <https://developer.apple.com/documentation/bundleresources/privacy-manifest-files>, <https://developer.apple.com/documentation/bundleresources/describing-data-use-in-privacy-manifests>, and <https://developer.apple.com/app-store/app-privacy-details/> | Declare the data type explicitly; do not claim the app has zero collected data while auth persists an account subject. |
| Required-reason APIs | The application manifest declares no app-owned required-reason API categories. The audited package manifests remain: `swift-composable-architecture/Sources/ComposableArchitecture/Resources/PrivacyInfo.xcprivacy` declares `NSPrivacyAccessedAPICategoryUserDefaults` / `C56D.1`; `swift-sharing/Sources/Sharing/PrivacyInfo.xcprivacy` declares `NSPrivacyAccessedAPICategoryFileTimestamp` / `C617.1` and `NSPrivacyAccessedAPICategoryUserDefaults` / `C56D.1`. | Cached package manifests under `.build/ios-task3/SourcePackages/checkouts` and `scripts/check_ios_privacy_manifest.py --source-packages .build/ios-task3/SourcePackages`. | Keep dependency required-reason API declarations audited in their own manifests; do not re-add app-owned `CA92.1` unless application Swift sources directly use `UserDefaults` again. |

## Required authorized-host evidence before distribution

- [ ] Enable Sign in with Apple for the production App ID in the Apple Developer account and regenerate/refresh the matching provisioning profile.
- [ ] Set the authorized `DEVELOPMENT_TEAM` outside the repository or in the release environment; do not commit a personal team identifier.
- [ ] Produce a fresh generic-device Release archive with the intended distribution certificate and provisioning profile.
- [ ] Inspect the signed application entitlements and confirm `com.apple.developer.applesignin` survives code signing.
- [ ] Inspect the archive's merged privacy report and confirm the three dependency manifests and the application manifest are present with the recorded declarations.
- [ ] Confirm `ThirdPartyNotices.txt` is present in the archived `.app` resources.
- [ ] Export and upload the validated archive, wait for TestFlight processing, and record the build number and processing result.
- [ ] Exercise real Sign in with Apple and account deletion on a TestFlight build using an authorized test account.

## Current verification gaps

- Hosted PostgreSQL execution/migration proof and hosted Xcode compile/test for the current auth surface are pending.
- Fresh local Simulator execution for the current correction is pending; the existing untracked screenshots/video are stale and excluded from evidence.
- No signed archive, exported build, App Store Connect processing result, TestFlight install, real Sign in with Apple account run, or account deletion run has been produced for this surface.
- This checklist does not provide production evidence, M0 market evidence, App Review evidence, or revenue evidence.

## Lightweight verification commands

```sh
plutil -lint apps/ios/StyleCaptureJourney/StyleCaptureJourney/Resources/StyleCaptureJourney.entitlements
python3 scripts/check_ios_package_graph.py
python3 scripts/check_ios_privacy_manifest.py
python3 scripts/check_ios_privacy_manifest.py --source-packages .build/ios-task3/SourcePackages
xcodegen dump --spec apps/ios/StyleCaptureJourney/project.yml --type parsed-json
```

`xcodegen generate` plus `python3 scripts/check_ios_package_graph.py --require-generated-project` verifies generated resource and capability references without claiming signing or archive success.
