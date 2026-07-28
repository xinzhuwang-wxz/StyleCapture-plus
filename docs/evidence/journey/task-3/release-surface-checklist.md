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
- [x] The application privacy manifest declares no tracking or collected-data types and declares `NSPrivacyAccessedAPICategoryUserDefaults` reason `CA92.1` for the app's navigation snapshot use.

## Required authorized-host evidence before distribution

- [ ] Enable Sign in with Apple for the production App ID in the Apple Developer account and regenerate/refresh the matching provisioning profile.
- [ ] Set the authorized `DEVELOPMENT_TEAM` outside the repository or in the release environment; do not commit a personal team identifier.
- [ ] Produce a fresh generic-device Release archive with the intended distribution certificate and provisioning profile.
- [ ] Inspect the signed application entitlements and confirm `com.apple.developer.applesignin` survives code signing.
- [ ] Inspect the archive's merged privacy report and confirm the three dependency manifests and the application manifest are present with the recorded declarations.
- [ ] Confirm `ThirdPartyNotices.txt` is present in the archived `.app` resources.
- [ ] Export and upload the validated archive, wait for TestFlight processing, and record the build number and processing result.
- [ ] Exercise real Sign in with Apple and account deletion on a TestFlight build using an authorized test account.

## Lightweight verification commands

```sh
plutil -lint apps/ios/StyleCaptureJourney/StyleCaptureJourney/Resources/StyleCaptureJourney.entitlements
python3 scripts/check_ios_package_graph.py
python3 scripts/check_ios_privacy_manifest.py
python3 scripts/check_ios_privacy_manifest.py --source-packages .build/ios-task3/SourcePackages
xcodegen dump --spec apps/ios/StyleCaptureJourney/project.yml --type parsed-json
```

`xcodegen generate` plus `python3 scripts/check_ios_package_graph.py --require-generated-project` verifies generated resource and capability references without claiming signing or archive success.
