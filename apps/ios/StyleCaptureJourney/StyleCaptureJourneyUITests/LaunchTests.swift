import XCTest

final class LaunchTests: XCTestCase {
    func testLaunchShowsSignedOutAuthenticationShellBeforeJourney() {
        let app = XCUIApplication()
        app.launch()

        XCTAssertTrue(app.buttons["auth.cta.apple"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.otherElements["auth.shell.signedOut"].exists)
        XCTAssertFalse(app.staticTexts["journey.emptyState"].exists)
    }
}
