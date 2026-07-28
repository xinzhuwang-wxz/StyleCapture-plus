import XCTest

final class LaunchTests: XCTestCase {
    func testLaunchShowsRestoringThenSignedOutAuthenticationShell() {
        let app = XCUIApplication()
        app.launch()

        XCTAssertTrue(app.otherElements["auth.shell.restoring"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["auth.cta.apple"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.otherElements["auth.shell.signedOut"].exists)
        XCTAssertFalse(app.staticTexts["journey.emptyState"].exists)
    }
}
