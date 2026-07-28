import XCTest
@testable import StyleCaptureJourney

final class AuthViewContractTests: XCTestCase {
    func testRestoringStateExposesInitialShellIdentifier() {
        XCTAssertEqual(
            AuthViewContract.accessibilityIdentifiers(
                for: AuthFeature.State(phase: .restoring)
            ),
            [
                "auth.shell.restoring",
                "auth.progress.restoring",
            ]
        )
    }

    func testSignedOutStateExposesAppleCTAIdentifier() {
        XCTAssertEqual(
            AuthViewContract.accessibilityIdentifiers(
                for: AuthFeature.State(phase: .signedOut)
            ),
            [
                "auth.shell.signedOut",
                "auth.cta.apple",
            ]
        )
    }

    func testSigningInStateExposesProcessingIdentifier() {
        XCTAssertEqual(
            AuthViewContract.accessibilityIdentifiers(
                for: AuthFeature.State(phase: .signingIn)
            ),
            [
                "auth.shell.signingIn",
                "auth.progress.signingIn",
            ]
        )
    }

    func testSignedInStateExposesAccountControlsAndDeleteIdentifier() {
        XCTAssertEqual(
            AuthViewContract.accessibilityIdentifiers(
                for: AuthFeature.State(phase: .signedIn(Self.tokens))
            ),
            [
                "auth.shell.signedIn",
                "auth.account.controls",
                "auth.deleteAccount.button",
            ]
        )
    }

    func testFailureStateExposesRetryIdentifier() {
        XCTAssertEqual(
            AuthViewContract.accessibilityIdentifiers(
                for: AuthFeature.State(phase: .failed(.localCredentialPersistenceFailed))
            ),
            [
                "auth.shell.failure",
                "auth.retrySignIn.button",
            ]
        )
    }

    func testDeletingStateExposesDeleteProgressIdentifier() {
        XCTAssertEqual(
            AuthViewContract.accessibilityIdentifiers(
                for: AuthFeature.State(phase: .deleting)
            ),
            [
                "auth.shell.deleting",
                "auth.progress.deleting",
            ]
        )
    }

    func testCleanupRecoveryStateExposesLocalCredentialRetryIdentifier() {
        XCTAssertEqual(
            AuthViewContract.accessibilityIdentifiers(
                for: AuthFeature.State(phase: .localCredentialCleanupRequired)
            ),
            [
                "auth.shell.cleanupRecovery",
                "auth.retryLocalCleanup.button",
            ]
        )
    }
}

private extension AuthViewContractTests {
    static let tokens = AuthTokens(
        accountSubject: "account-123",
        accessToken: "access-token",
        refreshToken: "refresh-token",
        accessExpiresAt: Date(timeIntervalSince1970: 1_900_000_000),
        tokenType: "Bearer"
    )
}
