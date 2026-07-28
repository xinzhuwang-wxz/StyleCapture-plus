# Task 3 live-auth tracer-bullet report

## Implementation commit

This report is committed with the implementation as the single corrected local commit after the Lore-message repair.

## Changed files

- `apps/ios/StyleCaptureJourney/StyleCaptureAPI/GeneratedClientFactory.swift`
  - Adds `BearerAuthorizationMiddleware`, the official `OpenAPIRuntime.ClientMiddleware` implementation that sets exactly one `Authorization: Bearer <token>` header and forwards the request, body, and base URL.
  - Adds optional middleware injection to the generated-client factory.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/API/ProductAuthAPI.swift`
  - Maps `AppleSignInRequest` to generated `Components.Schemas.AppleAuthBody`.
  - Maps generated `AuthTokenResponse` to domain `AuthTokens`.
  - Owns generated-client calls for Apple authentication, session refresh, and account deletion, including operation-specific generated-error mapping.

## Test intent and failure modes

- `testBearerMiddlewareAddsAuthorizationHeader` fails if bearer formatting changes, the header is omitted, the base URL changes, or the forwarded body bytes differ from the original payload.
- `testAppleRequestMappingPreservesRawCredentialPayload` fails if identity token, authorization code, raw nonce, or optional device name is dropped or renamed at the Core/API boundary.
- `testGeneratedTokenResponseMapsIntoDomainValue` fails if any server-issued token, subject, expiry, or token type is not copied exactly into the domain value.

The tests were introduced as the required hosted RED checkpoint in commit `ed4f17b`; no test assertions were weakened or replaced. Local Xcode/Simulator test execution is intentionally excluded by this slice's resource constraints.

## Commands and results

| Command | Result |
| --- | --- |
| `xcodegen generate --spec apps/ios/StyleCaptureJourney/project.yml` | Passed; regenerated `StyleCaptureJourney.xcodeproj`. |
| `python3 scripts/check_ios_package_graph.py --require-generated-project` | Passed; exact package graph and generated-project references validated. |
| `git diff --check` | Passed; no whitespace errors. |

## Concerns

- Hosted iPhone CI is still required to compile and run `ProductAuthAPITests` against the generated client; no local Xcode or Simulator build was run.
- Keychain composition and AuthenticationServices UI remain deliberately out of scope.

## Generated-client factory boundary correction

The frozen RED originally passed a prebuilt generated `Client` into `ProductAuthAPI`. That client keeps its underlying `UniversalClient` and middleware list private, while the generated account-delete input has no `Authorization` field. The required official per-delete bearer middleware was therefore unrepresentable with that construction.

`ProductAuthAPI` now receives a feature-local generated-client factory. It creates the unauthenticated client with no middleware for Apple authentication and refresh, and creates the deletion client with exactly one `BearerAuthorizationMiddleware`. `ProductAuthAPITests` supplies the server URL and test transport through the factory while preserving the transport-level header assertions. This correction does not introduce handwritten network DTOs, routes, or transport code.

## Hosted decoding-failure correction

Run `30373358421` showed that malformed successful JSON reaches `ProductAuthAPI` as the generated runtime's public `ClientError`, rather than as a bare `DecodingError`. The runtime attaches a non-nil HTTP response when deserialization fails; transport failures have no response. The boundary therefore maps `ClientError` values with a response to `unexpectedResponse` and preserves response-less client errors as `transportFailure`.

## Release-surface auth addendum

This addendum records the current repository state only. It does not claim a production build, M0 market signal, App Review readiness, TestFlight processing, or real Sign in with Apple execution.

### Current source evidence

- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Onboarding/AppleSignInTriggerButton.swift`
  - Reuses Apple's `ASAuthorizationAppleIDButton` directly through a thin SwiftUI `UIViewRepresentable`.
  - Sets `.signIn` and `.black`, applies the design-system corner radius, forwards accessibility values, and sends the TCA tap action.
  - Official references: <https://developer.apple.com/documentation/authenticationservices/asauthorizationappleidbutton> and <https://developer.apple.com/documentation/signinwithapple/displaying-sign-in-with-apple-buttons-in-your-app>.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Onboarding/AuthFeature.swift`
  - Keeps restore, sign-in, refresh, logout, deletion confirmation, local cleanup, credential revocation, and cancellation inside the TCA reducer.
  - Uses dependency clients for auth API/session storage, Apple authorization, nonce generation, credential state, and date.
  - Reuse decision: keep exact-pinned `swift-composable-architecture` `1.26.1` / `ead11e04e5011c437722c1990d22f80d87056978`; do not add a ViewModel, app router, DI container, effect runner, or second navigation owner.
  - Official Point-Free source references: <https://github.com/pointfreeco/swift-composable-architecture/tree/1.26.1> and <https://github.com/pointfreeco/swift-composable-architecture/blob/1.26.1/Sources/ComposableArchitecture/Documentation.docc/Articles/SharingState.md>.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/App/AppFeature.swift` and `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Navigation/NavigationSnapshot.swift`
  - Remove the custom `NavigationSnapshotClient`, app-owned `UserDefaults` navigation store, navigation persistence effect, and navigation persistence status.
  - Initialize `@Shared var navigationSnapshot` with TCA's `Shared(wrappedValue: NavigationSnapshot(), .fileStorage(.styleCaptureNavigationSnapshot))` persistence strategy.
  - Keep `NavigationSnapshot` as a pure `Codable` value and keep restore/deep-link state mutation in the reducer.
  - Do not introduce `StackState` for this shell until a real pushed navigation stack exists.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Auth/AuthSession.swift`
  - Deleted. Its duplicate session responsibilities are consolidated into `AuthClient` plus `ProductAuthAPI` boundaries used by TCA.
  - Reuse decision: remove the feature-local duplicate instead of maintaining two auth-session owners.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Auth/AppleCredentialStateDependency.swift`
  - Reuses `ASAuthorizationAppleIDProvider.getCredentialState(forUserID:completion:)`.
  - Reuses `ASAuthorizationAppleIDProvider.credentialRevokedNotification` and Foundation `NotificationCenter.notifications(named:)` as an async sequence.
  - Official references: <https://developer.apple.com/documentation/authenticationservices/asauthorizationappleidprovider/getcredentialstate(foruserid:completion:)>, <https://developer.apple.com/documentation/authenticationservices/asauthorizationappleidprovider/credentialrevokednotification>, and <https://developer.apple.com/documentation/foundation/notificationcenter/notifications>.
- `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Resources/PrivacyInfo.xcprivacy`
  - Declares `NSPrivacyTracking = false`.
  - Declares linked, non-tracking `NSPrivacyCollectedDataTypeUserID` with `NSPrivacyCollectedDataTypePurposeAppFunctionality` for Sign in with Apple and backend account-subject alignment.
  - Declares no app-owned accessed API categories. The app no longer declares `NSPrivacyAccessedAPICategoryUserDefaults` reason `CA92.1` because application Swift sources no longer directly use `UserDefaults`.
  - Official references: <https://developer.apple.com/documentation/bundleresources/privacy-manifest-files>, <https://developer.apple.com/documentation/bundleresources/describing-data-use-in-privacy-manifests>, and <https://developer.apple.com/app-store/app-privacy-details/>.
- `.build/ios-task3/SourcePackages/checkouts/swift-composable-architecture/Sources/ComposableArchitecture/Resources/PrivacyInfo.xcprivacy`
  - Dependency manifest declares `NSPrivacyAccessedAPICategoryUserDefaults` / `C56D.1` and no tracking or collected-data types.
- `.build/ios-task3/SourcePackages/checkouts/swift-sharing/Sources/Sharing/PrivacyInfo.xcprivacy`
  - Dependency manifest declares `NSPrivacyAccessedAPICategoryFileTimestamp` / `C617.1` and `NSPrivacyAccessedAPICategoryUserDefaults` / `C56D.1`, with no tracking or collected-data types.

### Current verification gaps

- Hosted Xcode compile is pending for this current auth surface.
- Hosted Simulator execution is pending for this current auth surface.
- No signed archive, TestFlight processed build, real Sign in with Apple account run, account deletion run, production run, M0 market evidence, or revenue evidence exists in this addendum.
