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

struct AuthenticatedAccount: Equatable, Sendable {
    var accessExpiresAt: Date
    var appleUserIdentifier: String?
}

enum StoredAuthSession: Equatable, Sendable {
    case signedOut
    case authenticated(AuthTokens)
    case accountDeletionPending(AccountDeletionIntent)
}

enum AccountDeletionIntentPhase: String, Codable, Equatable, Sendable {
    case pendingSubmission
    case accepted
}

struct AccountDeletionIntent: Codable, Equatable, Sendable {
    var idempotencyKey: String
    var phase: AccountDeletionIntentPhase

    init(
        idempotencyKey: String = UUID().uuidString,
        phase: AccountDeletionIntentPhase = .pendingSubmission
    ) {
        self.idempotencyKey = idempotencyKey
        self.phase = phase
    }
}

enum AccountDeletionStatus: Equatable, Sendable {
    case accepted
}

struct AccountDeletionAcknowledgement: Equatable, Sendable {
    var status: AccountDeletionStatus
}

extension AuthTokens {
    var authenticatedAccount: AuthenticatedAccount {
        AuthenticatedAccount(
            accessExpiresAt: accessExpiresAt,
            appleUserIdentifier: appleUserIdentifier
        )
    }
}

protocol TokenStore: Sendable {
    func load() async throws -> StoredAuthSession
    func save(_ tokens: AuthTokens) async throws
    func loadTokensForAccountDeletionRetry() async throws -> AuthTokens?
    func markAccountDeletionPending() async throws -> AccountDeletionIntent
    func markAccountDeletionAccepted(_ intent: AccountDeletionIntent) async throws
    func clear() async throws
}
