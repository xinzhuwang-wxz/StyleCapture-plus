import ComposableArchitecture
import Foundation

public struct DatabaseClient: Sendable {
    public var migrate: @Sendable () async throws -> Void
    public var insertOutbox: @Sendable (OutboxRecord) async throws -> Void
    public var pendingOutbox: @Sendable () async throws -> [OutboxRecord]

    public init(
        migrate: @escaping @Sendable () async throws -> Void,
        insertOutbox: @escaping @Sendable (OutboxRecord) async throws -> Void,
        pendingOutbox: @escaping @Sendable () async throws -> [OutboxRecord]
    ) {
        self.migrate = migrate
        self.insertOutbox = insertOutbox
        self.pendingOutbox = pendingOutbox
    }
}

public enum DatabaseClientError: Error, Equatable, Sendable {
    case unimplemented
}

extension DatabaseClient: DependencyKey {
    public static let liveValue = DatabaseClient(
        migrate: {
            let database = try AppDatabase.at(Self.defaultDatabaseURL())
            try database.migrate()
        },
        insertOutbox: { record in
            let database = try AppDatabase.at(Self.defaultDatabaseURL())
            try database.migrate()
            try database.insertOutbox(record)
        },
        pendingOutbox: {
            let database = try AppDatabase.at(Self.defaultDatabaseURL())
            try database.migrate()
            return try database.pendingOutbox()
        }
    )

    public static let testValue = DatabaseClient(
        migrate: { throw DatabaseClientError.unimplemented },
        insertOutbox: { _ in throw DatabaseClientError.unimplemented },
        pendingOutbox: { throw DatabaseClientError.unimplemented }
    )

    private static func defaultDatabaseURL() throws -> URL {
        let directory = try FileManager.default.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        return directory.appending(path: "StyleCaptureJourney.sqlite")
    }
}

public extension DependencyValues {
    var databaseClient: DatabaseClient {
        get { self[DatabaseClient.self] }
        set { self[DatabaseClient.self] = newValue }
    }
}
