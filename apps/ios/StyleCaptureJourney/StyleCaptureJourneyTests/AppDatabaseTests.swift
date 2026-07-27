import XCTest
@testable import StyleCaptureJourney

final class AppDatabaseTests: XCTestCase {
    func testFirstRunMigrationCreatesOutboxAndRoundTripsPendingRecord() throws {
        let database = try AppDatabase.inMemory()
        try database.migrate()

        let record = OutboxRecord(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000043")!,
            subjectID: "journey-42",
            operation: "trip.create",
            payloadJSON: #"{"trip_id":"journey-42"}"#,
            createdAt: Date(timeIntervalSince1970: 1_800_000_000)
        )

        try database.insertOutbox(record)
        XCTAssertEqual(try database.pendingOutbox(), [record])
    }
}
