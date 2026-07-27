import ComposableArchitecture
import Foundation

public struct NavigationSnapshot: Codable, Equatable, Sendable {
    public var selectedTab: String
    public var journeyID: String?

    public init(selectedTab: String, journeyID: String?) {
        self.selectedTab = selectedTab
        self.journeyID = journeyID
    }
}

public struct NavigationSnapshotClient: Sendable {
    public var load: @Sendable () async throws -> NavigationSnapshot?
    public var save: @Sendable (NavigationSnapshot) async throws -> Void

    public init(
        load: @escaping @Sendable () async throws -> NavigationSnapshot?,
        save: @escaping @Sendable (NavigationSnapshot) async throws -> Void
    ) {
        self.load = load
        self.save = save
    }
}

extension NavigationSnapshotClient: DependencyKey {
    public static let liveValue = NavigationSnapshotClient.live()
    public static let testValue = NavigationSnapshotClient(load: { nil }, save: { _ in })

    public static func live(
        defaults: UserDefaults = .standard,
        key: String = "com.stylecapture.journey.navigationSnapshot"
    ) -> NavigationSnapshotClient {
        let store = UserDefaultsNavigationSnapshotStore(defaults: defaults, key: key)
        return NavigationSnapshotClient(
            load: {
                try store.load()
            },
            save: { snapshot in
                try store.save(snapshot)
            }
        )
    }
}

public extension DependencyValues {
    var navigationSnapshotClient: NavigationSnapshotClient {
        get { self[NavigationSnapshotClient.self] }
        set { self[NavigationSnapshotClient.self] = newValue }
    }
}

private struct UserDefaultsNavigationSnapshotStore: @unchecked Sendable {
    let defaults: UserDefaults
    let key: String

    func load() throws -> NavigationSnapshot? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try JSONDecoder().decode(NavigationSnapshot.self, from: data)
    }

    func save(_ snapshot: NavigationSnapshot) throws {
        let data = try JSONEncoder().encode(snapshot)
        defaults.set(data, forKey: key)
    }
}
