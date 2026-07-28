import AuthenticationServices
import Foundation
import XCTest
@testable import StyleCaptureJourney

final class AppleSignInLiveTests: XCTestCase {
    func testAuthorizeRequestsFullNameEmailAndNonceThenReturnsCredentialStrings() async throws {
        let session = CapturingAuthorizationSession { request in
            XCTAssertEqual(request.scopes, [.fullName, .email])
            XCTAssertEqual(request.nonce, "sha256-nonce")
            return .appleID(
                identityToken: Data("identity-token".utf8),
                authorizationCode: Data("authorization-code".utf8)
            )
        }
        let client = AppleSignInClient.live(authorizationSession: session)

        let credential = try await client.authorize("sha256-nonce")

        XCTAssertEqual(
            session.capturedRequests,
            [AppleSignInAuthorizationRequest(scopes: [.fullName, .email], nonce: "sha256-nonce")]
        )
        XCTAssertEqual(credential.identityToken, "identity-token")
        XCTAssertEqual(credential.authorizationCode, "authorization-code")
    }

    func testAuthorizeMapsAppleCancellationDistinctly() async throws {
        let session = CapturingAuthorizationSession { _ in
            throw NSError(
                domain: ASAuthorizationError.errorDomain,
                code: ASAuthorizationError.canceled.rawValue
            )
        }
        let client = AppleSignInClient.live(authorizationSession: session)

        await XCTAssertThrowsErrorAsync(try await client.authorize("sha256-nonce")) { error in
            XCTAssertEqual(error as? AuthClientError, .authorizationCancelled)
        }
    }

    func testAuthorizeFailsClosedForWrongCredentialType() async throws {
        let session = CapturingAuthorizationSession { _ in
            .unsupportedCredential
        }
        let client = AppleSignInClient.live(authorizationSession: session)

        await XCTAssertThrowsErrorAsync(try await client.authorize("sha256-nonce")) { error in
            XCTAssertEqual(error as? AuthClientError, .invalidAppleCredential)
        }
    }

    func testAuthorizeFailsClosedWhenIdentityTokenIsMissing() async throws {
        let session = CapturingAuthorizationSession { _ in
            .appleID(
                identityToken: nil,
                authorizationCode: Data("authorization-code".utf8)
            )
        }
        let client = AppleSignInClient.live(authorizationSession: session)

        await XCTAssertThrowsErrorAsync(try await client.authorize("sha256-nonce")) { error in
            XCTAssertEqual(error as? AuthClientError, .invalidAppleCredential)
        }
    }

    func testAuthorizeFailsClosedWhenAuthorizationCodeIsMissing() async throws {
        let session = CapturingAuthorizationSession { _ in
            .appleID(
                identityToken: Data("identity-token".utf8),
                authorizationCode: nil
            )
        }
        let client = AppleSignInClient.live(authorizationSession: session)

        await XCTAssertThrowsErrorAsync(try await client.authorize("sha256-nonce")) { error in
            XCTAssertEqual(error as? AuthClientError, .invalidAppleCredential)
        }
    }

    func testAuthorizeFailsClosedWhenIdentityTokenIsNotUTF8() async throws {
        let session = CapturingAuthorizationSession { _ in
            .appleID(
                identityToken: Data([0xff, 0xfe]),
                authorizationCode: Data("authorization-code".utf8)
            )
        }
        let client = AppleSignInClient.live(authorizationSession: session)

        await XCTAssertThrowsErrorAsync(try await client.authorize("sha256-nonce")) { error in
            XCTAssertEqual(error as? AuthClientError, .invalidAppleCredential)
        }
    }

    func testAuthorizeFailsClosedWhenAuthorizationCodeIsNotUTF8() async throws {
        let session = CapturingAuthorizationSession { _ in
            .appleID(
                identityToken: Data("identity-token".utf8),
                authorizationCode: Data([0xff, 0xfe])
            )
        }
        let client = AppleSignInClient.live(authorizationSession: session)

        await XCTAssertThrowsErrorAsync(try await client.authorize("sha256-nonce")) { error in
            XCTAssertEqual(error as? AuthClientError, .invalidAppleCredential)
        }
    }
}

private final class CapturingAuthorizationSession: AppleSignInAuthorizationSession, @unchecked Sendable {
    private let authorizeHandler: @Sendable (AppleSignInAuthorizationRequest) async throws
        -> AppleSignInAuthorizationCredential

    private(set) var capturedRequests: [AppleSignInAuthorizationRequest] = []

    init(
        authorizeHandler: @escaping @Sendable (AppleSignInAuthorizationRequest) async throws
            -> AppleSignInAuthorizationCredential
    ) {
        self.authorizeHandler = authorizeHandler
    }

    func authorize(
        _ request: AppleSignInAuthorizationRequest
    ) async throws -> AppleSignInAuthorizationCredential {
        capturedRequests.append(request)
        return try await authorizeHandler(request)
    }
}

private func XCTAssertThrowsErrorAsync<T>(
    _ expression: @autoclosure () async throws -> T,
    _ verify: (Error) -> Void,
    file: StaticString = #filePath,
    line: UInt = #line
) async {
    do {
        _ = try await expression()
        XCTFail("Expected error to be thrown", file: file, line: line)
    } catch {
        verify(error)
    }
}
