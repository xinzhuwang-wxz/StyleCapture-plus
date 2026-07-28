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
