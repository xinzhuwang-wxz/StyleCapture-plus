import Foundation

struct AppleSignInRequest: Equatable, Sendable {
    var identityToken: String
    var authorizationCode: String
    var nonce: String
    var deviceName: String?
}

struct AuthTokens: Codable, Equatable, Sendable {
    var accountSubject: String
    var accessToken: String
    var refreshToken: String
    var accessExpiresAt: Date
    var tokenType: String
}

protocol TokenStore: Sendable {
    func load() async -> AuthTokens?
    func save(_ tokens: AuthTokens) async
    func clear() async
}

enum AuthSessionError: Error, Equatable {
    case missingToken
    case invalidCredentialPayload
}

struct AuthSession: Sendable {
    var tokenStore: any TokenStore
    var authenticateWithApple: @Sendable (AppleSignInRequest) async throws -> AuthTokens
    var refreshSession: @Sendable (String) async throws -> AuthTokens
    var requestAccountDeletion: @Sendable () async throws -> Void

    init(
        tokenStore: any TokenStore,
        authenticateWithApple: @escaping @Sendable (AppleSignInRequest) async throws -> AuthTokens,
        refreshSession: @escaping @Sendable (String) async throws -> AuthTokens,
        deleteAccount: @escaping @Sendable () async throws -> Void
    ) {
        self.tokenStore = tokenStore
        self.authenticateWithApple = authenticateWithApple
        self.refreshSession = refreshSession
        self.requestAccountDeletion = deleteAccount
    }

    @discardableResult
    func completeAppleSignIn(
        identityToken: String,
        authorizationCode: String,
        nonce: String,
        deviceName: String? = nil
    ) async throws -> AuthTokens {
        let tokens = try await authenticateWithApple(
            AppleSignInRequest(
                identityToken: identityToken,
                authorizationCode: authorizationCode,
                nonce: nonce,
                deviceName: deviceName
            )
        )
        await tokenStore.save(tokens)
        return tokens
    }

    @discardableResult
    func refresh() async throws -> AuthTokens {
        guard let current = await tokenStore.load() else {
            throw AuthSessionError.missingToken
        }
        let tokens = try await refreshSession(current.refreshToken)
        await tokenStore.save(tokens)
        return tokens
    }

    func logout() async {
        await tokenStore.clear()
    }

    func deleteAccount() async throws {
        try await requestAccountDeletion()
        await tokenStore.clear()
    }
}
