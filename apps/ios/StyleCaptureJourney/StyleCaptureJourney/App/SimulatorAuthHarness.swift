#if DEBUG
import ComposableArchitecture
import Foundation

enum SimulatorAuthHarness {
    private static let enabledKey = "STYLECAPTURE_UI_HARNESS"
    private static let scenarioKey = "STYLECAPTURE_UI_HARNESS_SCENARIO"
    private static let namespaceKey = "STYLECAPTURE_UI_HARNESS_NAMESPACE"
    private static let resetKey = "STYLECAPTURE_UI_HARNESS_RESET"

    static func makeStore() -> StoreOf<AppFeature> {
        let environment = ProcessInfo.processInfo.environment
        guard environment[enabledKey] == "1",
              let configuration = Configuration(environment: environment)
        else {
            return liveStore()
        }

        if configuration.resetPersistence {
            Persistence.reset(namespace: configuration.namespace)
        }

        let state = SimulatorAuthHarnessState(configuration: configuration)
        return withDependencies {
            $0.databaseClient = DatabaseClient(
                migrate: {},
                insertOutbox: { _ in },
                pendingOutbox: { [] }
            )
            $0.authClient = authClient(state: state)
            $0.appleSignInNonce = AppleSignInNonceClient {
                AppleSignInNonce(
                    rawValue: "debug-simulator-ui-harness-nonce",
                    hashedValue: "debug-simulator-ui-harness-hashed-nonce"
                )
            }
            $0.appleCredentialStateClient = .unavailable
            $0.date.now = Date(timeIntervalSince1970: 1_785_199_900)

            if configuration.scenario != .liveAppleSheet {
                $0.appleSignInClient = AppleSignInClient { _ in
                    AppleSignInCredential(
                        userIdentifier: "debug.ui.harness.apple-user",
                        identityToken: "debug-ui-harness-identity-token",
                        authorizationCode: "debug-ui-harness-authorization-code"
                    )
                }
            }
        } operation: {
            liveStore()
        }
    }

    private static func liveStore() -> StoreOf<AppFeature> {
        Store(initialState: AppFeature.State()) {
            AppFeature()
        }
    }

    private static func authClient(state: SimulatorAuthHarnessState) -> AuthClient {
        AuthClient(
            restore: {
                try await state.restore()
            },
            storedAppleCredentialIsValid: {
                true
            },
            authenticate: { _, _ in
                try await state.authenticate()
            },
            refresh: {
                await state.account()
            },
            logout: {
                await state.clearSession()
            },
            deleteAccount: {
                try await state.deleteAccount()
            },
            clearLocalCredentials: {
                try await state.clearLocalCredentials()
            }
        )
    }
}

private enum SimulatorAuthHarnessScenario: String {
    case signedOut
    case liveAppleSheet
    case signInNetworkFailureThenSuccess
    case signedInDeleteSuspends
    case deleteNetworkFailurePersistsIntent
    case localCleanupRequiredThenSuccess
}

private extension SimulatorAuthHarness {
    struct Configuration {
        var scenario: SimulatorAuthHarnessScenario
        var namespace: String
        var resetPersistence: Bool

        init?(environment: [String: String]) {
            guard let scenarioName = environment[scenarioKey],
                  let scenario = SimulatorAuthHarnessScenario(rawValue: scenarioName)
            else {
                return nil
            }

            self.scenario = scenario
            self.namespace = environment[namespaceKey] ?? UUID().uuidString
            self.resetPersistence = environment[resetKey] == "1"
        }
    }

    enum Persistence {
        static func reset(namespace: String) {
            UserDefaults.standard.removeObject(forKey: key("delete.intent", namespace: namespace))
            UserDefaults.standard.removeObject(forKey: key("delete.accepted", namespace: namespace))
        }

        static func hasDeletionIntent(namespace: String) -> Bool {
            UserDefaults.standard.bool(forKey: key("delete.intent", namespace: namespace))
        }

        static func markDeletionIntent(namespace: String) {
            UserDefaults.standard.set(true, forKey: key("delete.intent", namespace: namespace))
        }

        static func markDeletionAccepted(namespace: String) {
            UserDefaults.standard.set(true, forKey: key("delete.accepted", namespace: namespace))
        }

        static func hasDeletionAccepted(namespace: String) -> Bool {
            UserDefaults.standard.bool(forKey: key("delete.accepted", namespace: namespace))
        }

        static func clear(namespace: String) {
            reset(namespace: namespace)
        }

        private static func key(_ suffix: String, namespace: String) -> String {
            "stylecapture.debug.uiHarness.\(namespace).\(suffix)"
        }
    }
}

private actor SimulatorAuthHarnessState {
    private let configuration: SimulatorAuthHarness.Configuration
    private var authenticateAttempts = 0
    private var localCleanupAttempts = 0

    init(configuration: SimulatorAuthHarness.Configuration) {
        self.configuration = configuration
    }

    func restore() throws -> AuthenticatedAccount? {
        switch configuration.scenario {
        case .signedOut,
             .liveAppleSheet,
             .signInNetworkFailureThenSuccess:
            return nil

        case .signedInDeleteSuspends:
            return account()

        case .deleteNetworkFailurePersistsIntent:
            if SimulatorAuthHarness.Persistence.hasDeletionIntent(namespace: configuration.namespace) {
                throw AuthClientError.accountDeletionReconciliationRequired
            }
            return account()

        case .localCleanupRequiredThenSuccess:
            throw AuthClientError.localCredentialCleanupRequired
        }
    }

    func authenticate() throws -> AuthenticatedAccount {
        switch configuration.scenario {
        case .signInNetworkFailureThenSuccess:
            authenticateAttempts += 1
            if authenticateAttempts == 1 {
                throw AuthClientError.networkUnavailable
            }
            return account()

        case .signedOut,
             .liveAppleSheet,
             .signedInDeleteSuspends,
             .deleteNetworkFailurePersistsIntent,
             .localCleanupRequiredThenSuccess:
            return account()
        }
    }

    func deleteAccount() async throws -> AccountDeletionAcknowledgement {
        switch configuration.scenario {
        case .signedInDeleteSuspends:
            try await Task.sleep(nanoseconds: 60_000_000_000)
            throw CancellationError()

        case .deleteNetworkFailurePersistsIntent:
            if SimulatorAuthHarness.Persistence.hasDeletionIntent(namespace: configuration.namespace) {
                SimulatorAuthHarness.Persistence.markDeletionAccepted(namespace: configuration.namespace)
                return AccountDeletionAcknowledgement(status: .accepted)
            }

            SimulatorAuthHarness.Persistence.markDeletionIntent(namespace: configuration.namespace)
            throw AuthClientError.networkUnavailable

        case .signedOut,
             .liveAppleSheet,
             .signInNetworkFailureThenSuccess,
             .localCleanupRequiredThenSuccess:
            return AccountDeletionAcknowledgement(status: .accepted)
        }
    }

    func clearLocalCredentials() throws {
        switch configuration.scenario {
        case .deleteNetworkFailurePersistsIntent:
            guard SimulatorAuthHarness.Persistence.hasDeletionAccepted(
                namespace: configuration.namespace
            ) else {
                throw AuthClientError.localCredentialCleanupRequired
            }
            SimulatorAuthHarness.Persistence.clear(namespace: configuration.namespace)

        case .localCleanupRequiredThenSuccess:
            localCleanupAttempts += 1
            if localCleanupAttempts == 1 {
                return
            }

        case .signedOut,
             .liveAppleSheet,
             .signInNetworkFailureThenSuccess,
             .signedInDeleteSuspends:
            break
        }
    }

    func clearSession() {
        SimulatorAuthHarness.Persistence.clear(namespace: configuration.namespace)
    }

    func account() -> AuthenticatedAccount {
        AuthenticatedAccount(
            accessExpiresAt: Date(timeIntervalSince1970: 1_785_200_000)
        )
    }
}
#endif
