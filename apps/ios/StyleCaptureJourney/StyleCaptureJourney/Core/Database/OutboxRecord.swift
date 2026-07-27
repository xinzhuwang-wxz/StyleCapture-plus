import Foundation
import GRDB

public struct OutboxRecord: Codable, Equatable, FetchableRecord, PersistableRecord, Sendable {
    public static let databaseTableName = "outbox_records"

    public let id: UUID
    public let subjectID: String
    public let operation: String
    public let payloadJSON: String
    public let createdAt: Date

    public init(
        id: UUID,
        subjectID: String,
        operation: String,
        payloadJSON: String,
        createdAt: Date
    ) {
        self.id = id
        self.subjectID = subjectID
        self.operation = operation
        self.payloadJSON = payloadJSON
        self.createdAt = createdAt
    }

    enum Columns {
        static let id = Column("id")
        static let createdAt = Column("createdAt")
    }
}
