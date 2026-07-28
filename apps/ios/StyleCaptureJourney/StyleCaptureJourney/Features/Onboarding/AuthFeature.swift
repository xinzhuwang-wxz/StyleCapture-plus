import ComposableArchitecture
import Foundation

@Reducer
struct AuthFeature {
    @ObservableState
    struct State: Equatable {
        var phase: Phase = .restoring
    }

    enum Phase: Equatable {
        case restoring
        case signedOut
        case signingIn
        case signedIn(AuthTokens)
        case signingOut
        case confirmingAccountDeletion(AuthTokens)
        case deleting
        case clearingLocalCredentials
        case localCredentialCleanupRequired
        case failed(AuthClientError)
    }

    enum RestoreResponse: Equatable {
        case signedOut
        case signedIn(AuthTokens)
        case failure(AuthClientError)
    }

    enum SessionResponse: Equatable {
        case success(AuthTokens)
        case failure(AuthClientError)
    }

    enum OperationResponse: Equatable {
        case success
        case failure(AuthClientError)
    }

    enum Action: Equatable {
        case task
        case restoreResponse(RestoreResponse)
        case signInButtonTapped
        case retrySignInTapped
        case signInResponse(SessionResponse)
        case logoutButtonTapped
        case logoutResponse(OperationResponse)
        case deleteAccountButtonTapped
        case cancelDeleteAccountTapped
        case confirmDeleteAccountTapped
        case deleteAccountResponse(OperationResponse)
        case retryLocalCleanupTapped
        case localCleanupResponse(OperationResponse)
        case credentialRevokedNotification
        case credentialRevocationCleanupResponse(OperationResponse)
    }

    private enum CancellationID: Hashable {
        case signIn
        case credentialRevocationNotifications
    }

    @Dependency(\.authClient) var authClient
    @Dependency(\.appleSignInClient) var appleSignInClient
    @Dependency(\.appleSignInNonce) var appleSignInNonce
    @Dependency(\.appleCredentialStateClient) var appleCredentialStateClient
    @Dependency(\.date.now) var now

    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .task:
                return restore()

            case .restoreResponse(.signedOut):
                state.phase = .signedOut
                return .none

            case let .restoreResponse(.signedIn(tokens)):
                state.phase = .signedIn(tokens)
                return credentialRevocationNotifications()

            case let .restoreResponse(.failure(error)):
                state.phase = .failed(error)
                return .none

            case .signInButtonTapped, .retrySignInTapped:
                state.phase = .signingIn
                return signIn()

            case let .signInResponse(.success(tokens)):
                state.phase = .signedIn(tokens)
                return credentialRevocationNotifications()

            case .signInResponse(.failure(.authorizationCancelled)):
                state.phase = .signedOut
                return .none

            case let .signInResponse(.failure(error)):
                state.phase = .failed(error)
                return .none

            case .deleteAccountButtonTapped:
                switch state.phase {
                case let .signedIn(tokens):
                    state.phase = .confirmingAccountDeletion(tokens)
                default:
                    return .none
                }
                return .none

            case .cancelDeleteAccountTapped:
                if case let .confirmingAccountDeletion(tokens) = state.phase {
                    state.phase = .signedIn(tokens)
                }
                return .none

            case .confirmDeleteAccountTapped:
                guard case .confirmingAccountDeletion = state.phase else {
                    return .none
                }
                state.phase = .deleting
                return .run { send in
                    do {
                        try await authClient.deleteAccount()
                        await send(.deleteAccountResponse(.success))
                    } catch {
                        await send(.deleteAccountResponse(.failure(Self.map(error))))
                    }
                }

            case .deleteAccountResponse(.success):
                state.phase = .signedOut
                return .cancel(id: CancellationID.credentialRevocationNotifications)

            case .deleteAccountResponse(.failure(.localCredentialCleanupRequired)):
                state.phase = .localCredentialCleanupRequired
                return .none

            case let .deleteAccountResponse(.failure(error)):
                state.phase = .failed(error)
                return .none

            case .logoutButtonTapped:
                state.phase = .signingOut
                return .run { send in
                    do {
                        try await authClient.logout()
                        await send(.logoutResponse(.success))
                    } catch {
                        await send(.logoutResponse(.failure(Self.map(error))))
                    }
                }

            case .logoutResponse(.success):
                state.phase = .signedOut
                return .cancel(id: CancellationID.credentialRevocationNotifications)

            case let .logoutResponse(.failure(error)):
                state.phase = .failed(error)
                return .none

            case .retryLocalCleanupTapped:
                state.phase = .clearingLocalCredentials
                return .run { send in
                    do {
                        try await authClient.clearLocalCredentials()
                        await send(.localCleanupResponse(.success))
                    } catch {
                        await send(.localCleanupResponse(.failure(Self.map(error))))
                    }
                }

            case .localCleanupResponse(.success):
                state.phase = .signedOut
                return .cancel(id: CancellationID.credentialRevocationNotifications)

            case let .localCleanupResponse(.failure(error)):
                state.phase = error == .localCredentialCleanupRequired
                    ? .localCredentialCleanupRequired
                    : .failed(error)
                return .none

            case .credentialRevokedNotification:
                guard state.phase.isAuthenticated else {
                    return .none
                }
                state.phase = .clearingLocalCredentials
                return clearRevokedCredential()

            case .credentialRevocationCleanupResponse(.success):
                state.phase = .signedOut
                return .cancel(id: CancellationID.credentialRevocationNotifications)

            case let .credentialRevocationCleanupResponse(.failure(error)):
                state.phase = error == .localCredentialCleanupRequired
                    ? .localCredentialCleanupRequired
                    : .failed(error)
                return .none
            }
        }
    }

    private func restore() -> Effect<Action> {
        .run { send in
            do {
                guard let restoredTokens = try await authClient.restore() else {
                    await send(.restoreResponse(.signedOut))
                    return
                }

                guard try await credentialIsStillValid(for: restoredTokens) else {
                    try await authClient.logout()
                    await send(.restoreResponse(.signedOut))
                    return
                }

                if restoredTokens.accessExpiresAt <= now {
                    let refreshedTokens = try await authClient.refresh()
                    await send(.restoreResponse(.signedIn(refreshedTokens)))
                } else {
                    await send(.restoreResponse(.signedIn(restoredTokens)))
                }
            } catch {
                await send(.restoreResponse(.failure(Self.map(error))))
            }
        }
    }

    private func signIn() -> Effect<Action> {
        .run { send in
            do {
                let nonce = try appleSignInNonce.generate()
                let credential = try await appleSignInClient.authorize(nonce.hashedValue)
                try Task.checkCancellation()
                let tokens = try await authClient.authenticate(credential, nonce.rawValue)
                await send(.signInResponse(.success(tokens)))
            } catch is CancellationError {
                return
            } catch {
                await send(.signInResponse(.failure(Self.map(error))))
            }
        }
        .cancellable(id: CancellationID.signIn, cancelInFlight: true)
    }

    private static func map(_ error: any Error) -> AuthClientError {
        error as? AuthClientError ?? .unavailable
    }

    private func credentialIsStillValid(for tokens: AuthTokens) async throws -> Bool {
        guard let userIdentifier = tokens.appleUserIdentifier else {
            return true
        }

        switch await appleCredentialStateClient.credentialState(userIdentifier) {
        case .authorized, .unavailable:
            return true
        case .revoked, .notFound, .transferred:
            return false
        }
    }

    private func credentialRevocationNotifications() -> Effect<Action> {
        .run { send in
            for await _ in appleCredentialStateClient.revocationEvents() {
                await send(.credentialRevokedNotification)
            }
        }
        .cancellable(
            id: CancellationID.credentialRevocationNotifications,
            cancelInFlight: true
        )
    }

    private func clearRevokedCredential() -> Effect<Action> {
        .run { send in
            do {
                try await authClient.logout()
                await send(.credentialRevocationCleanupResponse(.success))
            } catch {
                await send(.credentialRevocationCleanupResponse(.failure(Self.map(error))))
            }
        }
    }
}

private extension AuthFeature.Phase {
    var isAuthenticated: Bool {
        switch self {
        case .signedIn, .confirmingAccountDeletion:
            return true
        case .restoring,
             .signedOut,
             .signingIn,
             .signingOut,
             .deleting,
             .clearingLocalCredentials,
             .localCredentialCleanupRequired,
             .failed:
            return false
        }
    }
}
