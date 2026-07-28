# Task 3 Product Auth Calls RED Report

## Added RED behaviors

1. `testAuthenticateWithApplePostsCredentialThroughGeneratedClientAndMapsTokens`
   - Fails until `ProductAuthAPI` can be initialized with generated `StyleCaptureAPI.Client`.
   - Fails until `authenticate(_:)` calls generated `authenticateWithAppleV1AuthApplePost`, sends `POST /v1/auth/apple`, preserves the Apple credential JSON body, decodes generated `AuthTokenResponse`, and maps it to `AuthTokens`.

2. `testRefreshPostsRefreshTokenThroughGeneratedClientAndMapsTokens`
   - Fails until `refresh(refreshToken:)` calls generated `refreshSessionV1AuthRefreshPost`, sends `POST /v1/auth/refresh`, preserves `refresh_token`, decodes generated `AuthTokenResponse`, and maps it to `AuthTokens`.

3. `testDeleteAccountPostsExactlyOneBearerHeaderAndOnlyAcceptedSucceeds`
   - Fails until `deleteAccount(accessToken:)` calls generated `deleteAccountV1AccountDeletePost` with `POST /v1/account/delete`.
   - Fails until the adapter composes exactly one `Authorization: Bearer <token>` header through official middleware/client transport.
   - Fails until only generated `202 accepted` is treated as success and other generated success-looking statuses map to `.unexpectedResponse`.

4. `testAuthenticateMapsAppleCredentialFailuresByBackendCode`
   - Fails until Apple credential and identity failures map by `ErrorEnvelope.error.code`, not by status alone.
   - Covers `apple_identity_invalid`, `apple_authorization_failed`, and `apple_nonce_invalid` 401 responses as `.invalidCredential`.
   - Covers `request_invalid` 422 as `.invalidRequest`.
   - Covers `authorization_code_replayed` and `account_binding_conflict` 409 responses as `.conflict`.
   - Covers `apple_identity_unavailable` and `apple_authorization_unavailable` 503 responses as `.serverUnavailable`.
   - Covers documented unexpected 404 and undocumented 418 responses as `.unexpectedResponse`.

5. `testRefreshMapsSessionFailuresByBackendCode`
   - Fails until refresh maps invalid request, expired session, reused refresh token, and unavailable responses independently from Apple-auth credential semantics.
   - Covers `request_invalid` 400/422 as `.invalidRequest`.
   - Covers `session_invalid` and `refresh_token_expired` 401 as `.sessionExpired`.
   - Covers `refresh_token_reused` 409 as `.conflict`.
   - Covers `processing_dispatch_unavailable` 503 as `.serverUnavailable`.

6. `testDeleteAccountMapsSessionFailuresByBackendCode`
   - Fails until delete maps invalid request, invalid session, conflict, and unavailable responses independently from Apple-auth credential semantics.
   - Covers `request_invalid` 400/422 as `.invalidRequest`.
   - Covers `session_invalid` 401 as `.sessionExpired`.
   - Covers generated 409 as `.conflict` and `processing_dispatch_unavailable` 503 as `.serverUnavailable`.
   - The backend currently has no account-delete-specific 409 code; the fixture uses `account_delete_conflict` to keep the operation-local behavior explicit without reusing Apple-auth conflict codes.

7. `testTransportAndDecodingFailuresMapToTypedProductAuthAPIErrors`
   - Fails until transport throws map to `.transportFailure`.
   - Fails until malformed generated response decoding maps to `.unexpectedResponse` without leaking response bodies or credentials into the public error surface.

## Lightweight inspection

- Used `OpenAPIRuntime.ClientTransport` in tests, not generated `APIProtocol` and not a custom networking stack.
- Generated symbol names were confirmed from a temporary Swift OpenAPI Generator output:
  - `Operations.AuthenticateWithAppleV1AuthApplePost.id`
  - `Operations.RefreshSessionV1AuthRefreshPost.id`
  - `Operations.DeleteAccountV1AccountDeletePost.id`
  - `Client.authenticateWithAppleV1AuthApplePost(_:)`
  - `Client.refreshSessionV1AuthRefreshPost(_:)`
  - `Client.deleteAccountV1AccountDeletePost(_:)`
- Existing middleware and mapping tests remain in place.

## Expected RED symbols

- `ProductAuthAPI(client:)`
- `ProductAuthAPI.authenticate(_:)`
- `ProductAuthAPI.refresh(refreshToken:)`
- `ProductAuthAPI.deleteAccount(accessToken:)`
- `ProductAuthAPI.APIError`
- `ProductAuthAPI.APIError.invalidCredential`
- `ProductAuthAPI.APIError.invalidRequest`
- `ProductAuthAPI.APIError.sessionExpired`
- `ProductAuthAPI.APIError.conflict`
- `ProductAuthAPI.APIError.serverUnavailable`
- `ProductAuthAPI.APIError.unexpectedResponse`
- `ProductAuthAPI.APIError.transportFailure`
