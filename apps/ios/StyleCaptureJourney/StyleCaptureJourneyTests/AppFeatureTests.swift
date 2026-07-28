import ComposableArchitecture
import XCTest
@testable import StyleCaptureJourney

@MainActor
final class AppFeatureTests: XCTestCase {
    func testLaunchMigratesDatabaseAndMarksAppReady() async {
        let store = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        } withDependencies: {
            $0.databaseClient = DatabaseClient(
                migrate: {},
                insertOutbox: { _ in },
                pendingOutbox: { [] }
            )
            $0.navigationSnapshotClient = NavigationSnapshotClient(
                load: { nil },
                save: { _ in }
            )
        }

        await store.send(.launch)
        await store.receive(.launchResponse(.success(nil))) {
            $0.hasMigratedDatabase = true
        }
    }

    func testEmptyJourneyNavigationRestoresFromSnapshot() async {
        let store = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        }

        await store.send(.restoreNavigation(.init(selectedTab: "journey", journeyID: "journey-42"))) {
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-42"
        }
        await store.receive(.navigationPersistenceResponse(.success)) {
            $0.navigationPersistenceStatus = .persisted
        }
    }

    func testDeepLinkSelectsJourneyWithoutCustomRouter() async {
        let store = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        }

        await store.send(.deepLink(URL(string: "stylecapture://journey/journey-43")!)) {
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-43"
        }
        await store.receive(.navigationPersistenceResponse(.success)) {
            $0.navigationPersistenceStatus = .persisted
        }
    }

    func testNavigationSaveFailureIsVisibleAndDoesNotAcknowledgePersistence() async {
        struct SaveFailed: Error {}

        let store = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        } withDependencies: {
            $0.navigationSnapshotClient = NavigationSnapshotClient(
                load: { nil },
                save: { _ in throw SaveFailed() }
            )
        }

        await store.send(.deepLink(URL(string: "stylecapture://journey/journey-save-fails")!)) {
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-save-fails"
        }
        await store.receive(.navigationPersistenceResponse(.failure(.navigationPersistenceFailed))) {
            $0.navigationPersistenceStatus = .failed(.navigationPersistenceFailed)
        }
    }

    func testDeepLinkNavigationPersistsAndRestoresAfterRelaunch() async {
        let persistence = NavigationSnapshotPersistence()
        let dependencies: (inout DependencyValues) -> Void = {
            $0.databaseClient = DatabaseClient(
                migrate: {},
                insertOutbox: { _ in },
                pendingOutbox: { [] }
            )
            $0.navigationSnapshotClient = NavigationSnapshotClient(
                load: { await persistence.load() },
                save: { await persistence.save($0) }
            )
        }

        let firstStore = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        } withDependencies: { dependencies(&$0) }

        await firstStore.send(.deepLink(URL(string: "stylecapture://journey/journey-44")!)) {
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-44"
        }
        await firstStore.receive(.navigationPersistenceResponse(.success)) {
            $0.navigationPersistenceStatus = .persisted
        }

        let secondStore = TestStore(initialState: AppFeature.State()) {
            AppFeature()
        } withDependencies: { dependencies(&$0) }

        await secondStore.send(.launch)
        await secondStore.receive(
            .launchResponse(
                .success(.init(selectedTab: "journey", journeyID: "journey-44"))
            )
        ) {
            $0.hasMigratedDatabase = true
            $0.selectedTab = .journey
            $0.restoredJourneyID = "journey-44"
        }
    }
}

private actor NavigationSnapshotPersistence {
    private var snapshot: NavigationSnapshot?

    func load() -> NavigationSnapshot? {
        snapshot
    }

    func save(_ snapshot: NavigationSnapshot) {
        self.snapshot = snapshot
    }
}
