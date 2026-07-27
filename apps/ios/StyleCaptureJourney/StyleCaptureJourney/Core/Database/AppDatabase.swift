import Foundation
import GRDB

public struct AppDatabase: @unchecked Sendable {
    private let writer: any DatabaseWriter

    public init(writer: any DatabaseWriter) {
        self.writer = writer
    }

    public static func inMemory() throws -> AppDatabase {
        try AppDatabase(writer: DatabaseQueue())
    }

    public static func at(_ url: URL) throws -> AppDatabase {
        try AppDatabase(writer: DatabaseQueue(path: url.path))
    }

    public func migrate() throws {
        var migrator = DatabaseMigrator()
        migrator.registerMigration("v1_create_outbox_records") { db in
            try db.create(table: OutboxRecord.databaseTableName, ifNotExists: true) { table in
                table.column("id", .text).primaryKey()
                table.column("subjectID", .text).notNull()
                table.column("operation", .text).notNull()
                table.column("payloadJSON", .text).notNull()
                table.column("createdAt", .datetime).notNull()
            }
            try db.create(
                index: "idx_outbox_records_created_at",
                on: OutboxRecord.databaseTableName,
                columns: ["createdAt"]
            )
        }
        try migrator.migrate(writer)
    }

    public func insertOutbox(_ record: OutboxRecord) throws {
        try writer.write { db in
            try record.insert(db)
        }
    }

    public func pendingOutbox() throws -> [OutboxRecord] {
        try writer.read { db in
            try OutboxRecord
                .order(OutboxRecord.Columns.createdAt.asc, OutboxRecord.Columns.id.asc)
                .fetchAll(db)
        }
    }
}
