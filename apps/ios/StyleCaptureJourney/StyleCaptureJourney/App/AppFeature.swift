import ComposableArchitecture
import Foundation

@Reducer
struct AppFeature {
    @ObservableState
    struct State: Equatable {
        var hasMigratedDatabase = false
        var selectedTab: Tab = .journey
        var restoredJourneyID: String?
        var navigationPersistenceStatus: NavigationPersistenceStatus = .idle
        var journey = JourneyFeature.State()
    }

    enum Tab: String, Codable, Equatable, Sendable {
        case journey
    }

    enum NavigationPersistenceStatus: Equatable, Sendable {
        case idle
        case persisted
        case failed(AppError)
    }

    enum NavigationPersistenceResponse: Equatable, Sendable {
        case success
        case failure(AppError)
    }

    enum Action: Equatable {
        case launch
        case launchResponse(Result<NavigationSnapshot?, AppError>)
        case navigationPersistenceResponse(NavigationPersistenceResponse)
        case restoreNavigation(NavigationSnapshot)
        case selectedTabChanged(Tab)
        case deepLink(URL)
        case journey(JourneyFeature.Action)
    }

    enum AppError: Error, Equatable, Sendable {
        case databaseMigrationFailed
        case navigationPersistenceFailed
    }

    @Dependency(\.databaseClient) var databaseClient
    @Dependency(\.navigationSnapshotClient) var navigationSnapshotClient
    @Dependency(\.appLogger) var appLogger

    var body: some ReducerOf<Self> {
        Scope(state: \.journey, action: \.journey) {
            JourneyFeature()
        }
        Reduce { state, action in
            switch action {
            case .launch:
                return .run { send in
                    do {
                        try await databaseClient.migrate()
                    } catch {
                        await send(.launchResponse(.failure(.databaseMigrationFailed)))
                        return
                    }
                    do {
                        let snapshot = try await navigationSnapshotClient.load()
                        await send(.launchResponse(.success(snapshot)))
                    } catch {
                        await send(.launchResponse(.failure(.navigationPersistenceFailed)))
                    }
                }

            case let .launchResponse(.success(snapshot)):
                state.hasMigratedDatabase = true
                if let snapshot {
                    Self.apply(snapshot, to: &state)
                }
                return .none

            case .launchResponse(.failure):
                state.hasMigratedDatabase = false
                return .none

            case .navigationPersistenceResponse(.success):
                state.navigationPersistenceStatus = .persisted
                return .none

            case let .navigationPersistenceResponse(.failure(error)):
                state.navigationPersistenceStatus = .failed(error)
                return .none

            case let .restoreNavigation(snapshot):
                Self.apply(snapshot, to: &state)
                return persistNavigation(state)

            case let .selectedTabChanged(tab):
                state.selectedTab = tab
                return persistNavigation(state)

            case let .deepLink(url):
                if let journeyID = Self.journeyID(from: url) {
                    state.selectedTab = .journey
                    state.restoredJourneyID = journeyID
                    return persistNavigation(state)
                }
                return .none

            case .journey:
                return .none
            }
        }
    }

    private static func journeyID(from url: URL) -> String? {
        guard url.host == "journey" else { return nil }
        return url.pathComponents.dropFirst().first
    }

    private func persistNavigation(_ state: State) -> Effect<Action> {
        let snapshot = NavigationSnapshot(
            selectedTab: state.selectedTab.rawValue,
            journeyID: state.restoredJourneyID
        )
        return .run { send in
            do {
                try await navigationSnapshotClient.save(snapshot)
                await send(.navigationPersistenceResponse(.success))
            } catch {
                appLogger.userRecoverableError("navigation persistence failed")
                await send(.navigationPersistenceResponse(.failure(.navigationPersistenceFailed)))
            }
        }
    }

    private static func apply(_ snapshot: NavigationSnapshot, to state: inout State) {
        state.selectedTab = Tab(rawValue: snapshot.selectedTab) ?? .journey
        state.restoredJourneyID = snapshot.journeyID
    }
}
