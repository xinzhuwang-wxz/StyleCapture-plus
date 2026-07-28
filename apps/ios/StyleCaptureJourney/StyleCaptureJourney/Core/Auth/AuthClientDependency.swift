import ComposableArchitecture
import Foundation

enum AuthClientError: Error, Equatable, Sendable {
    case authorizationCancelled
    case invalidAppleCredential
    case authorizationUnavailable
    case requestRejected
    case accountConflict
    case serviceUnavailable
    case invalidResponse
    case networkUnavailable
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

extension AuthClient {
    static func live(
        productAuthAPI: ProductAuthAPI,
        tokenStore: any TokenStore,
        deviceName: @escaping @Sendable () -> String?
    ) -> AuthClient {
        AuthClient(
            restore: {
                do {
                    return try await tokenStore.load()
                } catch {
                    throw AuthClientError.localCredentialPersistenceFailed
                }
            },
            authenticate: { credential, nonce in
                var tokens: AuthTokens
                do {
                    tokens = try await productAuthAPI.authenticate(
                        AppleSignInRequest(
                            identityToken: credential.identityToken,
                            authorizationCode: credential.authorizationCode,
                            nonce: nonce,
                            deviceName: deviceName()
                        )
                    )
                } catch {
                    throw Self.mapAuthenticateError(error)
                }
                tokens.appleUserIdentifier = credential.userIdentifier

                do {
                    try await tokenStore.save(tokens)
                    return tokens
                } catch {
                    throw AuthClientError.localCredentialPersistenceFailed
                }
            },
            refresh: {
                let current: AuthTokens
                do {
                    guard let stored = try await tokenStore.load() else {
                        throw AuthClientError.sessionExpired
                    }
                    current = stored
                } catch let error as AuthClientError {
                    throw error
                } catch {
                    throw AuthClientError.localCredentialPersistenceFailed
                }

                var tokens: AuthTokens
                do {
                    tokens = try await productAuthAPI.refresh(
                        refreshToken: current.refreshToken
                    )
                } catch {
                    throw Self.mapProductAuthError(error, serverUnavailable: .serviceUnavailable)
                }
                tokens.appleUserIdentifier = current.appleUserIdentifier

                do {
                    try await tokenStore.save(tokens)
                    return tokens
                } catch {
                    throw AuthClientError.localCredentialPersistenceFailed
                }
            },
            logout: {
                try await Self.clear(tokenStore)
            },
            deleteAccount: {
                let current: AuthTokens
                do {
                    guard let stored = try await tokenStore.load() else {
                        throw AuthClientError.sessionExpired
                    }
                    current = stored
                } catch let error as AuthClientError {
                    throw error
                } catch {
                    throw AuthClientError.localCredentialPersistenceFailed
                }

                do {
                    try await productAuthAPI.deleteAccount(
                        accessToken: current.accessToken
                    )
                } catch {
                    throw Self.mapProductAuthError(error, serverUnavailable: .serviceUnavailable)
                }

                try await Self.clear(tokenStore)
            },
            clearLocalCredentials: {
                try await Self.clear(tokenStore)
            }
        )
    }

    private static func clear(_ tokenStore: any TokenStore) async throws {
        do {
            try await tokenStore.clear()
        } catch {
            throw AuthClientError.localCredentialCleanupRequired
        }
    }

    private static func mapAuthenticateError(_ error: any Error) -> AuthClientError {
        mapProductAuthError(error, serverUnavailable: .authorizationUnavailable)
    }

    private static func mapProductAuthError(
        _ error: any Error,
        serverUnavailable: AuthClientError
    ) -> AuthClientError {
        guard let apiError = error as? ProductAuthAPI.APIError else {
            return .unavailable
        }
        switch apiError {
        case .invalidCredential:
            return .invalidAppleCredential
        case .sessionExpired:
            return .sessionExpired
        case .invalidRequest:
            return .requestRejected
        case .conflict:
            return .accountConflict
        case .serverUnavailable:
            return serverUnavailable
        case .unexpectedResponse:
            return .invalidResponse
        case .transportFailure:
            return .networkUnavailable
        }
    }
}

extension AuthClient: DependencyKey {
    static let liveValue = AuthClient.live(
        productAuthAPI: .live,
        tokenStore: KeychainTokenStore(),
        deviceName: { nil }
    )
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
