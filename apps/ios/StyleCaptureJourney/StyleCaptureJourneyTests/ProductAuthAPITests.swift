import Foundation
import HTTPTypes
import OpenAPIRuntime
import XCTest
@testable import StyleCaptureAPI
@testable import StyleCaptureJourney

final class ProductAuthAPITests: XCTestCase {
    func testBearerMiddlewareAddsAuthorizationHeader() async throws {
        let middleware = BearerAuthorizationMiddleware(accessToken: "access-token")
        let request = HTTPRequest(
            method: .delete,
            scheme: "https",
            authority: "api.stylecapture.test",
            path: "/v1/account"
        )

        _ = try await middleware.intercept(
            request,
            body: nil,
            baseURL: URL(string: "https://api.stylecapture.test")!,
            operationID: "delete_account_v1_account_delete_post"
        ) { forwardedRequest, _, _ in
            XCTAssertEqual(
                forwardedRequest.headerFields[.authorization],
                "Bearer access-token"
            )
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
