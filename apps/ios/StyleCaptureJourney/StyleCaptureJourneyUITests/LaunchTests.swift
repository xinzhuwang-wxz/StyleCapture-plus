import XCTest

final class LaunchTests: XCTestCase {
    override func setUp() {
        super.setUp()
        continueAfterFailure = false
    }

    func testHarnessSignedOutShowsAuthenticationShellBeforeJourney() {
        let app = launchHarness(scenario: "signedOut")

        XCTAssertTrue(app.buttons["auth.cta.apple"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.otherElements["auth.shell.signedOut"].exists)
        XCTAssertFalse(app.staticTexts["journey.emptyState"].exists)
        attachScreenshot(named: "signed-out", app: app)
    }

    func testHarnessLiveAppleSheetUsesRealAppleAuthorizationSheet() {
        let app = launchHarness(scenario: "liveAppleSheet")

        XCTAssertTrue(app.buttons["auth.cta.apple"].waitForExistence(timeout: 5))
        app.buttons["auth.cta.apple"].tap()

        XCTAssertTrue(app.otherElements["auth.shell.signingIn"].waitForExistence(timeout: 5))
        attachScreenshot(named: "live-apple-sheet-debug-simulator", app: app)
    }

    func testHarnessSignInNetworkFailureThenSuccess() {
        let app = launchHarness(scenario: "signInNetworkFailureThenSuccess")

        XCTAssertTrue(app.buttons["auth.cta.apple"].waitForExistence(timeout: 5))
        app.buttons["auth.cta.apple"].tap()

        XCTAssertTrue(app.otherElements["auth.shell.failure"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["auth.status.title"].exists)
        attachScreenshot(named: "sign-in-network-failure", app: app)

        XCTAssertTrue(app.buttons["auth.retrySignIn.button"].waitForExistence(timeout: 5))
        app.buttons["auth.retrySignIn.button"].tap()

        XCTAssertTrue(app.otherElements["auth.account.controls"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["journey.emptyState"].exists)
        attachScreenshot(named: "sign-in-retry-success", app: app)
    }

    func testHarnessSignedInDeleteSuspendsOnDeletingState() {
        let app = launchHarness(scenario: "signedInDeleteSuspends")

        XCTAssertTrue(app.otherElements["auth.account.controls"].waitForExistence(timeout: 5))
        app.buttons["auth.deleteAccount.button"].tap()

        XCTAssertTrue(app.otherElements["auth.delete.confirmation"].waitForExistence(timeout: 5))
        app.buttons["auth.confirmDelete.button"].tap()

        XCTAssertTrue(app.otherElements["auth.shell.deleting"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.progressIndicators["auth.progress.deleting"].exists)
        attachScreenshot(named: "account-deleting-suspended", app: app)
    }

    func testHarnessDeleteNetworkFailurePersistsIntentAcrossRelaunchThenRetrySucceeds() {
        let namespace = harnessNamespace()
        let app = launchHarness(
            scenario: "deleteNetworkFailurePersistsIntent",
            namespace: namespace
        )

        XCTAssertTrue(app.otherElements["auth.account.controls"].waitForExistence(timeout: 5))
        app.buttons["auth.deleteAccount.button"].tap()
        XCTAssertTrue(app.otherElements["auth.delete.confirmation"].waitForExistence(timeout: 5))
        app.buttons["auth.confirmDelete.button"].tap()

        XCTAssertTrue(app.otherElements["auth.shell.deleteRecovery"].waitForExistence(timeout: 5))
        attachScreenshot(named: "delete-network-failure-recovery", app: app)

        app.terminate()

        let relaunched = launchHarness(
            scenario: "deleteNetworkFailurePersistsIntent",
            namespace: namespace,
            reset: false
        )

        XCTAssertTrue(relaunched.otherElements["auth.shell.deleteRecovery"].waitForExistence(timeout: 5))
        attachScreenshot(named: "delete-intent-recovery-after-relaunch", app: relaunched)

        relaunched.buttons["auth.retryAccountDeletion.button"].tap()
        XCTAssertTrue(relaunched.otherElements["auth.shell.signedOut"].waitForExistence(timeout: 5))
        attachScreenshot(named: "delete-retry-success-signed-out", app: relaunched)
    }

    func testHarnessLocalCleanupRequiredThenSuccess() {
        let app = launchHarness(scenario: "localCleanupRequiredThenSuccess")

        XCTAssertTrue(app.otherElements["auth.shell.cleanupRecovery"].waitForExistence(timeout: 5))
        attachScreenshot(named: "local-cleanup-required", app: app)

        app.buttons["auth.retryLocalCleanup.button"].tap()

        XCTAssertTrue(app.otherElements["auth.shell.signedOut"].waitForExistence(timeout: 5))
        attachScreenshot(named: "local-cleanup-success", app: app)
    }

    private func launchHarness(
        scenario: String,
        namespace: String? = nil,
        reset: Bool = true
    ) -> XCUIApplication {
        let namespace = namespace ?? harnessNamespace()
        let app = XCUIApplication()
        app.launchEnvironment["STYLECAPTURE_UI_HARNESS"] = "1"
        app.launchEnvironment["STYLECAPTURE_UI_HARNESS_SCENARIO"] = scenario
        app.launchEnvironment["STYLECAPTURE_UI_HARNESS_NAMESPACE"] = namespace
        app.launchEnvironment["STYLECAPTURE_UI_HARNESS_RESET"] = reset ? "1" : "0"
        app.launch()
        return app
    }

    private func attachScreenshot(named name: String, app: XCUIApplication) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "DEBUG simulator UI harness - \(name)"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func harnessNamespace() -> String {
        "\(name)-\(UUID().uuidString)"
    }
}
