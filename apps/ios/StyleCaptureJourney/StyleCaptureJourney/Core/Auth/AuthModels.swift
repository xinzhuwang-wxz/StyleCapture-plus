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
    var appleUserIdentifier: String?

    init(
        accountSubject: String,
        accessToken: String,
        refreshToken: String,
        accessExpiresAt: Date,
        tokenType: String,
        appleUserIdentifier: String? = nil
    ) {
        self.accountSubject = accountSubject
        self.accessToken = accessToken
        self.refreshToken = refreshToken
        self.accessExpiresAt = accessExpiresAt
        self.tokenType = tokenType
        self.appleUserIdentifier = appleUserIdentifier
    }
}

protocol TokenStore: Sendable {
    func load() async throws -> AuthTokens?
    func save(_ tokens: AuthTokens) async throws
    func clear() async throws
}
