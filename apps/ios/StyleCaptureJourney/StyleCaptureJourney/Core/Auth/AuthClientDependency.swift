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
    case accountDeletionReconciliationRequired
    case sessionExpired
    case unavailable
}

struct AuthClient: Sendable {
    var restore: @Sendable () async throws -> AuthenticatedAccount?
    var authenticate: @Sendable (AppleSignInCredential, String) async throws -> AuthenticatedAccount
    var refresh: @Sendable () async throws -> AuthenticatedAccount
    var logout: @Sendable () async throws -> Void
    var deleteAccount: @Sendable () async throws -> AccountDeletionAcknowledgement
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
                    switch try await tokenStore.load() {
                    case .signedOut:
                        return nil
                    case let .authenticated(tokens):
                        return tokens.authenticatedAccount
                    case .accountDeletionPending:
                        throw AuthClientError.accountDeletionReconciliationRequired
                    }
                } catch is CancellationError {
                    throw CancellationError()
                } catch let error as AuthClientError {
                    throw error
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
                } catch is CancellationError {
                    throw CancellationError()
                } catch {
                    throw Self.mapAuthenticateError(error)
                }
                tokens.appleUserIdentifier = credential.userIdentifier

                do {
                    try await tokenStore.save(tokens)
                    return tokens.authenticatedAccount
                } catch is CancellationError {
                    throw CancellationError()
                } catch {
                    throw AuthClientError.localCredentialPersistenceFailed
                }
            },
            refresh: {
                let current: AuthTokens
                do {
                    guard case let .authenticated(stored) = try await tokenStore.load() else {
                        throw AuthClientError.sessionExpired
                    }
                    current = stored
                } catch is CancellationError {
                    throw CancellationError()
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
                } catch is CancellationError {
                    throw CancellationError()
                } catch let error as AuthClientError {
                    throw error
                } catch {
                    throw Self.mapProductAuthError(error, serverUnavailable: .serviceUnavailable)
                }
                tokens.appleUserIdentifier = current.appleUserIdentifier

                do {
                    try await tokenStore.save(tokens)
                    return tokens.authenticatedAccount
                } catch is CancellationError {
                    throw CancellationError()
                } catch {
                    throw AuthClientError.localCredentialPersistenceFailed
                }
            },
            logout: {
                try await Self.clear(tokenStore)
            },
            deleteAccount: {
                let current: AuthTokens
                let intent: AccountDeletionIntent
                do {
                    switch try await tokenStore.load() {
                    case let .authenticated(stored):
                        current = stored
                        intent = try await tokenStore.markAccountDeletionPending()
                    case let .accountDeletionPending(storedIntent):
                        guard let stored = try await tokenStore.loadTokensForAccountDeletionRetry() else {
                            throw AuthClientError.localCredentialCleanupRequired
                        }
                        current = stored
                        intent = storedIntent
                    case .signedOut:
                        throw AuthClientError.sessionExpired
                    }
                } catch is CancellationError {
                    throw CancellationError()
                } catch let error as AuthClientError {
                    throw error
                } catch {
                    throw AuthClientError.localCredentialPersistenceFailed
                }

                let acknowledgement: AccountDeletionAcknowledgement
                do {
                    acknowledgement = try await productAuthAPI.deleteAccount(
                        accessToken: current.accessToken,
                        idempotencyKey: intent.idempotencyKey
                    )
                } catch is CancellationError {
                    throw CancellationError()
                } catch ProductAuthAPI.APIError.unexpectedResponse {
                    throw AuthClientError.accountDeletionReconciliationRequired
                } catch {
                    throw Self.mapProductAuthError(error, serverUnavailable: .serviceUnavailable)
                }

                do {
                    try await tokenStore.markAccountDeletionAccepted(intent)
                } catch is CancellationError {
                    throw CancellationError()
                } catch {
                    throw AuthClientError.localCredentialCleanupRequired
                }
                return acknowledgement
            },
            clearLocalCredentials: {
                try await Self.clear(tokenStore)
            }
        )
    }

    private static func clear(_ tokenStore: any TokenStore) async throws {
        do {
            try await tokenStore.clear()
        } catch is CancellationError {
            throw CancellationError()
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
