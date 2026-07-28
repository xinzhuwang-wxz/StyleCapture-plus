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
        case refreshing(AuthTokens)
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
    }

    private enum CancellationID: Hashable {
        case signIn
    }

    @Dependency(\.authClient) var authClient
    @Dependency(\.appleSignInClient) var appleSignInClient
    @Dependency(\.appleSignInNonce) var appleSignInNonce

    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .task:
                return .run { send in
                    do {
                        if let tokens = try await authClient.restore() {
                            await send(.restoreResponse(.signedIn(tokens)))
                        } else {
                            await send(.restoreResponse(.signedOut))
                        }
                    } catch {
                        await send(.restoreResponse(.failure(Self.map(error))))
                    }
                }

            case .restoreResponse(.signedOut):
                state.phase = .signedOut
                return .none

            case let .restoreResponse(.signedIn(tokens)):
                state.phase = .signedIn(tokens)
                return .none

            case let .restoreResponse(.failure(error)):
                state.phase = .failed(error)
                return .none

            case .signInButtonTapped, .retrySignInTapped:
                state.phase = .signingIn
                return signIn()

            case let .signInResponse(.success(tokens)):
                state.phase = .signedIn(tokens)
                return .none

            case .signInResponse(.failure(.authorizationCancelled)):
                state.phase = .signedOut
                return .none

            case let .signInResponse(.failure(error)):
                state.phase = .failed(error)
                return .none

            case .deleteAccountButtonTapped:
                switch state.phase {
                case let .signedIn(tokens), let .refreshing(tokens):
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
                return .none

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
                return .none

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
                return .none

            case let .localCleanupResponse(.failure(error)):
                state.phase = error == .localCredentialCleanupRequired
                    ? .localCredentialCleanupRequired
                    : .failed(error)
                return .none
            }
        }
    }

    private func signIn() -> Effect<Action> {
        .run { send in
            do {
                let nonce = try appleSignInNonce.generate()
                let credential = try await appleSignInClient.authorize(nonce.hashedValue)
                let tokens = try await authClient.authenticate(credential, nonce.rawValue)
                await send(.signInResponse(.success(tokens)))
            } catch {
                await send(.signInResponse(.failure(Self.map(error))))
            }
        }
        .cancellable(id: CancellationID.signIn, cancelInFlight: true)
    }

    private static func map(_ error: any Error) -> AuthClientError {
        error as? AuthClientError ?? .unavailable
    }
}
