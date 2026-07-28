import AuthenticationServices
import ComposableArchitecture
import Foundation

enum AppleCredentialState: Equatable, Sendable {
    case authorized
    case revoked
    case notFound
    case transferred
    case unavailable
}

struct AppleCredentialStateClient: Sendable {
    var credentialState: @Sendable (String) async -> AppleCredentialState
    var revocationEvents: @Sendable () -> AsyncStream<Void>
}

extension AppleCredentialStateClient {
    static func live(
        provider: LiveAppleCredentialStateProvider = LiveAppleCredentialStateProvider()
    ) -> AppleCredentialStateClient {
        AppleCredentialStateClient(
            credentialState: { userID in
                do {
                    return try await provider.credentialState(forUserID: userID)
                } catch {
                    return .unavailable
                }
            },
            revocationEvents: {
                provider.revocationEvents()
            }
        )
    }

    static let unavailable = AppleCredentialStateClient(
        credentialState: { _ in .unavailable },
        revocationEvents: { AsyncStream { $0.finish() } }
    )
}

extension AppleCredentialStateClient: DependencyKey {
    static let liveValue = AppleCredentialStateClient.live()
    static let testValue = unavailable
}

extension DependencyValues {
    var appleCredentialStateClient: AppleCredentialStateClient {
        get { self[AppleCredentialStateClient.self] }
        set { self[AppleCredentialStateClient.self] = newValue }
    }
}

struct LiveAppleCredentialStateProvider: @unchecked Sendable {
    typealias CredentialStateLookup = (
        String,
        @escaping (ASAuthorizationAppleIDProvider.CredentialState, (any Error)?) -> Void
    ) -> Void

    private let credentialStateLookup: CredentialStateLookup
    private let revocationEventsSource: @Sendable () -> AsyncStream<Void>

    init(
        appleIDProvider: ASAuthorizationAppleIDProvider = .init(),
        notificationCenter: NotificationCenter = .default,
        credentialStateLookup: CredentialStateLookup? = nil,
        revocationEventsSource: (@Sendable () -> AsyncStream<Void>)? = nil
    ) {
        self.credentialStateLookup = credentialStateLookup ?? { userID, completion in
            appleIDProvider.getCredentialState(forUserID: userID, completion: completion)
        }
        self.revocationEventsSource = revocationEventsSource ?? {
            AsyncStream { continuation in
                let task = Task {
                    for await _ in notificationCenter.notifications(
                        named: ASAuthorizationAppleIDProvider.credentialRevokedNotification
                    ) {
                        continuation.yield(())
                    }
                }
                continuation.onTermination = { @Sendable _ in
                    task.cancel()
                }
            }
        }
    }

    func credentialState(forUserID userID: String) async throws -> AppleCredentialState {
        let request = OneShotCredentialStateRequest()

        return try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                guard request.install(continuation) else { return }

                credentialStateLookup(userID) { state, error in
                    if let error {
                        request.resume(with: .failure(error))
                        return
                    }
                    request.resume(with: .success(Self.map(state)))
                }
            }
        } onCancel: {
            request.resume(with: .failure(CancellationError()))
        }
    }

    func revocationEvents() -> AsyncStream<Void> {
        revocationEventsSource()
    }

    private static func map(
        _ state: ASAuthorizationAppleIDProvider.CredentialState
    ) -> AppleCredentialState {
        switch state {
        case .authorized:
            .authorized
        case .revoked:
            .revoked
        case .notFound:
            .notFound
        case .transferred:
            .transferred
        @unknown default:
            .unavailable
        }
    }
}

private final class OneShotCredentialStateRequest: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<AppleCredentialState, Error>?
    private var didResume = false

    func install(
        _ continuation: CheckedContinuation<AppleCredentialState, Error>
    ) -> Bool {
        lock.lock()
        guard !didResume else {
            lock.unlock()
            continuation.resume(throwing: CancellationError())
            return false
        }

        self.continuation = continuation
        lock.unlock()
        return true
    }

    func resume(with result: Result<AppleCredentialState, Error>) {
        lock.lock()
        guard !didResume else {
            lock.unlock()
            return
        }

        didResume = true
        let continuation = continuation
        self.continuation = nil
        lock.unlock()

        continuation?.resume(with: result)
    }
}
