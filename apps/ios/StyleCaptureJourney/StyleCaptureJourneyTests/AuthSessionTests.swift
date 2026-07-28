import XCTest
@testable import StyleCaptureJourney

private let authTokensFixture = AuthTokens(
    accountSubject: "account-1",
    accessToken: "access-1",
    refreshToken: "refresh-1",
    accessExpiresAt: Date(timeIntervalSince1970: 1_785_200_000),
    tokenType: "Bearer"
)

final class AuthSessionTests: XCTestCase {
    func testSignInStoresServerTokensAndRefreshRotatesRefreshToken() async throws {
        let store = MemoryTokenStore()
        let refreshedToken = StringRecorder()
        let session = AuthSession(
            tokenStore: store,
            authenticateWithApple: { request in
                XCTAssertEqual(request.nonce, "nonce-1")
                return AuthTokens(
                    accountSubject: "account-1",
                    accessToken: "access-1",
                    refreshToken: "refresh-1",
                    accessExpiresAt: Date(timeIntervalSince1970: 1_785_200_000),
                    tokenType: "Bearer"
                )
            },
            refreshSession: { refreshToken in
                await refreshedToken.record(refreshToken)
                return AuthTokens(
                    accountSubject: "account-1",
                    accessToken: "access-2",
                    refreshToken: "refresh-2",
                    accessExpiresAt: Date(timeIntervalSince1970: 1_785_200_900),
                    tokenType: "Bearer"
                )
            },
            deleteAccount: { _ in }
        )

        let signedIn = try await session.completeAppleSignIn(
            identityToken: "identity",
            authorizationCode: "code",
            nonce: "nonce-1"
        )
        let refreshed = try await session.refresh()

        XCTAssertEqual(signedIn.accessToken, "access-1")
        XCTAssertEqual(refreshed.accessToken, "access-2")
        let recordedRefreshToken = await refreshedToken.value
        XCTAssertEqual(recordedRefreshToken, "refresh-1")
        let stored = try await store.load()
        XCTAssertEqual(stored, refreshed)
    }

    func testLogoutAndDeleteClearTokens() async throws {
        let store = MemoryTokenStore()
        try await store.save(
            AuthTokens(
                accountSubject: "account-1",
                accessToken: "access-1",
                refreshToken: "refresh-1",
                accessExpiresAt: Date(),
                tokenType: "Bearer"
            )
        )
        let deletion = DeletionRecorder()
        let session = AuthSession(
            tokenStore: store,
            authenticateWithApple: { _ in throw AuthSessionError.missingToken },
            refreshSession: { _ in throw AuthSessionError.missingToken },
            deleteAccount: { accessToken in await deletion.record(accessToken) }
        )

        try await session.logout()
        let afterLogout = try await store.load()
        XCTAssertNil(afterLogout)

        try await store.save(
            AuthTokens(
                accountSubject: "account-1",
                accessToken: "access-1",
                refreshToken: "refresh-1",
                accessExpiresAt: Date(),
                tokenType: "Bearer"
            )
        )
        try await session.deleteAccount()

        let didDelete = await deletion.didDelete
        XCTAssertTrue(didDelete)
        let deletedAccessToken = await deletion.accessToken
        XCTAssertEqual(deletedAccessToken, "access-1")
        let afterDeletion = try await store.load()
        XCTAssertNil(afterDeletion)
    }

    func testSignInFailsWhenSecureTokenPersistenceFails() async {
        let store = FailingTokenStore(failure: .save)
        let session = AuthSession(
            tokenStore: store,
            authenticateWithApple: { _ in authTokensFixture },
            refreshSession: { _ in authTokensFixture },
            deleteAccount: { _ in }
        )

        do {
            _ = try await session.completeAppleSignIn(
                identityToken: "identity",
                authorizationCode: "code",
                nonce: "nonce"
            )
            XCTFail("Sign-in must not complete when Keychain persistence fails")
        } catch {
            XCTAssertEqual(error as? TokenStoreTestFailure, .save)
        }
    }

    func testDeletionReportsLocalCredentialCleanupFailureAfterServerDeletion() async {
        let deletion = DeletionRecorder()
        let store = FailingTokenStore(failure: .clear)
        let session = AuthSession(
            tokenStore: store,
            authenticateWithApple: { _ in authTokensFixture },
            refreshSession: { _ in authTokensFixture },
            deleteAccount: { accessToken in await deletion.record(accessToken) }
        )

        do {
            try await session.deleteAccount()
            XCTFail("Deletion must expose a local credential cleanup failure")
        } catch {
            XCTAssertEqual(error as? TokenStoreTestFailure, .clear)
        }
        let didDelete = await deletion.didDelete
        XCTAssertTrue(didDelete)
    }

    func testDeletionWithoutStoredCredentialNeverCallsServer() async {
        let deletion = DeletionRecorder()
        let session = AuthSession(
            tokenStore: MemoryTokenStore(),
            authenticateWithApple: { _ in authTokensFixture },
            refreshSession: { _ in authTokensFixture },
            deleteAccount: { accessToken in await deletion.record(accessToken) }
        )

        do {
            try await session.deleteAccount()
            XCTFail("Deletion must require an authenticated local session")
        } catch {
            XCTAssertEqual(error as? AuthSessionError, .missingToken)
        }
        let didDelete = await deletion.didDelete
        XCTAssertFalse(didDelete)
    }
}

private actor MemoryTokenStore: TokenStore {
    private var tokens: AuthTokens?

    func load() throws -> AuthTokens? {
        tokens
    }

    func save(_ tokens: AuthTokens) throws {
        self.tokens = tokens
    }

    func clear() throws {
        tokens = nil
    }
}

private enum TokenStoreTestFailure: Error, Equatable {
    case load
    case save
    case clear
}

private actor FailingTokenStore: TokenStore {
    let failure: TokenStoreTestFailure

    init(failure: TokenStoreTestFailure) {
        self.failure = failure
    }

    func load() throws -> AuthTokens? {
        if failure == .load { throw failure }
        return authTokensFixture
    }

    func save(_ tokens: AuthTokens) throws {
        if failure == .save { throw failure }
    }

    func clear() throws {
        if failure == .clear { throw failure }
    }
}

private actor DeletionRecorder {
    private(set) var accessToken: String?

    var didDelete: Bool {
        accessToken != nil
    }

    func record(_ accessToken: String) {
        self.accessToken = accessToken
    }
}

private actor StringRecorder {
    private(set) var value: String?

    func record(_ value: String) {
        self.value = value
    }
}
