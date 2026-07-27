import XCTest

final class LaunchTests: XCTestCase {
    func testLaunchShowsEmptyJourneyShell() {
        let app = XCUIApplication()
        app.launch()

        XCTAssertTrue(app.staticTexts["journey.title"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["journey.emptyState"].exists)
    }
}
