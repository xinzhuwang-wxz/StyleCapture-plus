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
        XCTAssertEqual(restored, Self.storedTokens)

        let signedIn = try await authClient.authenticate(
            AppleSignInCredential(
                identityToken: "identity-token",
                authorizationCode: "authorization-code"
            ),
            "raw-nonce"
        )
        XCTAssertEqual(signedIn, Self.signedInTokens)
        let storedAfterSignIn = await tokenStore.currentTokens()
        XCTAssertEqual(storedAfterSignIn, Self.signedInTokens)

        let refreshed = try await authClient.refresh()
        XCTAssertEqual(refreshed, Self.rotatedTokens)
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
        try await authClient.deleteAccount()
        let storedAfterDeletion = await tokenStore.currentTokens()
        XCTAssertNil(storedAfterDeletion)

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

        let eventSnapshot = await events.snapshot()
        XCTAssertTrue(
            eventSnapshot.isOrdered(before: "server-delete", after: "token-clear"),
            "Server deletion must complete before local credential cleanup."
        )
    }

    func testLiveDeleteMapsPostServerKeychainClearFailureToLocalCleanupRequired() async throws {
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

        await XCTAssertThrowsAuthClientError(.localCredentialCleanupRequired) {
            try await authClient.deleteAccount()
        }
        let deletionAttemptsAfterFailure = await requests.count(
            operationID: Operations.DeleteAccountV1AccountDeletePost.id
        )
        XCTAssertEqual(deletionAttemptsAfterFailure, 1)
        let storedAfterFailedCleanup = await tokenStore.currentTokens()
        XCTAssertEqual(storedAfterFailedCleanup, Self.storedTokens)

        try await authClient.clearLocalCredentials()
        let storedAfterRetry = await tokenStore.currentTokens()
        XCTAssertNil(storedAfterRetry)
        let deletionAttemptsAfterRetry = await requests.count(
            operationID: Operations.DeleteAccountV1AccountDeletePost.id
        )
        XCTAssertEqual(deletionAttemptsAfterRetry, 1)
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
                AppleSignInCredential(identityToken: "bad-identity", authorizationCode: "code"),
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
                AppleSignInCredential(identityToken: "identity-token", authorizationCode: "code"),
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
        tokenType: "Bearer"
    )

    static let rotatedTokens = AuthTokens(
        accountSubject: "account-1",
        accessToken: "access-2",
        refreshToken: "refresh-2",
        accessExpiresAt: Date(timeIntervalSince1970: 1_785_226_500),
        tokenType: "Bearer"
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

private actor RecordingTokenStore: TokenStore {
    private var tokens: AuthTokens?
    private let events: EventLog?
    private let loadFailure: Error?
    private let saveFailure: Error?
    private var clearFailuresRemaining: Int

    init(
        initial: AuthTokens? = nil,
        events: EventLog? = nil,
        loadFailure: Error? = nil,
        saveFailure: Error? = nil,
        clearFailuresRemaining: Int = 0
    ) {
        tokens = initial
        self.events = events
        self.loadFailure = loadFailure
        self.saveFailure = saveFailure
        self.clearFailuresRemaining = clearFailuresRemaining
    }

    func currentTokens() -> AuthTokens? {
        tokens
    }

    func load() throws -> AuthTokens? {
        if let loadFailure {
            throw loadFailure
        }
        return tokens
    }

    func save(_ tokens: AuthTokens) throws {
        if let saveFailure {
            throw saveFailure
        }
        self.tokens = tokens
    }

    func clear() async throws {
        await events?.record("token-clear")
        if clearFailuresRemaining > 0 {
            clearFailuresRemaining -= 1
            throw TokenStoreFailure.clear
        }
        tokens = nil
    }
}

private enum TokenStoreFailure: Error, Equatable {
    case load
    case save
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
