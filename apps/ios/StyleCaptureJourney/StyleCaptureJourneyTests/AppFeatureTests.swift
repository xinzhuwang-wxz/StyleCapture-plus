import ComposableArchitecture
import XCTest
@testable import StyleCaptureJourney

@MainActor
final class AppFeatureTests: XCTestCase {
    func testAppLaunchRestoresAuthenticationBeforeJourneyIsAvailable() async {
        let store = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        } withDependencies: {
            $0.databaseClient = DatabaseClient(
                migrate: {},
                insertOutbox: { _ in },
                pendingOutbox: { [] }
            )
            $0.authClient.restore = { nil }
        }

        await store.send(.launch)
        await store.receive(.launchResponse(.success))
        await store.receive(.auth(.task))
        await store.receive(.auth(.restoreResponse(.signedOut))) {
            $0.auth.phase = .signedOut
        }
    }

    func testAppScopesAuthReducerAndUnlocksJourneyOnlyAfterRestoreSucceeds() async {
        let account = Self.account
        let store = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        } withDependencies: {
            $0.authClient.restore = { account }
        }

        await store.send(.auth(.task))
        await store.receive(.auth(.restoreResponse(.signedIn(account)))) {
            $0.auth.phase = .signedIn(account)
        }
    }

    func testDatabaseMigrationFailureExposesLaunchErrorAndDoesNotStartAuthRestoration() async {
        struct MigrationFailed: Error {}

        let store = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        } withDependencies: {
            $0.databaseClient = DatabaseClient(
                migrate: { throw MigrationFailed() },
                insertOutbox: { _ in },
                pendingOutbox: { [] }
            )
        }

        await store.send(.launch)
        await store.receive(.launchResponse(.failure(.databaseMigrationFailed))) {
            $0.launchError = .databaseMigrationFailed
        }
        await store.finish()
    }

    func testDatabaseMigrationFailureThenRetrySuccessRestoresAuthentication() async {
        let migration = LaunchRetryMigration()
        let store = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        } withDependencies: {
            $0.databaseClient = DatabaseClient(
                migrate: { try await migration.migrate() },
                insertOutbox: { _ in },
                pendingOutbox: { [] }
            )
            $0.authClient.restore = { nil }
        }

        await store.send(.launch)
        await store.receive(.launchResponse(.failure(.databaseMigrationFailed))) {
            $0.launchError = .databaseMigrationFailed
        }

        await store.send(.launch) {
            $0.launchError = nil
        }
        await store.receive(.launchResponse(.success))
        await store.receive(.auth(.task))
        await store.receive(.auth(.restoreResponse(.signedOut))) {
            $0.auth.phase = .signedOut
        }
    }

    func testRestoredNavigationSnapshotSelectsJourneyWithoutStack() async {
        let store = TestStore(
            initialState: AppFeature.State(
                navigationSnapshot: Shared(
                    value: NavigationSnapshot(selectedTab: "journey", journeyID: "journey-42")
                )
            )
        ) {
            AppFeature()
        } withDependencies: {
            $0.databaseClient = DatabaseClient(
                migrate: {},
                insertOutbox: { _ in },
                pendingOutbox: { [] }
            )
            $0.authClient.restore = { nil }
        }

        await store.send(.launch)
        await store.receive(.launchResponse(.success)) {
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-42"
        }
        await store.receive(.auth(.task))
        await store.receive(.auth(.restoreResponse(.signedOut))) {
            $0.auth.phase = .signedOut
        }
    }

    func testInvalidSelectedTabFallsBackToJourneyWhenRestored() async {
        let store = TestStore(
            initialState: AppFeature.State(
                navigationSnapshot: Shared(
                    value: NavigationSnapshot(selectedTab: "closet", journeyID: "journey-45")
                )
            )
        ) {
            AppFeature()
        } withDependencies: {
            $0.databaseClient = DatabaseClient(
                migrate: {},
                insertOutbox: { _ in },
                pendingOutbox: { [] }
            )
            $0.authClient.restore = { nil }
        }

        await store.send(.launch)
        await store.receive(.launchResponse(.success)) {
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-45"
        }
        await store.receive(.auth(.task))
        await store.receive(.auth(.restoreResponse(.signedOut))) {
            $0.auth.phase = .signedOut
        }
    }

    func testSelectedTabChangePersistsThroughSharedNavigationSnapshot() async {
        let sharedSnapshot = Shared(
            value: NavigationSnapshot(selectedTab: "journey", journeyID: "journey-existing")
        )
        let store = TestStore(initialState: AppFeature.State(navigationSnapshot: sharedSnapshot)) {
            AppFeature()
        }

        await store.send(.selectedTabChanged(.journey)) {
            $0.selectedTab = .journey
            $0.$navigationSnapshot.withLock {
                $0.selectedTab = "journey"
                $0.journeyID = "journey-existing"
            }
        }

        XCTAssertEqual(
            sharedSnapshot.wrappedValue,
            NavigationSnapshot(selectedTab: "journey", journeyID: "journey-existing")
        )
    }

    func testDeepLinkPersistsJourneyIDThroughSharedNavigationSnapshot() async {
        let sharedSnapshot = Shared(value: NavigationSnapshot(selectedTab: "journey", journeyID: nil))
        let store = TestStore(initialState: AppFeature.State(navigationSnapshot: sharedSnapshot)) {
            AppFeature()
        }

        await store.send(.deepLink(URL(string: "stylecapture://journey/journey-43")!)) {
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-43"
            $0.$navigationSnapshot.withLock {
                $0.selectedTab = "journey"
                $0.journeyID = "journey-43"
            }
        }

        XCTAssertEqual(
            sharedSnapshot.wrappedValue,
            NavigationSnapshot(selectedTab: "journey", journeyID: "journey-43")
        )
    }

    func testDeepLinkNavigationPersistsAndRestoresFromSharedSnapshotAfterRelaunch() async {
        let sharedSnapshot = Shared(value: NavigationSnapshot(selectedTab: "journey", journeyID: nil))
        let dependencies: (inout DependencyValues) -> Void = {
            $0.databaseClient = DatabaseClient(
                migrate: {},
                insertOutbox: { _ in },
                pendingOutbox: { [] }
            )
            $0.authClient.restore = { nil }
        }

        let firstStore = TestStore(initialState: AppFeature.State(navigationSnapshot: sharedSnapshot)) {
            AppFeature()
        } withDependencies: { dependencies(&$0) }

        await firstStore.send(.deepLink(URL(string: "stylecapture://journey/journey-44")!)) {
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-44"
            $0.$navigationSnapshot.withLock {
                $0.selectedTab = "journey"
                $0.journeyID = "journey-44"
            }
        }

        let secondStore = TestStore(initialState: AppFeature.State(navigationSnapshot: sharedSnapshot)) {
            AppFeature()
        } withDependencies: { dependencies(&$0) }

        await secondStore.send(.launch)
        await secondStore.receive(.launchResponse(.success)) {
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-44"
        }
        await secondStore.receive(.auth(.task))
        await secondStore.receive(.auth(.restoreResponse(.signedOut))) {
            $0.auth.phase = .signedOut
        }
    }
}

private extension AppFeatureTests {
    static let account = AuthenticatedAccount(
        accessExpiresAt: Date(timeIntervalSince1970: 1_900_000_000),
        appleUserIdentifier: nil
    )
}

private actor LaunchRetryMigration {
    private var attempts = 0

    func migrate() throws {
        attempts += 1
        if attempts == 1 {
            throw DatabaseClientError.unimplemented
        }
    }
}
