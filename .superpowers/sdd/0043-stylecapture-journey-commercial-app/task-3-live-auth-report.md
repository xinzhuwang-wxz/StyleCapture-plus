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
- Live authenticate, refresh, delete, error mapping, Keychain composition, and AuthenticationServices UI remain deliberately out of scope.
