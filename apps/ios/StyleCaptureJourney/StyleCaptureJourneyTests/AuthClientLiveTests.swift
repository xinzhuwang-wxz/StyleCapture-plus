import Foundation
import HTTPTypes
import OpenAPIRuntime
import XCTest
@testable import StyleCaptureAPI
@testable import StyleCaptureJourney

final class AuthClientLiveTests: XCTestCase {
    func testLiveClientRestoresPersistsRefreshesAndDeletesThroughProductAuthAPI() async throws {
        let events = EventLog()
        let requests = RecordedProductAuthRequests(events: events)
        let tokenStore = RecordingTokenStore(initial: Self.storedTokens, events: events)
        let authClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: requests),
            tokenStore: tokenStore,
            deviceName: { "iPhone 17" }
        )

        let restored = try await authClient.restore()
        XCTAssertEqual(restored, Self.storedTokens.authenticatedAccount)

        let signedIn = try await authClient.authenticate(
            AppleSignInCredential(
                userIdentifier: "apple-user-1",
                identityToken: "identity-token",
                authorizationCode: "authorization-code"
            ),
            "raw-nonce"
        )
        XCTAssertEqual(signedIn, Self.signedInTokens.authenticatedAccount)
        let storedAfterSignIn = await tokenStore.currentTokens()
        XCTAssertEqual(storedAfterSignIn, Self.signedInTokens)

        let refreshed = try await authClient.refresh()
        XCTAssertEqual(refreshed, Self.rotatedTokens.authenticatedAccount)
        let storedAfterRefresh = await tokenStore.currentTokens()
        XCTAssertEqual(storedAfterRefresh, Self.rotatedTokens)

        let requestCountBeforeLogout = await requests.count
        try await authClient.logout()
        let storedAfterLogout = await tokenStore.currentTokens()
        XCTAssertNil(storedAfterLogout)
        let requestCountAfterLogout = await requests.count
        XCTAssertEqual(requestCountAfterLogout, requestCountBeforeLogout)

        await events.removeAll()
        try await tokenStore.save(Self.rotatedTokens)
        let acknowledgement = try await authClient.deleteAccount()
        XCTAssertEqual(acknowledgement, Self.deletionAcknowledgement)
        let storedAfterDeletionAcknowledgement = await tokenStore.currentSession()
        XCTAssertEqual(storedAfterDeletionAcknowledgement.accountDeletionIntent?.phase, .accepted)
        XCTAssertNil(await tokenStore.tokensForRetry())

        try await authClient.clearLocalCredentials()
        let storedAfterLocalCleanup = await tokenStore.currentSession()
        XCTAssertEqual(storedAfterLocalCleanup, .signedOut)

        let authenticateRequest = try await requests.onlyRequest(
            operationID: Operations.AuthenticateWithAppleV1AuthApplePost.id
        )
        XCTAssertEqual(authenticateRequest.http.method, .post)
        XCTAssertEqual(authenticateRequest.http.path, "/v1/auth/apple")
        XCTAssertEqual(authenticateRequest.jsonBody?["identity_token"], "identity-token")
        XCTAssertEqual(authenticateRequest.jsonBody?["authorization_code"], "authorization-code")
        XCTAssertEqual(authenticateRequest.jsonBody?["nonce"], "raw-nonce")
        XCTAssertEqual(authenticateRequest.jsonBody?["device_name"], "iPhone 17")

        let refreshRequest = try await requests.onlyRequest(
            operationID: Operations.RefreshSessionV1AuthRefreshPost.id
        )
        XCTAssertEqual(refreshRequest.http.method, .post)
        XCTAssertEqual(refreshRequest.http.path, "/v1/auth/refresh")
        XCTAssertEqual(refreshRequest.jsonBody?["refresh_token"], "refresh-1")

        let deleteRequest = try await requests.onlyRequest(
            operationID: Operations.DeleteAccountV1AccountDeletePost.id
        )
        XCTAssertEqual(deleteRequest.http.method, .post)
        XCTAssertEqual(deleteRequest.http.path, "/v1/account/delete")
        XCTAssertNil(deleteRequest.bodyText)
        XCTAssertEqual(
            deleteRequest.http.headerFields.filter { $0.name == .authorization }.map(\.value),
            ["Bearer access-2"]
        )
        let deletionIntent = try XCTUnwrap(storedAfterDeletionAcknowledgement.accountDeletionIntent)
        XCTAssertEqual(
            deleteRequest.http.headerFields.filter {
                $0.name.rawName.lowercased() == "idempotency-key"
            }.map(\.value),
            [deletionIntent.idempotencyKey]
        )

        let eventSnapshot = await events.snapshot()
        XCTAssertTrue(
            eventSnapshot.isOrdered(before: "token-deletion-marker", after: "server-delete"),
            "Stored credentials must be replaced by a deletion marker before network deletion."
        )
        XCTAssertTrue(
            eventSnapshot.isOrdered(before: "server-delete", after: "token-delete"),
            "Server deletion acknowledgement must be received before bearer and refresh tokens are removed."
        )
    }

    func testLiveDeletePreservesAcknowledgementWhenLocalCleanupRequiresSeparateRetry() async throws {
        let events = EventLog()
        let requests = RecordedProductAuthRequests(events: events)
        let tokenStore = RecordingTokenStore(
            initial: Self.storedTokens,
            events: events,
            clearFailuresRemaining: 1
        )
        let authClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: requests),
            tokenStore: tokenStore,
            deviceName: { nil }
        )

        let acknowledgement = try await authClient.deleteAccount()
        XCTAssertEqual(acknowledgement, Self.deletionAcknowledgement)
        let deletionAttemptsAfterAcknowledgement = await requests.count(
            operationID: Operations.DeleteAccountV1AccountDeletePost.id
        )
        XCTAssertEqual(deletionAttemptsAfterAcknowledgement, 1)
        let storedAfterAcknowledgement = await tokenStore.currentSession()
        XCTAssertEqual(storedAfterAcknowledgement.accountDeletionIntent?.phase, .accepted)
        XCTAssertNil(await tokenStore.tokensForRetry())

        await XCTAssertThrowsAuthClientError(.localCredentialCleanupRequired) {
            try await authClient.clearLocalCredentials()
        }
        let storedAfterFailedCleanup = await tokenStore.currentSession()
        XCTAssertEqual(storedAfterFailedCleanup.accountDeletionIntent?.phase, .accepted)

        try await authClient.clearLocalCredentials()
        let storedAfterRetry = await tokenStore.currentTokens()
        XCTAssertNil(storedAfterRetry)
        let deletionAttemptsAfterRetry = await requests.count(
            operationID: Operations.DeleteAccountV1AccountDeletePost.id
        )
        XCTAssertEqual(deletionAttemptsAfterRetry, 1)
    }

    func testLiveDeleteWritesDurableMarkerBeforeNetworkSubmission() async throws {
        let events = EventLog()
        let requests = RecordedProductAuthRequests(events: events)
        let tokenStore = RecordingTokenStore(initial: Self.storedTokens, events: events)
        let authClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: requests),
            tokenStore: tokenStore,
            deviceName: { nil }
        )

        _ = try await authClient.deleteAccount()

        let eventSnapshot = await events.snapshot()
        XCTAssertTrue(
            eventSnapshot.isOrdered(before: "token-deletion-marker", after: "server-delete"),
            "A crash after submission must leave a deletion-pending marker before network deletion."
        )
        XCTAssertEqual((await tokenStore.currentSession()).accountDeletionIntent?.phase, .accepted)
    }

    func testLiveRestoreSurfacesDeletionReconciliationAfterRestartAndNeverRestoresAccount() async throws {
        let intent = AccountDeletionIntent(idempotencyKey: "delete-key-restore", phase: .pendingSubmission)
        let tokenStore = RecordingTokenStore(
            initial: Self.storedTokens,
            initialDeletionIntent: intent
        )
        let authClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: RecordedProductAuthRequests()),
            tokenStore: tokenStore,
            deviceName: { nil }
        )

        await XCTAssertThrowsAuthClientError(.accountDeletionReconciliationRequired) {
            _ = try await authClient.restore()
        }
        XCTAssertEqual(await tokenStore.currentSession(), .accountDeletionPending(intent))
        XCTAssertEqual(await tokenStore.tokensForRetry(), Self.storedTokens)
    }

    func testLiveDeleteRetryPreservesIntentAndTokensAfterNetworkFailure() async throws {
        let events = EventLog()
        let requests = RecordedProductAuthRequests(events: events)
        var shouldFail = true
        let api = Self.makeAPI { request, body, _, operationID in
            try await requests.record(request: request, body: body, operationID: operationID)
            guard operationID == Operations.DeleteAccountV1AccountDeletePost.id else {
                return Self.errorResponse(status: .badRequest, code: "unexpected_operation")
            }
            if shouldFail {
                shouldFail = false
                throw OfflineProductAuthTransportError()
            }
            return Self.jsonResponse(status: .accepted, body: deletionAcceptedBody)
        }
        let tokenStore = RecordingTokenStore(initial: Self.storedTokens, events: events)
        let authClient = AuthClient.live(
            productAuthAPI: api,
            tokenStore: tokenStore,
            deviceName: { nil }
        )

        await XCTAssertThrowsAuthClientError(.networkUnavailable) {
            try await authClient.deleteAccount()
        }
        let pendingIntent = try XCTUnwrap(
            (await tokenStore.currentSession()).accountDeletionIntent
        )
        XCTAssertEqual(pendingIntent.phase, .pendingSubmission)
        XCTAssertEqual(await tokenStore.tokensForRetry(), Self.storedTokens)

        _ = try await authClient.deleteAccount()

        XCTAssertEqual(
            (await tokenStore.currentSession()).accountDeletionIntent?.idempotencyKey,
            pendingIntent.idempotencyKey
        )
        XCTAssertEqual((await tokenStore.currentSession()).accountDeletionIntent?.phase, .accepted)
        XCTAssertNil(await tokenStore.tokensForRetry())
        XCTAssertEqual(
            await requests.count(operationID: Operations.DeleteAccountV1AccountDeletePost.id),
            2
        )
    }

    func testLiveDeleteReturnsCleanupRequiredWhenAcceptedMarkerWriteFailsAfterServer202() async throws {
        let requests = RecordedProductAuthRequests()
        let tokenStore = RecordingTokenStore(
            initial: Self.storedTokens,
            markDeletionAcceptedFailure: TokenStoreFailure.markDeletionAccepted
        )
        let authClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: requests),
            tokenStore: tokenStore,
            deviceName: { nil }
        )

        await XCTAssertThrowsAuthClientError(.localCredentialCleanupRequired) {
            try await authClient.deleteAccount()
        }

        XCTAssertEqual(
            await requests.count(operationID: Operations.DeleteAccountV1AccountDeletePost.id),
            1
        )
        XCTAssertEqual(
            (await tokenStore.currentSession()).accountDeletionIntent?.phase,
            .pendingSubmission
        )
        XCTAssertEqual(await tokenStore.tokensForRetry(), Self.storedTokens)
    }

    func testLiveDeleteUnknownAcceptedStatusRequiresDeletionReconciliationAndKeepsMarker() async throws {
        let requests = RecordedProductAuthRequests()
        let api = Self.makeAPI { request, body, _, operationID in
            try await requests.record(request: request, body: body, operationID: operationID)
            return Self.jsonResponse(status: .accepted, body: """
            {
              "account_subject": "account-1",
              "status": "unexpected_future_status",
              "requested_at": "2026-07-28T08:00:00Z",
              "updated_at": "2026-07-28T08:00:00Z"
            }
            """)
        }
        let tokenStore = RecordingTokenStore(initial: Self.storedTokens)
        let authClient = AuthClient.live(
            productAuthAPI: api,
            tokenStore: tokenStore,
            deviceName: { nil }
        )

        await XCTAssertThrowsAuthClientError(.accountDeletionReconciliationRequired) {
            try await authClient.deleteAccount()
        }

        XCTAssertEqual(
            await requests.count(operationID: Operations.DeleteAccountV1AccountDeletePost.id),
            1
        )
        XCTAssertEqual(
            (await tokenStore.currentSession()).accountDeletionIntent?.phase,
            .pendingSubmission
        )
        XCTAssertEqual(await tokenStore.tokensForRetry(), Self.storedTokens)
    }

    func testLiveDeletePropagatesAcceptedMarkerWriteCancellationUnchanged() async throws {
        let client = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: RecordedProductAuthRequests()),
            tokenStore: RecordingTokenStore(
                initial: Self.storedTokens,
                markDeletionAcceptedFailure: CancellationError()
            ),
            deviceName: { nil }
        )

        await XCTAssertThrowsCancellationError {
            try await client.deleteAccount()
        }
    }

    func testLiveDeleteDoesNotSubmitNetworkRequestWhenMarkerWriteFails() async throws {
        let requests = RecordedProductAuthRequests()
        let tokenStore = RecordingTokenStore(
            initial: Self.storedTokens,
            markDeletionPendingFailure: TokenStoreFailure.markDeletionPending
        )
        let authClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: requests),
            tokenStore: tokenStore,
            deviceName: { nil }
        )

        await XCTAssertThrowsAuthClientError(.localCredentialPersistenceFailed) {
            try await authClient.deleteAccount()
        }
        XCTAssertEqual(await requests.count, 0)
        XCTAssertEqual(await tokenStore.currentSession(), .authenticated(Self.storedTokens))
    }

    func testLiveClientKeepsMissingTokensProductFailuresAndKeychainFailuresTyped() async throws {
        let missingTokenClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: RecordedProductAuthRequests()),
            tokenStore: RecordingTokenStore(),
            deviceName: { nil }
        )
        await XCTAssertThrowsAuthClientError(.sessionExpired) {
            _ = try await missingTokenClient.refresh()
        }

        let credentialFailureClient = AuthClient.live(
            productAuthAPI: Self.makeAPI { _, _, _, operationID in
                XCTAssertEqual(operationID, Operations.AuthenticateWithAppleV1AuthApplePost.id)
                return Self.errorResponse(status: .unauthorized, code: "apple_identity_invalid")
            },
            tokenStore: RecordingTokenStore(),
            deviceName: { nil }
        )
        await XCTAssertThrowsAuthClientError(.invalidAppleCredential) {
            _ = try await credentialFailureClient.authenticate(
                AppleSignInCredential(
                    userIdentifier: "apple-user-1",
                    identityToken: "bad-identity",
                    authorizationCode: "code"
                ),
                "raw-nonce"
            )
        }

        let expiredRefreshClient = AuthClient.live(
            productAuthAPI: Self.makeAPI { _, _, _, operationID in
                XCTAssertEqual(operationID, Operations.RefreshSessionV1AuthRefreshPost.id)
                return Self.errorResponse(status: .unauthorized, code: "refresh_token_expired")
            },
            tokenStore: RecordingTokenStore(initial: Self.storedTokens),
            deviceName: { nil }
        )
        await XCTAssertThrowsAuthClientError(.sessionExpired) {
            _ = try await expiredRefreshClient.refresh()
        }

        let readFailureClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: RecordedProductAuthRequests()),
            tokenStore: RecordingTokenStore(loadFailure: TokenStoreFailure.load),
            deviceName: { nil }
        )
        await XCTAssertThrowsAuthClientError(.localCredentialPersistenceFailed) {
            _ = try await readFailureClient.restore()
        }

        let saveFailureClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: RecordedProductAuthRequests()),
            tokenStore: RecordingTokenStore(saveFailure: TokenStoreFailure.save),
            deviceName: { nil }
        )
        await XCTAssertThrowsAuthClientError(.localCredentialPersistenceFailed) {
            _ = try await saveFailureClient.authenticate(
                AppleSignInCredential(
                    userIdentifier: "apple-user-1",
                    identityToken: "identity-token",
                    authorizationCode: "code"
                ),
                "raw-nonce"
            )
        }

        let clearFailureClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: RecordedProductAuthRequests()),
            tokenStore: RecordingTokenStore(
                initial: Self.storedTokens,
                clearFailuresRemaining: 1
            ),
            deviceName: { nil }
        )
        await XCTAssertThrowsAuthClientError(.localCredentialCleanupRequired) {
            try await clearFailureClient.logout()
        }
    }

    func testLiveClientPreservesProductAuthErrorCategories() async throws {
        let cases: [(ProductAuthOperation, HTTPResponse.Status, String, AuthClientError)] = [
            (
                .authenticate,
                .serviceUnavailable,
                "apple_authorization_unavailable",
                .authorizationUnavailable
            ),
            (.authenticate, .conflict, "account_binding_conflict", .accountConflict),
            (.refresh, .badRequest, "request_invalid", .requestRejected),
            (.deleteAccount, .serviceUnavailable, "processing_dispatch_unavailable", .serviceUnavailable),
        ]

        for (operation, status, code, expectedError) in cases {
            let client = AuthClient.live(
                productAuthAPI: Self.makeAPI { _, _, _, _ in
                    Self.errorResponse(status: status, code: code)
                },
                tokenStore: RecordingTokenStore(initial: Self.storedTokens),
                deviceName: { nil }
            )

            await XCTAssertThrowsAuthClientError(expectedError) {
                try await operation.run(client)
            }
        }

        let invalidResponseClient = AuthClient.live(
            productAuthAPI: Self.makeAPI { _, _, _, _ in
                Self.jsonResponse(status: .ok, body: #"{"access_token":"truncated"}"#)
            },
            tokenStore: RecordingTokenStore(initial: Self.storedTokens),
            deviceName: { nil }
        )
        await XCTAssertThrowsAuthClientError(.invalidResponse) {
            _ = try await invalidResponseClient.refresh()
        }

        let networkFailureClient = AuthClient.live(
            productAuthAPI: Self.makeAPI { _, _, _, _ in
                throw OfflineProductAuthTransportError()
            },
            tokenStore: RecordingTokenStore(initial: Self.storedTokens),
            deviceName: { nil }
        )
        await XCTAssertThrowsAuthClientError(.networkUnavailable) {
            _ = try await networkFailureClient.refresh()
        }
    }

    func testLiveRestorePropagatesLocalCancellationUnchanged() async throws {
        let client = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: RecordedProductAuthRequests()),
            tokenStore: RecordingTokenStore(loadFailure: CancellationError()),
            deviceName: { nil }
        )

        await XCTAssertThrowsCancellationError {
            _ = try await client.restore()
        }
    }

    func testLiveAuthenticatePropagatesProductAuthCancellationUnchanged() async throws {
        let client = AuthClient.live(
            productAuthAPI: Self.makeAPI { _, _, _, operationID in
                XCTAssertEqual(operationID, Operations.AuthenticateWithAppleV1AuthApplePost.id)
                throw CancellationError()
            },
            tokenStore: RecordingTokenStore(),
            deviceName: { nil }
        )

        await XCTAssertThrowsCancellationError {
            _ = try await client.authenticate(
                AppleSignInCredential(
                    userIdentifier: "apple-user-1",
                    identityToken: "identity-token",
                    authorizationCode: "authorization-code"
                ),
                "raw-nonce"
            )
        }
    }

    func testLiveRefreshPropagatesProductAuthCancellationUnchanged() async throws {
        let client = AuthClient.live(
            productAuthAPI: Self.makeAPI { _, _, _, operationID in
                XCTAssertEqual(operationID, Operations.RefreshSessionV1AuthRefreshPost.id)
                throw CancellationError()
            },
            tokenStore: RecordingTokenStore(initial: Self.storedTokens),
            deviceName: { nil }
        )

        await XCTAssertThrowsCancellationError {
            _ = try await client.refresh()
        }
    }

    func testLiveDeleteAccountPropagatesProductAuthCancellationUnchanged() async throws {
        let client = AuthClient.live(
            productAuthAPI: Self.makeAPI { _, _, _, operationID in
                XCTAssertEqual(operationID, Operations.DeleteAccountV1AccountDeletePost.id)
                throw CancellationError()
            },
            tokenStore: RecordingTokenStore(initial: Self.storedTokens),
            deviceName: { nil }
        )

        await XCTAssertThrowsCancellationError {
            try await client.deleteAccount()
        }
    }

    func testLiveClearLocalCredentialsPropagatesLocalCancellationUnchanged() async throws {
        let client = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: RecordedProductAuthRequests()),
            tokenStore: RecordingTokenStore(
                initial: Self.storedTokens,
                clearFailure: CancellationError()
            ),
            deviceName: { nil }
        )

        await XCTAssertThrowsCancellationError {
            try await client.clearLocalCredentials()
        }
    }

    func testLiveClientPersistsAppleUserIdentifierAndKeepsItAcrossRefresh() async throws {
        let tokenStore = RecordingTokenStore()
        let authClient = AuthClient.live(
            productAuthAPI: Self.makeAPI(requests: RecordedProductAuthRequests()),
            tokenStore: tokenStore,
            deviceName: { nil }
        )

        let signedIn = try await authClient.authenticate(
            AppleSignInCredential(
                userIdentifier: "apple-user-1",
                identityToken: "identity-token-with-different-subject",
                authorizationCode: "authorization-code"
            ),
            "raw-nonce"
        )

        XCTAssertEqual(signedIn.appleUserIdentifier, "apple-user-1")
        let storedAfterSignIn = await tokenStore.currentTokens()
        XCTAssertEqual(storedAfterSignIn?.appleUserIdentifier, "apple-user-1")

        let refreshed = try await authClient.refresh()

        XCTAssertEqual(refreshed.appleUserIdentifier, "apple-user-1")
        let storedAfterRefresh = await tokenStore.currentTokens()
        XCTAssertEqual(storedAfterRefresh?.appleUserIdentifier, "apple-user-1")
    }

    func testAuthTokensCodablePreservesAppleUserIdentifierAndDefaultsLegacyPayload() throws {
        let encoded = try JSONEncoder.iso8601AuthTokens.encode(
            AuthTokens(
                accountSubject: "account-1",
                accessToken: "access-1",
                refreshToken: "refresh-1",
                accessExpiresAt: Date(timeIntervalSince1970: 1_785_225_600),
                tokenType: "Bearer",
                appleUserIdentifier: "apple-user-1"
            )
        )

        let decoded = try JSONDecoder.iso8601AuthTokens.decode(AuthTokens.self, from: encoded)
        XCTAssertEqual(decoded.appleUserIdentifier, "apple-user-1")

        let legacyPayload = Data(
            """
            {
              "accountSubject": "account-legacy",
              "accessToken": "access-legacy",
              "refreshToken": "refresh-legacy",
              "accessExpiresAt": "2026-07-28T08:00:00Z",
              "tokenType": "Bearer"
            }
            """.utf8
        )
        let legacy = try JSONDecoder.iso8601AuthTokens.decode(AuthTokens.self, from: legacyPayload)
        XCTAssertNil(legacy.appleUserIdentifier)
    }
}

private extension AuthClientLiveTests {
    static let storedTokens = AuthTokens(
        accountSubject: "account-1",
        accessToken: "access-1",
        refreshToken: "refresh-1",
        accessExpiresAt: Date(timeIntervalSince1970: 1_785_225_600),
        tokenType: "Bearer"
    )

    static let signedInTokens = AuthTokens(
        accountSubject: "account-1",
        accessToken: "access-1",
        refreshToken: "refresh-1",
        accessExpiresAt: Date(timeIntervalSince1970: 1_785_225_600),
        tokenType: "Bearer",
        appleUserIdentifier: "apple-user-1"
    )

    static let rotatedTokens = AuthTokens(
        accountSubject: "account-1",
        accessToken: "access-2",
        refreshToken: "refresh-2",
        accessExpiresAt: Date(timeIntervalSince1970: 1_785_226_500),
        tokenType: "Bearer",
        appleUserIdentifier: "apple-user-1"
    )

    static let deletionAcknowledgement = AccountDeletionAcknowledgement(
        status: .accepted
    )

    static func makeAPI(requests: RecordedProductAuthRequests) -> ProductAuthAPI {
        makeAPI { request, body, _, operationID in
            try await requests.record(request: request, body: body, operationID: operationID)
            switch operationID {
            case Operations.AuthenticateWithAppleV1AuthApplePost.id:
                return jsonResponse(status: .ok, body: tokenResponseBody(Self.signedInTokens))
            case Operations.RefreshSessionV1AuthRefreshPost.id:
                return jsonResponse(status: .ok, body: tokenResponseBody(Self.rotatedTokens))
            case Operations.DeleteAccountV1AccountDeletePost.id:
                return jsonResponse(status: .accepted, body: deletionAcceptedBody)
            default:
                XCTFail("Unexpected Product auth operation: \(operationID)")
                return errorResponse(status: .internalServerError, code: "unexpected_operation")
            }
        }
    }

    static func makeAPI(handler: @escaping TestProductAuthTransport.Handler) -> ProductAuthAPI {
        ProductAuthAPI(
            clientFactory: { middlewares in
                Client(
                    serverURL: URL(string: "https://api.stylecapture.test")!,
                    transport: TestProductAuthTransport(handler: handler),
                    middlewares: middlewares
                )
            }
        )
    }

    static func tokenResponseBody(_ tokens: AuthTokens) -> String {
        let expiry = tokens.accessToken == "access-2"
            ? "2026-07-28T08:15:00Z"
            : "2026-07-28T08:00:00Z"
        return """
        {
          "account_subject": "\(tokens.accountSubject)",
          "access_token": "\(tokens.accessToken)",
          "refresh_token": "\(tokens.refreshToken)",
          "access_expires_at": "\(expiry)",
          "token_type": "\(tokens.tokenType)"
        }
        """
    }

    static let deletionAcceptedBody = """
    {
      "account_subject": "account-1",
      "status": "pending_deletion",
      "requested_at": "2026-07-28T08:00:00Z",
      "updated_at": "2026-07-28T08:00:00Z"
    }
    """

    static func errorResponse(
        status: HTTPResponse.Status,
        code: String
    ) -> (HTTPResponse, HTTPBody?) {
        jsonResponse(
            status: status,
            body: """
            {
              "error": {
                "code": "\(code)",
                "message": "Request failed",
                "request_id": "request-1"
              }
            }
            """
        )
    }

    static func jsonResponse(
        status: HTTPResponse.Status,
        body: String
    ) -> (HTTPResponse, HTTPBody?) {
        (
            HTTPResponse(
                status: status,
                headerFields: [.contentType: "application/json"]
            ),
            HTTPBody(body)
        )
    }
}

private func XCTAssertThrowsAuthClientError(
    _ expected: AuthClientError,
    operation: () async throws -> Void,
    file: StaticString = #filePath,
    line: UInt = #line
) async {
    do {
        try await operation()
        XCTFail("Expected AuthClientError.\(expected)", file: file, line: line)
    } catch let error as AuthClientError {
        XCTAssertEqual(error, expected, file: file, line: line)
    } catch {
        XCTFail("Expected AuthClientError.\(expected), got \(error)", file: file, line: line)
    }
}

private func XCTAssertThrowsCancellationError(
    operation: () async throws -> Void,
    file: StaticString = #filePath,
    line: UInt = #line
) async {
    do {
        try await operation()
        XCTFail("Expected CancellationError", file: file, line: line)
    } catch is CancellationError {
        return
    } catch {
        XCTFail("Expected CancellationError, got \(error)", file: file, line: line)
    }
}

private struct TestProductAuthTransport: ClientTransport {
    typealias Handler = @Sendable (
        HTTPRequest,
        HTTPBody?,
        URL,
        String
    ) async throws -> (HTTPResponse, HTTPBody?)

    var handler: Handler

    func send(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String
    ) async throws -> (HTTPResponse, HTTPBody?) {
        try await handler(request, body, baseURL, operationID)
    }
}

private actor RecordedProductAuthRequests {
    private var requests: [RecordedProductAuthRequest] = []
    private let events: EventLog?

    init(events: EventLog? = nil) {
        self.events = events
    }

    var count: Int {
        requests.count
    }

    func count(operationID: String) -> Int {
        requests.filter { $0.operationID == operationID }.count
    }

    func record(
        request: HTTPRequest,
        body: HTTPBody?,
        operationID: String
    ) async throws {
        let bodyText: String?
        if let body {
            bodyText = try await String(collecting: body, upTo: 4_096)
        } else {
            bodyText = nil
        }
        let jsonBody: [String: String]?
        if let bodyText,
           let data = bodyText.data(using: .utf8) {
            let object = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            jsonBody = object?.reduce(into: [:]) { result, element in
                if let value = element.value as? String {
                    result[element.key] = value
                }
            }
        } else {
            jsonBody = nil
        }
        requests.append(
            RecordedProductAuthRequest(
                http: request,
                bodyText: bodyText,
                jsonBody: jsonBody,
                operationID: operationID
            )
        )
        if operationID == Operations.DeleteAccountV1AccountDeletePost.id {
            await events?.record("server-delete")
        }
    }

    func onlyRequest(operationID: String) throws -> RecordedProductAuthRequest {
        let matches = requests.filter { $0.operationID == operationID }
        XCTAssertEqual(matches.count, 1)
        return try XCTUnwrap(matches.first)
    }
}

private struct RecordedProductAuthRequest {
    var http: HTTPRequest
    var bodyText: String?
    var jsonBody: [String: String]?
    var operationID: String
}

private enum ProductAuthOperation {
    case authenticate
    case refresh
    case deleteAccount

    func run(_ client: AuthClient) async throws {
        switch self {
        case .authenticate:
            _ = try await client.authenticate(
                AppleSignInCredential(
                    userIdentifier: "apple-user-1",
                    identityToken: "identity-token",
                    authorizationCode: "authorization-code"
                ),
                "raw-nonce"
            )
        case .refresh:
            _ = try await client.refresh()
        case .deleteAccount:
            try await client.deleteAccount()
        }
    }
}

private struct OfflineProductAuthTransportError: Error {}

private actor RecordingTokenStore: TokenStore {
    private var tokens: AuthTokens?
    private var deletionIntent: AccountDeletionIntent?
    private let events: EventLog?
    private let loadFailure: Error?
    private let saveFailure: Error?
    private let markDeletionPendingFailure: Error?
    private let markDeletionAcceptedFailure: Error?
    private let clearFailure: Error?
    private var clearFailuresRemaining: Int

    init(
        initial: AuthTokens? = nil,
        initialSession: StoredAuthSession? = nil,
        initialDeletionIntent: AccountDeletionIntent? = nil,
        events: EventLog? = nil,
        loadFailure: Error? = nil,
        saveFailure: Error? = nil,
        markDeletionPendingFailure: Error? = nil,
        markDeletionAcceptedFailure: Error? = nil,
        clearFailure: Error? = nil,
        clearFailuresRemaining: Int = 0
    ) {
        if let initialSession {
            switch initialSession {
            case .signedOut:
                tokens = nil
                deletionIntent = nil
            case let .authenticated(stored):
                tokens = stored
                deletionIntent = nil
            case let .accountDeletionPending(intent):
                tokens = initial
                deletionIntent = intent
            }
        } else {
            tokens = initial
            deletionIntent = initialDeletionIntent
        }
        self.events = events
        self.loadFailure = loadFailure
        self.saveFailure = saveFailure
        self.markDeletionPendingFailure = markDeletionPendingFailure
        self.markDeletionAcceptedFailure = markDeletionAcceptedFailure
        self.clearFailure = clearFailure
        self.clearFailuresRemaining = clearFailuresRemaining
    }

    func currentTokens() -> AuthTokens? {
        deletionIntent == nil ? tokens : nil
    }

    func tokensForRetry() -> AuthTokens? {
        tokens
    }

    func currentSession() -> StoredAuthSession {
        if let deletionIntent {
            return .accountDeletionPending(deletionIntent)
        }
        if let tokens {
            return .authenticated(tokens)
        }
        return .signedOut
    }

    func load() throws -> StoredAuthSession {
        if let loadFailure {
            throw loadFailure
        }
        currentSession()
    }

    func save(_ tokens: AuthTokens) throws {
        if let saveFailure {
            throw saveFailure
        }
        self.tokens = tokens
        deletionIntent = nil
    }

    func loadTokensForAccountDeletionRetry() throws -> AuthTokens? {
        tokens
    }

    func markAccountDeletionPending() async throws -> AccountDeletionIntent {
        if let markDeletionPendingFailure {
            throw markDeletionPendingFailure
        }
        if let deletionIntent {
            return deletionIntent
        }
        let intent = AccountDeletionIntent(idempotencyKey: "delete-key-\(UUID().uuidString)")
        deletionIntent = intent
        await events?.record("token-deletion-marker")
        return intent
    }

    func markAccountDeletionAccepted(_ intent: AccountDeletionIntent) async throws {
        if let markDeletionAcceptedFailure {
            throw markDeletionAcceptedFailure
        }
        deletionIntent = AccountDeletionIntent(
            idempotencyKey: intent.idempotencyKey,
            phase: .accepted
        )
        tokens = nil
        await events?.record("token-delete")
    }

    func clear() async throws {
        await events?.record("token-clear")
        if let clearFailure {
            throw clearFailure
        }
        if clearFailuresRemaining > 0 {
            clearFailuresRemaining -= 1
            throw TokenStoreFailure.clear
        }
        tokens = nil
        deletionIntent = nil
    }
}

private enum TokenStoreFailure: Error, Equatable {
    case load
    case save
    case markDeletionPending
    case markDeletionAccepted
    case clear
}

private actor EventLog {
    private var events: [String] = []

    func record(_ event: String) {
        events.append(event)
    }

    func snapshot() -> [String] {
        events
    }

    func removeAll() {
        events.removeAll()
    }
}

private extension Array where Element == String {
    func isOrdered(before earlier: String, after later: String) -> Bool {
        guard let earlierIndex = firstIndex(of: earlier),
              let laterIndex = firstIndex(of: later) else {
            return false
        }
        return earlierIndex < laterIndex
    }
}

private extension StoredAuthSession {
    var accountDeletionIntent: AccountDeletionIntent? {
        guard case let .accountDeletionPending(intent) = self else {
            return nil
        }
        return intent
    }
}

private extension JSONEncoder {
    static var iso8601AuthTokens: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }
}

private extension JSONDecoder {
    static var iso8601AuthTokens: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }
}
