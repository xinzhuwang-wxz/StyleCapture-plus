import ComposableArchitecture
import Foundation

enum AuthClientError: Error, Equatable, Sendable {
    case authorizationCancelled
    case invalidAppleCredential
    case localCredentialPersistenceFailed
    case localCredentialCleanupRequired
    case sessionExpired
    case unavailable
}

struct AuthClient: Sendable {
    var restore: @Sendable () async throws -> AuthTokens?
    var authenticate: @Sendable (AppleSignInCredential, String) async throws -> AuthTokens
    var refresh: @Sendable () async throws -> AuthTokens
    var logout: @Sendable () async throws -> Void
    var deleteAccount: @Sendable () async throws -> Void
    var clearLocalCredentials: @Sendable () async throws -> Void
}

extension AuthClient: DependencyKey {
    static let liveValue = AuthClient.unavailable
    static let testValue = AuthClient.unavailable

    private static let unavailable = AuthClient(
        restore: { throw AuthClientError.unavailable },
        authenticate: { _, _ in throw AuthClientError.unavailable },
        refresh: { throw AuthClientError.unavailable },
        logout: { throw AuthClientError.unavailable },
        deleteAccount: { throw AuthClientError.unavailable },
        clearLocalCredentials: { throw AuthClientError.unavailable }
    )
}

extension DependencyValues {
    var authClient: AuthClient {
        get { self[AuthClient.self] }
        set { self[AuthClient.self] = newValue }
    }
}
