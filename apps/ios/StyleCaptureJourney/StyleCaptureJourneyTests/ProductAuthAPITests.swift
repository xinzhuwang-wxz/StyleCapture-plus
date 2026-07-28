import Foundation
import HTTPTypes
import OpenAPIRuntime
import XCTest
@testable import StyleCaptureAPI
@testable import StyleCaptureJourney

final class ProductAuthAPITests: XCTestCase {
    func testAuthenticateWithApplePostsCredentialThroughGeneratedClientAndMapsTokens() async throws {
        let recorder = RecordedProductAuthRequests()
        let api = Self.makeAPI { request, body, _, operationID in
            try await recorder.record(
                request: request,
                body: body,
                operationID: operationID
            )
            return Self.authTokenResponse()
        }

        let tokens = try await api.authenticate(
            AppleSignInRequest(
                identityToken: "identity-token",
                authorizationCode: "authorization-code",
                nonce: "raw-nonce",
                deviceName: "iPhone 17"
            )
        )

        let request = try await recorder.onlyRequest()
        XCTAssertEqual(request.operationID, Operations.AuthenticateWithAppleV1AuthApplePost.id)
        XCTAssertEqual(request.http.method, .post)
        XCTAssertEqual(request.http.path, "/v1/auth/apple")
        let payload = try XCTUnwrap(request.jsonBody)
        XCTAssertEqual(payload["identity_token"], "identity-token")
        XCTAssertEqual(payload["authorization_code"], "authorization-code")
        XCTAssertEqual(payload["nonce"], "raw-nonce")
        XCTAssertEqual(payload["device_name"], "iPhone 17")
        XCTAssertEqual(tokens, Self.expectedTokens)
    }

    func testRefreshPostsRefreshTokenThroughGeneratedClientAndMapsTokens() async throws {
        let recorder = RecordedProductAuthRequests()
        let api = Self.makeAPI { request, body, _, operationID in
            try await recorder.record(
                request: request,
                body: body,
                operationID: operationID
            )
            return Self.authTokenResponse()
        }

        let tokens = try await api.refresh(refreshToken: "refresh-token")

        let request = try await recorder.onlyRequest()
        XCTAssertEqual(request.operationID, Operations.RefreshSessionV1AuthRefreshPost.id)
        XCTAssertEqual(request.http.method, .post)
        XCTAssertEqual(request.http.path, "/v1/auth/refresh")
        let payload = try XCTUnwrap(request.jsonBody)
        XCTAssertEqual(payload["refresh_token"], "refresh-token")
        XCTAssertEqual(tokens, Self.expectedTokens)
    }

    func testDeleteAccountPostsExactlyOneBearerHeaderAndOnlyAcceptedSucceeds() async throws {
        let recorder = RecordedProductAuthRequests()
        let api = Self.makeAPI { request, body, _, operationID in
            try await recorder.record(
                request: request,
                body: body,
                operationID: operationID
            )
            return Self.deletionAcceptedResponse()
        }

        try await api.deleteAccount(accessToken: "access-token")

        let request = try await recorder.onlyRequest()
        XCTAssertEqual(request.operationID, Operations.DeleteAccountV1AccountDeletePost.id)
        XCTAssertEqual(request.http.method, .post)
        XCTAssertEqual(request.http.path, "/v1/account/delete")
        XCTAssertNil(request.bodyText)
        let authorizationHeaders = request.http.headerFields.filter {
            $0.name == .authorization
        }
        XCTAssertEqual(authorizationHeaders.map(\.value), ["Bearer access-token"])

        let unexpectedSuccessAPI = Self.makeAPI { _, _, _, _ in
            Self.jsonResponse(status: .ok, body: Self.deletionResponseBody)
        }
        do {
            try await unexpectedSuccessAPI.deleteAccount(accessToken: "access-token")
            XCTFail("Expected generated 200 ok to be rejected for deleteAccount")
        } catch let error as ProductAuthAPI.APIError {
            XCTAssertEqual(error, .unexpectedResponse)
        }
    }

    func testAuthenticateMapsAppleCredentialFailuresByBackendCode() async throws {
        let cases: [(HTTPResponse.Status, String, ProductAuthAPI.APIError, UInt)] = [
            (.unauthorized, "apple_identity_invalid", .invalidCredential, #line),
            (.unauthorized, "apple_authorization_failed", .invalidCredential, #line),
            (.unauthorized, "apple_nonce_invalid", .invalidCredential, #line),
            (.unprocessableContent, "request_invalid", .invalidRequest, #line),
            (.conflict, "authorization_code_replayed", .conflict, #line),
            (.conflict, "account_binding_conflict", .conflict, #line),
            (.serviceUnavailable, "apple_identity_unavailable", .serverUnavailable, #line),
            (.serviceUnavailable, "apple_authorization_unavailable", .serverUnavailable, #line),
            (.notFound, "account_not_found", .unexpectedResponse, #line),
            (HTTPResponse.Status(code: 418, reasonPhrase: "Teapot"), "undocumented", .unexpectedResponse, #line),
        ]

        for (status, code, expectedError, line) in cases {
            await Self.assertAuthenticateFailure(
                status: status,
                code: code,
                expectedError: expectedError,
                line: line
            )
        }
    }

    func testRefreshMapsSessionFailuresByBackendCode() async throws {
        let cases: [(HTTPResponse.Status, String, ProductAuthAPI.APIError, UInt)] = [
            (.badRequest, "request_invalid", .invalidRequest, #line),
            (.unprocessableContent, "request_invalid", .invalidRequest, #line),
            (.unauthorized, "session_invalid", .sessionExpired, #line),
            (.unauthorized, "refresh_token_expired", .sessionExpired, #line),
            (.conflict, "refresh_token_reused", .conflict, #line),
            (.serviceUnavailable, "processing_dispatch_unavailable", .serverUnavailable, #line),
        ]

        for (status, code, expectedError, line) in cases {
            await Self.assertRefreshFailure(
                status: status,
                code: code,
                expectedError: expectedError,
                line: line
            )
        }
    }

    func testDeleteAccountMapsSessionFailuresByBackendCode() async throws {
        let cases: [(HTTPResponse.Status, String, ProductAuthAPI.APIError, UInt)] = [
            (.badRequest, "request_invalid", .invalidRequest, #line),
            (.unprocessableContent, "request_invalid", .invalidRequest, #line),
            (.unauthorized, "session_invalid", .sessionExpired, #line),
            (.conflict, "account_delete_conflict", .conflict, #line),
            (.serviceUnavailable, "processing_dispatch_unavailable", .serverUnavailable, #line),
        ]

        for (status, code, expectedError, line) in cases {
            await Self.assertDeleteAccountFailure(
                status: status,
                code: code,
                expectedError: expectedError,
                line: line
            )
        }
    }

    func testTransportAndDecodingFailuresMapToTypedProductAuthAPIErrors() async throws {
        let offlineAPI = Self.makeAPI { _, _, _, _ in
            throw OfflineProductAuthTransportError()
        }

        do {
            _ = try await offlineAPI.refresh(refreshToken: "refresh-token")
            XCTFail("Expected transport failure to throw")
        } catch let error as ProductAuthAPI.APIError {
            XCTAssertEqual(error, .transportFailure)
        }

        let malformedAPI = Self.makeAPI { _, _, _, _ in
            Self.jsonResponse(status: .ok, body: #"{"access_token":"truncated"}"#)
        }

        do {
            _ = try await malformedAPI.refresh(refreshToken: "refresh-token")
            XCTFail("Expected malformed generated response to throw")
        } catch let error as ProductAuthAPI.APIError {
            XCTAssertEqual(error, .unexpectedResponse)
        }
    }

    func testBearerMiddlewareAddsAuthorizationHeader() async throws {
        let middleware = BearerAuthorizationMiddleware(accessToken: "access-token")
        let body = HTTPBody("request-body")
        let baseURL = URL(string: "https://api.stylecapture.test")!
        let request = HTTPRequest(
            method: .delete,
            scheme: "https",
            authority: "api.stylecapture.test",
            path: "/v1/account"
        )

        _ = try await middleware.intercept(
            request,
            body: body,
            baseURL: baseURL,
            operationID: "delete_account_v1_account_delete_post"
        ) { forwardedRequest, forwardedBody, forwardedBaseURL in
            XCTAssertEqual(
                forwardedRequest.headerFields[.authorization],
                "Bearer access-token"
            )
            XCTAssertEqual(forwardedBaseURL, baseURL)
            let forwardedBytes = try await String(
                collecting: try XCTUnwrap(forwardedBody),
                upTo: 1_024
            )
            XCTAssertEqual(forwardedBytes, "request-body")
            return (HTTPResponse(status: .accepted), nil)
        }
    }

    func testAppleRequestMappingPreservesRawCredentialPayload() {
        let body = ProductAuthAPI.appleAuthBody(
            from: AppleSignInRequest(
                identityToken: "identity-token",
                authorizationCode: "authorization-code",
                nonce: "raw-nonce",
                deviceName: "iPhone 17"
            )
        )

        XCTAssertEqual(body.identityToken, "identity-token")
        XCTAssertEqual(body.authorizationCode, "authorization-code")
        XCTAssertEqual(body.nonce, "raw-nonce")
        XCTAssertEqual(body.deviceName, "iPhone 17")
    }

    func testGeneratedTokenResponseMapsIntoDomainValue() {
        let expiresAt = Date(timeIntervalSince1970: 1_785_200_000)
        let tokens = ProductAuthAPI.authTokens(
            from: Components.Schemas.AuthTokenResponse(
                accessExpiresAt: expiresAt,
                accessToken: "access-1",
                accountSubject: "account-1",
                refreshToken: "refresh-1",
                tokenType: "Bearer"
            )
        )

        XCTAssertEqual(
            tokens,
            AuthTokens(
                accountSubject: "account-1",
                accessToken: "access-1",
                refreshToken: "refresh-1",
                accessExpiresAt: expiresAt,
                tokenType: "Bearer"
            )
        )
    }
}

private extension ProductAuthAPITests {
    static let expectedAccessExpiresAt = Date(timeIntervalSince1970: 1_785_225_600)
    static let expectedTokens = AuthTokens(
        accountSubject: "11111111-1111-1111-1111-111111111111",
        accessToken: "access-1",
        refreshToken: "refresh-1",
        accessExpiresAt: expectedAccessExpiresAt,
        tokenType: "Bearer"
    )
    static let tokenResponseBody = """
    {
      "account_subject": "11111111-1111-1111-1111-111111111111",
      "access_token": "access-1",
      "refresh_token": "refresh-1",
      "access_expires_at": "2026-07-28T08:00:00Z",
      "token_type": "Bearer"
    }
    """
    static let deletionResponseBody = """
    {
      "account_subject": "11111111-1111-1111-1111-111111111111",
      "status": "pending_deletion",
      "requested_at": "2026-07-28T08:00:00Z",
      "updated_at": "2026-07-28T08:00:00Z"
    }
    """

    static func makeAPI(handler: @escaping TestProductAuthTransport.Handler) -> ProductAuthAPI {
        ProductAuthAPI { middlewares in
            Client(
                serverURL: URL(string: "https://api.stylecapture.test")!,
                transport: TestProductAuthTransport(handler: handler),
                middlewares: middlewares
            )
        }
    }

    static func authTokenResponse() -> (HTTPResponse, HTTPBody?) {
        Self.jsonResponse(status: .ok, body: tokenResponseBody)
    }

    static func deletionAcceptedResponse() -> (HTTPResponse, HTTPBody?) {
        Self.jsonResponse(status: .accepted, body: deletionResponseBody)
    }

    static func errorResponseBody(code: String) -> String {
        """
        {
          "error": {
            "code": "\(code)",
            "message": "Request failed",
            "request_id": "request-1"
          }
        }
        """
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

    static func assertAuthenticateFailure(
        status: HTTPResponse.Status,
        code: String,
        expectedError: ProductAuthAPI.APIError,
        line: UInt
    ) async {
        let api = Self.makeAPI { _, _, _, _ in
            Self.jsonResponse(status: status, body: Self.errorResponseBody(code: code))
        }

        do {
            _ = try await api.authenticate(
                AppleSignInRequest(
                    identityToken: "identity-token",
                    authorizationCode: "authorization-code",
                    nonce: "raw-nonce",
                    deviceName: nil
                )
            )
            XCTFail("Expected authenticate \(status) \(code) to throw", line: line)
        } catch let error as ProductAuthAPI.APIError {
            XCTAssertEqual(error, expectedError, line: line)
        } catch {
            XCTFail("Expected ProductAuthAPI.APIError, got \(error)", line: line)
        }
    }

    static func assertRefreshFailure(
        status: HTTPResponse.Status,
        code: String,
        expectedError: ProductAuthAPI.APIError,
        line: UInt
    ) async {
        let api = Self.makeAPI { _, _, _, _ in
            Self.jsonResponse(status: status, body: Self.errorResponseBody(code: code))
        }

        do {
            _ = try await api.refresh(refreshToken: "refresh-token")
            XCTFail("Expected refresh \(status) \(code) to throw", line: line)
        } catch let error as ProductAuthAPI.APIError {
            XCTAssertEqual(error, expectedError, line: line)
        } catch {
            XCTFail("Expected ProductAuthAPI.APIError, got \(error)", line: line)
        }
    }

    static func assertDeleteAccountFailure(
        status: HTTPResponse.Status,
        code: String,
        expectedError: ProductAuthAPI.APIError,
        line: UInt
    ) async {
        let api = Self.makeAPI { _, _, _, _ in
            Self.jsonResponse(status: status, body: Self.errorResponseBody(code: code))
        }

        do {
            try await api.deleteAccount(accessToken: "access-token")
            XCTFail("Expected deleteAccount \(status) \(code) to throw", line: line)
        } catch let error as ProductAuthAPI.APIError {
            XCTAssertEqual(error, expectedError, line: line)
        } catch {
            XCTFail("Expected ProductAuthAPI.APIError, got \(error)", line: line)
        }
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
    }

    func onlyRequest() throws -> RecordedProductAuthRequest {
        XCTAssertEqual(requests.count, 1)
        return try XCTUnwrap(requests.first)
    }
}

private struct RecordedProductAuthRequest {
    var http: HTTPRequest
    var bodyText: String?
    var jsonBody: [String: String]?
    var operationID: String
}

private struct OfflineProductAuthTransportError: Error {}
