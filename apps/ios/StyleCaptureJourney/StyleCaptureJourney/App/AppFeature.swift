import ComposableArchitecture
import Foundation

@Reducer
struct AppFeature {
    @ObservableState
    struct State: Equatable {
        var launchError: AppError?
        var selectedTab: Tab = .journey
        var restoredJourneyID: String?
        @Shared var navigationSnapshot: NavigationSnapshot
        var auth = AuthFeature.State()
        var journey = JourneyFeature.State()

        init(
            launchError: AppError? = nil,
            selectedTab: Tab = .journey,
            restoredJourneyID: String? = nil,
            navigationSnapshot: Shared<NavigationSnapshot> = Shared(
                wrappedValue: NavigationSnapshot(),
                .fileStorage(.styleCaptureNavigationSnapshot)
            ),
            auth: AuthFeature.State = .init(),
            journey: JourneyFeature.State = .init()
        ) {
            self.launchError = launchError
            self.selectedTab = selectedTab
            self.restoredJourneyID = restoredJourneyID
            self._navigationSnapshot = navigationSnapshot
            self.auth = auth
            self.journey = journey
        }
    }

    enum Tab: String, Codable, Equatable, Sendable {
        case journey
    }

    enum Action: Equatable {
        case launch
        case launchResponse(LaunchResponse)
        case selectedTabChanged(Tab)
        case deepLink(URL)
        case auth(AuthFeature.Action)
        case journey(JourneyFeature.Action)
    }

    enum AppError: Error, Equatable, Sendable {
        case databaseMigrationFailed
    }

    enum LaunchResponse: Equatable, Sendable {
        case success
        case failure(AppError)
    }

    @Dependency(\.databaseClient) var databaseClient

    var body: some ReducerOf<Self> {
        Scope(state: \.auth, action: \.auth) {
            AuthFeature()
        }
        Scope(state: \.journey, action: \.journey) {
            JourneyFeature()
        }
        Reduce { state, action in
            switch action {
            case .launch:
                state.launchError = nil
                return launchApplication()

            case .launchResponse(.success):
                state.launchError = nil
                Self.apply(state.navigationSnapshot, to: &state)
                return .send(.auth(.task))

            case .launchResponse(.failure(.databaseMigrationFailed)):
                state.launchError = .databaseMigrationFailed
                return .none

            case let .selectedTabChanged(tab):
                state.selectedTab = tab
                Self.updateNavigationSnapshot(in: &state)
                return .none

            case let .deepLink(url):
                if let journeyID = Self.journeyID(from: url) {
                    state.selectedTab = .journey
                    state.restoredJourneyID = journeyID
                    Self.updateNavigationSnapshot(in: &state)
                }
                return .none

            case .auth, .journey:
                return .none
            }
        }
    }

    private static func journeyID(from url: URL) -> String? {
        guard url.host == "journey" else { return nil }
        return url.pathComponents.dropFirst().first
    }

    private func launchApplication() -> Effect<Action> {
        .run { send in
            do {
                try await databaseClient.migrate()
                await send(.launchResponse(.success))
            } catch {
                await send(.launchResponse(.failure(.databaseMigrationFailed)))
            }
        }
    }

    private static func apply(_ snapshot: NavigationSnapshot, to state: inout State) {
        state.selectedTab = Tab(rawValue: snapshot.selectedTab) ?? .journey
        state.restoredJourneyID = snapshot.journeyID
    }

    private static func updateNavigationSnapshot(in state: inout State) {
        let selectedTab = state.selectedTab.rawValue
        let journeyID = state.restoredJourneyID
        state.$navigationSnapshot.withLock {
            $0.selectedTab = selectedTab
            $0.journeyID = journeyID
        }
    }
}

private extension URL {
    static let styleCaptureNavigationSnapshot = applicationSupportDirectory
        .appending(component: "StyleCaptureJourney", directoryHint: .isDirectory)
        .appending(component: "navigation-snapshot.json")
}
