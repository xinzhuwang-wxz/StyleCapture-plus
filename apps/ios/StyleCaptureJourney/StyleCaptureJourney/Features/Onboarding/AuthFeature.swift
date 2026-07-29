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
        case signedIn(AuthenticatedAccount)
        case signingOut
        case confirmingAccountDeletion(AuthenticatedAccount)
        case deleting(AuthenticatedAccount)
        case accountDeletionReconciliationRequired
        case resubmittingAccountDeletion
        case clearingLocalCredentials(AccountDeletionStatus?)
        case localCredentialCleanupRequired(AccountDeletionStatus?)
        case failed(AuthClientError)
    }

    enum RestoreResponse: Equatable {
        case signedOut
        case signedIn(AuthenticatedAccount)
        case failure(AuthClientError)
    }

    enum SessionResponse: Equatable {
        case success(AuthenticatedAccount)
        case failure(AuthClientError)
    }

    enum DeleteAccountResponse: Equatable {
        case success(AccountDeletionAcknowledgement)
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
        case retryAccountDeletionTapped
        case deleteAccountResponse(DeleteAccountResponse)
        case retryLocalCleanupTapped
        case localCleanupResponse(OperationResponse)
        case credentialRevokedNotification
        case credentialRevocationCleanupResponse(OperationResponse)
    }

    private enum CancellationID: Hashable {
        case restore
        case signIn
        case localCredentialCleanup
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
                guard state.phase == .restoring else {
                    return .none
                }
                state.phase = .signedOut
                return .none

            case let .restoreResponse(.signedIn(account)):
                guard state.phase == .restoring else {
                    return .none
                }
                state.phase = .signedIn(account)
                return credentialRevocationNotifications()

            case .restoreResponse(.failure(.localCredentialCleanupRequired)):
                guard state.phase == .restoring else {
                    return .none
                }
                state.phase = .localCredentialCleanupRequired(nil)
                return .none

            case .restoreResponse(.failure(.accountDeletionReconciliationRequired)):
                guard state.phase == .restoring else {
                    return .none
                }
                state.phase = .accountDeletionReconciliationRequired
                return .none

            case let .restoreResponse(.failure(error)):
                guard state.phase == .restoring else {
                    return .none
                }
                state.phase = .failed(error)
                return .none

            case .signInButtonTapped, .retrySignInTapped:
                state.phase = .signingIn
                return .merge(
                    .cancel(id: CancellationID.restore),
                    signIn()
                )

            case let .signInResponse(.success(account)):
                state.phase = .signedIn(account)
                return credentialRevocationNotifications()

            case .signInResponse(.failure(.authorizationCancelled)):
                state.phase = .signedOut
                return .none

            case let .signInResponse(.failure(error)):
                state.phase = .failed(error)
                return .none

            case .deleteAccountButtonTapped:
                switch state.phase {
                case let .signedIn(account):
                    state.phase = .confirmingAccountDeletion(account)
                default:
                    return .none
                }
                return .none

            case .cancelDeleteAccountTapped:
                if case let .confirmingAccountDeletion(account) = state.phase {
                    state.phase = .signedIn(account)
                }
                return .none

            case .confirmDeleteAccountTapped:
                guard case let .confirmingAccountDeletion(account) = state.phase else {
                    return .none
                }
                state.phase = .deleting(account)
                return submitAccountDeletion()

            case .retryAccountDeletionTapped:
                guard case .accountDeletionReconciliationRequired = state.phase else {
                    return .none
                }
                state.phase = .resubmittingAccountDeletion
                return submitAccountDeletion()

            case let .deleteAccountResponse(.success(acknowledgement)):
                state.phase = .clearingLocalCredentials(acknowledgement.status)
                return clearLocalCredentials()

            case .deleteAccountResponse(.failure(.localCredentialCleanupRequired)):
                state.phase = .localCredentialCleanupRequired(nil)
                return .none

            case .deleteAccountResponse(.failure(.networkUnavailable)),
                 .deleteAccountResponse(.failure(.serviceUnavailable)),
                 .deleteAccountResponse(.failure(.accountDeletionReconciliationRequired)):
                state.phase = .accountDeletionReconciliationRequired
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
                    } catch is CancellationError {
                        return
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
                let status = state.phase.accountDeletionStatus
                state.phase = .clearingLocalCredentials(status)
                return clearLocalCredentials()

            case .localCleanupResponse(.success):
                state.phase = .signedOut
                return .cancel(id: CancellationID.credentialRevocationNotifications)

            case let .localCleanupResponse(.failure(error)):
                state.phase = error == .localCredentialCleanupRequired
                    ? .localCredentialCleanupRequired(state.phase.accountDeletionStatus)
                    : .failed(error)
                return .none

            case .credentialRevokedNotification:
                guard state.phase.isAuthenticated else {
                    return .none
                }
                state.phase = .clearingLocalCredentials(nil)
                return clearRevokedCredential()

            case .credentialRevocationCleanupResponse(.success):
                state.phase = .signedOut
                return .cancel(id: CancellationID.credentialRevocationNotifications)

            case let .credentialRevocationCleanupResponse(.failure(error)):
                state.phase = error == .localCredentialCleanupRequired
                    ? .localCredentialCleanupRequired(nil)
                    : .failed(error)
                return .none
            }
        }
    }

    private func restore() -> Effect<Action> {
        .run { send in
            do {
                guard let restoredAccount = try await authClient.restore() else {
                    await send(.restoreResponse(.signedOut))
                    return
                }

                guard try await authClient.storedAppleCredentialIsValid() else {
                    try await authClient.logout()
                    await send(.restoreResponse(.signedOut))
                    return
                }

                if restoredAccount.accessExpiresAt <= now {
                    let refreshedTokens = try await authClient.refresh()
                    await send(.restoreResponse(.signedIn(refreshedTokens)))
                } else {
                    await send(.restoreResponse(.signedIn(restoredAccount)))
                }
            } catch is CancellationError {
                return
            } catch {
                await send(.restoreResponse(.failure(Self.map(error))))
            }
        }
        .cancellable(id: CancellationID.restore, cancelInFlight: true)
    }

    private func signIn() -> Effect<Action> {
        .run { send in
            do {
                let nonce = try appleSignInNonce.generate()
                let credential = try await appleSignInClient.authorize(nonce.hashedValue)
                try Task.checkCancellation()
                let account = try await authClient.authenticate(credential, nonce.rawValue)
                await send(.signInResponse(.success(account)))
            } catch is CancellationError {
                return
            } catch {
                await send(.signInResponse(.failure(Self.map(error))))
            }
        }
        .cancellable(id: CancellationID.signIn, cancelInFlight: true)
    }

    private func submitAccountDeletion() -> Effect<Action> {
        .run { send in
            do {
                let acknowledgement = try await authClient.deleteAccount()
                await send(.deleteAccountResponse(.success(acknowledgement)))
            } catch is CancellationError {
                return
            } catch {
                await send(.deleteAccountResponse(.failure(Self.map(error))))
            }
        }
    }

    private static func map(_ error: any Error) -> AuthClientError {
        error as? AuthClientError ?? .unavailable
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
            } catch is CancellationError {
                return
            } catch {
                await send(.credentialRevocationCleanupResponse(.failure(Self.map(error))))
            }
        }
    }

    private func clearLocalCredentials() -> Effect<Action> {
        .run { send in
            do {
                try await authClient.clearLocalCredentials()
                await send(.localCleanupResponse(.success))
            } catch is CancellationError {
                return
            } catch {
                await send(.localCleanupResponse(.failure(Self.map(error))))
            }
        }
        .cancellable(id: CancellationID.localCredentialCleanup, cancelInFlight: true)
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
             .accountDeletionReconciliationRequired,
             .resubmittingAccountDeletion,
             .clearingLocalCredentials,
             .localCredentialCleanupRequired,
             .failed:
            return false
        }
    }

    var accountDeletionStatus: AccountDeletionStatus? {
        switch self {
        case let .clearingLocalCredentials(status),
             let .localCredentialCleanupRequired(status):
            return status
        case .restoring,
             .signedOut,
             .signingIn,
             .signedIn,
             .signingOut,
             .confirmingAccountDeletion,
             .deleting,
             .accountDeletionReconciliationRequired,
             .resubmittingAccountDeletion,
             .failed:
            return nil
        }
    }
}
