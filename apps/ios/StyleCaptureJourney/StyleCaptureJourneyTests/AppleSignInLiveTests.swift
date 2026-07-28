import AuthenticationServices
import Foundation
import XCTest
@testable import StyleCaptureJourney

final class AppleSignInLiveTests: XCTestCase {
    func testTestValueFailsClosedWithoutStartingLiveAppleAuthorization() async throws {
        await XCTAssertThrowsErrorAsync(try await AppleSignInClient.testValue.authorize("sha256-nonce")) { error in
            XCTAssertEqual(error as? AuthClientError, .unavailable)
        }
    }

    func testAuthorizeRequestsOnlyNonceThenReturnsCredentialStringsAndUserIdentifier() async throws {
        let session = CapturingAuthorizationSession { request in
            XCTAssertEqual(request.scopes, [])
            XCTAssertEqual(request.nonce, "sha256-nonce")
            return .appleID(
                userIdentifier: "apple-user-123",
                identityToken: Data("identity-token".utf8),
                authorizationCode: Data("authorization-code".utf8)
            )
        }
        let client = AppleSignInClient.live(authorizationSession: session)

        let credential = try await client.authorize("sha256-nonce")

        XCTAssertEqual(
            session.capturedRequests,
            [AppleSignInAuthorizationRequest(scopes: [], nonce: "sha256-nonce")]
        )
        XCTAssertEqual(credential.userIdentifier, "apple-user-123")
        XCTAssertEqual(credential.identityToken, "identity-token")
        XCTAssertEqual(credential.authorizationCode, "authorization-code")
    }

    func testAuthorizePreservesProgrammaticCancellation() async throws {
        let session = CapturingAuthorizationSession { _ in
            throw CancellationError()
        }
        let client = AppleSignInClient.live(authorizationSession: session)

        await XCTAssertThrowsErrorAsync(try await client.authorize("sha256-nonce")) { error in
            XCTAssertTrue(error is CancellationError)
            XCTAssertNil(error as? AuthClientError)
        }
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

    func testAuthorizeMapsUnavailableAppleAuthorizationErrorsDistinctly() async throws {
        for code in [
            ASAuthorizationError.unknown,
            .notHandled,
            .notInteractive,
        ] {
            let session = CapturingAuthorizationSession { _ in
                throw NSError(
                    domain: ASAuthorizationError.errorDomain,
                    code: code.rawValue
                )
            }
            let client = AppleSignInClient.live(authorizationSession: session)

            await XCTAssertThrowsErrorAsync(try await client.authorize("sha256-nonce")) { error in
                XCTAssertEqual(error as? AuthClientError, .authorizationUnavailable)
            }
        }
    }

    func testAuthorizeDoesNotReturnCredentialAfterProgrammaticTaskCancellation() async throws {
        let session = DelayedCredentialSession()
        let client = AppleSignInClient.live(authorizationSession: session)
        let task = Task {
            try await client.authorize("sha256-nonce")
        }

        await session.waitUntilAuthorizeStarted()
        task.cancel()
        await session.returnCredentialAfterCancellation()

        await XCTAssertThrowsErrorAsync(try await task.value) { error in
            XCTAssertTrue(error is CancellationError)
            XCTAssertNil(error as? AuthClientError)
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
                userIdentifier: "apple-user-123",
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
                userIdentifier: "apple-user-123",
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
                userIdentifier: "apple-user-123",
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
                userIdentifier: "apple-user-123",
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

private actor DelayedCredentialSession: AppleSignInAuthorizationSession {
    private var authorizeStarted = false
    private var shouldReturnCredential = false
    private var waiters: [CheckedContinuation<Void, Never>] = []
    private var returnWaiters: [CheckedContinuation<Void, Never>] = []

    func authorize(
        _ request: AppleSignInAuthorizationRequest
    ) async throws -> AppleSignInAuthorizationCredential {
        authorizeStarted = true
        waiters.forEach { $0.resume() }
        waiters.removeAll()

        await withCheckedContinuation { continuation in
            if shouldReturnCredential {
                continuation.resume()
            } else {
                returnWaiters.append(continuation)
            }
        }

        return .appleID(
            userIdentifier: "late-apple-user",
            identityToken: Data("late-identity-token".utf8),
            authorizationCode: Data("late-authorization-code".utf8)
        )
    }

    func waitUntilAuthorizeStarted() async {
        await withCheckedContinuation { continuation in
            if authorizeStarted {
                continuation.resume()
            } else {
                waiters.append(continuation)
            }
        }
    }

    func returnCredentialAfterCancellation() {
        shouldReturnCredential = true
        returnWaiters.forEach { $0.resume() }
        returnWaiters.removeAll()
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
