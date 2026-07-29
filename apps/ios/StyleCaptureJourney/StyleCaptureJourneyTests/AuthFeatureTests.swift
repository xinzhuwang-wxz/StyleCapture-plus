import ComposableArchitecture
import Foundation
import XCTest
@testable import StyleCaptureJourney

@MainActor
final class AuthFeatureTests: XCTestCase {
    func testLaunchRestoresSignedOutStateWhenNoCredentialExists() async {
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.restore = { nil }
        }

        await store.send(.task)
        await store.receive(.restoreResponse(.signedOut)) {
            $0.phase = .signedOut
        }
    }

    func testRestoreRefreshesExpiredAccessTokenBeforeSigningIn() async {
        let expired = Self.expiredAccount
        let refreshed = Self.account
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.date.now = Date(timeIntervalSince1970: 1_785_200_100)
            $0.authClient.restore = { expired }
            $0.authClient.refresh = { refreshed }
        }

        await store.send(.task)
        await store.receive(.restoreResponse(.signedIn(refreshed))) {
            $0.phase = .signedIn(refreshed)
        }
    }

    func testRestoreKeepsUnexpiredAccessTokenWithoutRefresh() async {
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.date.now = Date(timeIntervalSince1970: 1_785_199_900)
            $0.authClient.restore = { Self.account }
            $0.authClient.refresh = {
                XCTFail("Fresh access tokens must not be refreshed during restore")
                return Self.account
            }
        }

        await store.send(.task)
        await store.receive(.restoreResponse(.signedIn(Self.account))) {
            $0.phase = .signedIn(Self.account)
        }
        XCTAssertFalse(String(describing: store.state).contains(Self.appleUserIdentifier))
    }

    func testRestoreRevokedAppleCredentialClearsSessionAndSignsOut() async {
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.date.now = Date(timeIntervalSince1970: 1_785_199_900)
            $0.authClient.restore = { Self.account }
            $0.authClient.logout = {}
            $0.authClient.storedAppleCredentialIsValid = { false }
        }

        await store.send(.task)
        await store.receive(.restoreResponse(.signedOut)) {
            $0.phase = .signedOut
        }
    }

    func testRestoreRevokedAppleCredentialCleanupFailureRequiresRetryBeforeSignedOut() async {
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.date.now = Date(timeIntervalSince1970: 1_785_199_900)
            $0.authClient.restore = { Self.account }
            $0.authClient.logout = {
                throw AuthClientError.localCredentialCleanupRequired
            }
            $0.authClient.clearLocalCredentials = {}
            $0.authClient.storedAppleCredentialIsValid = { false }
        }

        await store.send(.task)
        await store.receive(
            .restoreResponse(.failure(.localCredentialCleanupRequired))
        ) {
            $0.phase = .localCredentialCleanupRequired(nil)
        }
        await store.send(.retryLocalCleanupTapped) {
            $0.phase = .clearingLocalCredentials(nil)
        }
        await store.receive(.localCleanupResponse(.success)) {
            $0.phase = .signedOut
        }
    }

    func testRetryRestoreCancelsInFlightRestoreWithoutFalseFailure() async {
        let gate = CancellableRestoreGate(secondResult: nil)
        let secondRestoreStarted = expectation(description: "second restore started")
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.restore = {
                try await gate.restore {
                    secondRestoreStarted.fulfill()
                }
            }
            $0.authClient.refresh = {
                XCTFail("Signed-out restore retry must not refresh stale tokens")
                return Self.account
            }
        }

        await store.send(.task)
        await store.send(.task)
        await fulfillment(of: [secondRestoreStarted], timeout: 1)
        await store.receive(.restoreResponse(.signedOut)) {
            $0.phase = .signedOut
        }
        await gate.cancelFirstRestore()
        await store.finish()
    }

    func testStaleRestoreResponsesCannotOverwriteSignInInProgress() async {
        await assertStaleRestoreResponseIgnoredAfterSignInBegins(.signedOut)
        await assertStaleRestoreResponseIgnoredAfterSignInBegins(.signedIn(Self.account))
        await assertStaleRestoreResponseIgnoredAfterSignInBegins(.failure(.serviceUnavailable))
        await assertStaleRestoreResponseIgnoredAfterSignInBegins(
            .failure(.localCredentialCleanupRequired)
        )
        await assertStaleRestoreResponseIgnoredAfterSignInBegins(
            .failure(.accountDeletionReconciliationRequired)
        )
    }

    func testRestoreDeletionIntentRequiresExplicitDeleteRetry() async {
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.restore = {
                throw AuthClientError.accountDeletionReconciliationRequired
            }
            $0.authClient.deleteAccount = {
                Self.deletionAcknowledgement
            }
            $0.authClient.clearLocalCredentials = {}
        }

        await store.send(.task)
        await store.receive(
            .restoreResponse(.failure(.accountDeletionReconciliationRequired))
        ) {
            $0.phase = .accountDeletionReconciliationRequired
        }
        await store.send(.retryAccountDeletionTapped) {
            $0.phase = .resubmittingAccountDeletion
        }
        await store.receive(.deleteAccountResponse(.success(Self.deletionAcknowledgement))) {
            $0.phase = .clearingLocalCredentials(.accepted)
        }
        await store.receive(.localCleanupResponse(.success)) {
            $0.phase = .signedOut
        }
    }

    func testRecoveredDeletionRetryNetworkFailureStaysInRecovery() async {
        let store = TestStore(
            initialState: AuthFeature.State(phase: .accountDeletionReconciliationRequired)
        ) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.deleteAccount = {
                throw AuthClientError.networkUnavailable
            }
        }

        await store.send(.retryAccountDeletionTapped) {
            $0.phase = .resubmittingAccountDeletion
        }
        await store.receive(.deleteAccountResponse(.failure(.networkUnavailable))) {
            $0.phase = .accountDeletionReconciliationRequired
        }
    }

    func testDeletionUnexpectedResponseAfterLocalIntentStaysInRecovery() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.account))) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.deleteAccount = {
                throw AuthClientError.accountDeletionReconciliationRequired
            }
        }

        await store.send(.deleteAccountButtonTapped) {
            $0.phase = .confirmingAccountDeletion(Self.account)
        }
        await store.send(.confirmDeleteAccountTapped) {
            $0.phase = .deleting(Self.account)
        }
        await store.receive(
            .deleteAccountResponse(.failure(.accountDeletionReconciliationRequired))
        ) {
            $0.phase = .accountDeletionReconciliationRequired
        }
    }

    func testRestoreNotFoundAppleCredentialClearsSessionAndSignsOut() async {
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.date.now = Date(timeIntervalSince1970: 1_785_199_900)
            $0.authClient.restore = { Self.account }
            $0.authClient.logout = {}
            $0.authClient.storedAppleCredentialIsValid = { false }
        }

        await store.send(.task)
        await store.receive(.restoreResponse(.signedOut)) {
            $0.phase = .signedOut
        }
    }

    func testRestoreTransferredAppleCredentialClearsSessionAndSignsOut() async {
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.date.now = Date(timeIntervalSince1970: 1_785_199_900)
            $0.authClient.restore = { Self.account }
            $0.authClient.logout = {}
            $0.authClient.storedAppleCredentialIsValid = { false }
        }

        await store.send(.task)
        await store.receive(.restoreResponse(.signedOut)) {
            $0.phase = .signedOut
        }
    }

    func testRestoreAuthorizedAppleCredentialPreservesUnexpiredSession() async {
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.date.now = Date(timeIntervalSince1970: 1_785_199_900)
            $0.authClient.restore = { Self.account }
            $0.authClient.logout = {
                XCTFail("Authorized Apple credentials must preserve server session")
            }
            $0.authClient.storedAppleCredentialIsValid = { true }
        }

        await store.send(.task)
        await store.receive(.restoreResponse(.signedIn(Self.account))) {
            $0.phase = .signedIn(Self.account)
        }
    }

    func testRestoreCredentialStateUnavailablePreservesServerTruthAndExpiryLogic() async {
        let expired = Self.expiredAccount
        let refreshed = Self.account
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.date.now = Date(timeIntervalSince1970: 1_785_200_100)
            $0.authClient.restore = { expired }
            $0.authClient.refresh = { refreshed }
            $0.authClient.storedAppleCredentialIsValid = { true }
        }

        await store.send(.task)
        await store.receive(.restoreResponse(.signedIn(refreshed))) {
            $0.phase = .signedIn(refreshed)
        }
    }

    func testCredentialRevocationNotificationLogsOutAndReturnsSignedOut() async {
        let notifications = AsyncStream<Void>.makeStream()
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.date.now = Date(timeIntervalSince1970: 1_785_199_900)
            $0.authClient.restore = { Self.account }
            $0.authClient.logout = {}
            $0.appleCredentialStateClient.revocationEvents = { notifications.stream }
        }

        await store.send(.task)
        await store.receive(.restoreResponse(.signedIn(Self.account))) {
            $0.phase = .signedIn(Self.account)
        }
        notifications.continuation.yield(())
        await store.receive(.credentialRevokedNotification) {
            $0.phase = .clearingLocalCredentials(nil)
        }
        await store.receive(.credentialRevocationCleanupResponse(.success)) {
            $0.phase = .signedOut
        }
        notifications.continuation.finish()
    }

    func testSignInUsesHashedNonceForAppleAndRawNonceForServer() async {
        let nonce = AppleSignInNonce(rawValue: "raw-nonce", hashedValue: "hashed-nonce")
        let credential = AppleSignInCredential(
            userIdentifier: Self.appleUserIdentifier,
            identityToken: "identity-token",
            authorizationCode: "authorization-code"
        )
        let account = Self.account
        let store = TestStore(initialState: AuthFeature.State(phase: .signedOut)) {
            AuthFeature()
        } withDependencies: {
            $0.appleSignInNonce.generate = { nonce }
            $0.appleSignInClient.authorize = { hashedNonce in
                XCTAssertEqual(hashedNonce, nonce.hashedValue)
                return credential
            }
            $0.authClient.authenticate = { receivedCredential, rawNonce in
                XCTAssertEqual(receivedCredential, credential)
                XCTAssertEqual(rawNonce, nonce.rawValue)
                return account
            }
        }

        await store.send(.signInButtonTapped) {
            $0.phase = .signingIn
        }
        await store.receive(.signInResponse(.success(account))) {
            $0.phase = .signedIn(account)
        }
        XCTAssertFalse(String(describing: store.state).contains(Self.appleUserIdentifier))
    }

    func testCancelledSignInEmitsNoStaleResponseAfterAppleReturnsCredential() async {
        let nonce = AppleSignInNonce(rawValue: "raw-nonce", hashedValue: "hashed-nonce")
        let credential = AppleSignInCredential(
            userIdentifier: Self.appleUserIdentifier,
            identityToken: "identity-token",
            authorizationCode: "authorization-code"
        )
        let gate = CancellableAppleAuthorizationGate(credential: credential)
        let secondAuthorizationStarted = expectation(description: "retry authorization started")
        let authenticateCalled = expectation(description: "authenticate was called")
        authenticateCalled.isInverted = true
        let store = TestStore(initialState: AuthFeature.State(phase: .signedOut)) {
            AuthFeature()
        } withDependencies: {
            $0.appleSignInNonce.generate = { nonce }
            $0.appleSignInClient.authorize = { _ in
                try await gate.authorize {
                    secondAuthorizationStarted.fulfill()
                }
            }
            $0.authClient.authenticate = { _, _ in
                authenticateCalled.fulfill()
                return Self.account
            }
        }

        await store.send(.signInButtonTapped) {
            $0.phase = .signingIn
        }
        await store.send(.retrySignInTapped)
        await fulfillment(of: [secondAuthorizationStarted], timeout: 1)
        await gate.resumeCancelledAuthorization()
        await fulfillment(of: [authenticateCalled], timeout: 0.1)
        await store.finish()
    }

    func testAppleCancellationReturnsToSignedOutWithoutFalseFailure() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedOut)) {
            AuthFeature()
        } withDependencies: {
            $0.appleSignInNonce.generate = { .init(rawValue: "raw", hashedValue: "hashed") }
            $0.appleSignInClient.authorize = { _ in
                throw AuthClientError.authorizationCancelled
            }
        }

        await store.send(.signInButtonTapped) {
            $0.phase = .signingIn
        }
        await store.receive(.signInResponse(.failure(.authorizationCancelled))) {
            $0.phase = .signedOut
        }
    }

    func testCredentialPersistenceFailureRemainsVisibleAndRetryable() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedOut)) {
            AuthFeature()
        } withDependencies: {
            $0.appleSignInNonce.generate = { .init(rawValue: "raw", hashedValue: "hashed") }
            $0.appleSignInClient.authorize = { _ in
                .init(
                    userIdentifier: Self.appleUserIdentifier,
                    identityToken: "identity",
                    authorizationCode: "code"
                )
            }
            $0.authClient.authenticate = { _, _ in
                throw AuthClientError.localCredentialPersistenceFailed
            }
        }

        await store.send(.signInButtonTapped) {
            $0.phase = .signingIn
        }
        await store.receive(
            .signInResponse(.failure(.localCredentialPersistenceFailed))
        ) {
            $0.phase = .failed(.localCredentialPersistenceFailed)
        }
        await store.send(.retrySignInTapped) {
            $0.phase = .signingIn
        }
        await store.receive(
            .signInResponse(.failure(.localCredentialPersistenceFailed))
        ) {
            $0.phase = .failed(.localCredentialPersistenceFailed)
        }
    }

    func testDeletionCleanupFailureCannotMasqueradeAsSignedOut() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.account))) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.deleteAccount = {
                throw AuthClientError.localCredentialCleanupRequired
            }
            $0.authClient.clearLocalCredentials = {}
        }

        await store.send(.deleteAccountButtonTapped) {
            $0.phase = .confirmingAccountDeletion(Self.account)
        }
        await store.send(.confirmDeleteAccountTapped) {
            $0.phase = .deleting(Self.account)
        }
        await store.receive(
            .deleteAccountResponse(.failure(.localCredentialCleanupRequired))
        ) {
            $0.phase = .localCredentialCleanupRequired(nil)
        }
        await store.send(.retryLocalCleanupTapped) {
            $0.phase = .clearingLocalCredentials(nil)
        }
        await store.receive(.localCleanupResponse(.success)) {
            $0.phase = .signedOut
        }
    }

    func testDeletionAcceptedStatusIsPreservedWhileLocalCleanupRunsSeparately() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.account))) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.deleteAccount = {
                Self.deletionAcknowledgement
            }
            $0.authClient.clearLocalCredentials = {
                throw AuthClientError.localCredentialCleanupRequired
            }
        }

        await store.send(.deleteAccountButtonTapped) {
            $0.phase = .confirmingAccountDeletion(Self.account)
        }
        await store.send(.confirmDeleteAccountTapped) {
            $0.phase = .deleting(Self.account)
        }
        await store.receive(.deleteAccountResponse(.success(Self.deletionAcknowledgement))) {
            $0.phase = .clearingLocalCredentials(.accepted)
        }
        await store.receive(.localCleanupResponse(.failure(.localCredentialCleanupRequired))) {
            $0.phase = .localCredentialCleanupRequired(.accepted)
        }
    }

    func testDeletionStatusStateDoesNotExposeSubjectTimestampsOrRawBackendStatus() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.account))) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.deleteAccount = {
                AccountDeletionAcknowledgement(status: .accepted)
            }
            $0.authClient.clearLocalCredentials = {
                throw AuthClientError.localCredentialCleanupRequired
            }
        }

        await store.send(.deleteAccountButtonTapped) {
            $0.phase = .confirmingAccountDeletion(Self.account)
        }
        await store.send(.confirmDeleteAccountTapped) {
            $0.phase = .deleting(Self.account)
        }
        await store.receive(.deleteAccountResponse(.success(.init(status: .accepted)))) {
            $0.phase = .clearingLocalCredentials(.accepted)
        }
        await store.receive(.localCleanupResponse(.failure(.localCredentialCleanupRequired))) {
            $0.phase = .localCredentialCleanupRequired(.accepted)
        }
        XCTAssertFalse(String(describing: store.state.phase).contains("account-1"))
        XCTAssertFalse(String(describing: store.state.phase).contains("pending_deletion"))
        XCTAssertFalse(String(describing: store.state.phase).contains("1970"))
    }

    func testDeleteConfirmationCanBeCancelledWithoutLosingSignedInSession() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.account))) {
            AuthFeature()
        }

        await store.send(.deleteAccountButtonTapped) {
            $0.phase = .confirmingAccountDeletion(Self.account)
        }
        await store.send(.cancelDeleteAccountTapped) {
            $0.phase = .signedIn(Self.account)
        }
    }

    func testConfirmDeleteIgnoredOutsideConfirmationPhase() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.account))) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.deleteAccount = {
                XCTFail("Delete must require the explicit confirmation phase")
                throw AuthClientError.unavailable
            }
        }

        await store.send(.confirmDeleteAccountTapped)
    }

    func testLogoutClearsLocalSessionAndReturnsToSignedOut() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.account))) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.logout = {}
        }

        await store.send(.logoutButtonTapped) {
            $0.phase = .signingOut
        }
        await store.receive(.logoutResponse(.success)) {
            $0.phase = .signedOut
        }
    }

    private static let appleUserIdentifier = "apple-user-1"

    private static let tokens = AuthTokens(
        accountSubject: "account-1",
        accessToken: "access-1",
        refreshToken: "refresh-1",
        accessExpiresAt: Date(timeIntervalSince1970: 1_785_200_000),
        tokenType: "Bearer",
        appleUserIdentifier: appleUserIdentifier
    )

    private static let expiredTokens = AuthTokens(
        accountSubject: "account-1",
        accessToken: "access-expired",
        refreshToken: "refresh-1",
        accessExpiresAt: Date(timeIntervalSince1970: 1_785_200_000),
        tokenType: "Bearer",
        appleUserIdentifier: appleUserIdentifier
    )

    private static let account = tokens.authenticatedAccount

    private static let expiredAccount = expiredTokens.authenticatedAccount

    private static let deletionAcknowledgement = AccountDeletionAcknowledgement(
        status: .accepted
    )

    func assertStaleRestoreResponseIgnoredAfterSignInBegins(
        _ response: AuthFeature.RestoreResponse
    ) async {
        let store = TestStore(initialState: AuthFeature.State()) {
            AuthFeature()
        } withDependencies: {
            $0.appleSignInNonce.generate = { .init(rawValue: "raw", hashedValue: "hashed") }
            $0.appleSignInClient.authorize = { _ in
                throw CancellationError()
            }
        }

        await store.send(.signInButtonTapped) {
            $0.phase = .signingIn
        }
        await store.send(.restoreResponse(response))
        await store.finish()
    }
}

private actor CancellableAppleAuthorizationGate {
    private let credential: AppleSignInCredential
    private var callCount = 0
    private var continuation: CheckedContinuation<AppleSignInCredential, Never>?

    init(credential: AppleSignInCredential) {
        self.credential = credential
    }

    func authorize(
        onSecondAuthorization: @escaping @Sendable () -> Void
    ) async throws -> AppleSignInCredential {
        callCount += 1
        guard callCount == 1 else {
            onSecondAuthorization()
            throw CancellationError()
        }
        return await withCheckedContinuation { continuation in
            self.continuation = continuation
        }
    }

    func resumeCancelledAuthorization() {
        continuation?.resume(returning: credential)
        continuation = nil
    }
}

private actor CancellableRestoreGate {
    private let secondResult: AuthenticatedAccount?
    private var callCount = 0
    private var firstContinuation: CheckedContinuation<AuthenticatedAccount?, Error>?

    init(secondResult: AuthenticatedAccount?) {
        self.secondResult = secondResult
    }

    func restore(
        onSecondRestore: @escaping @Sendable () -> Void
    ) async throws -> AuthenticatedAccount? {
        callCount += 1
        guard callCount == 1 else {
            onSecondRestore()
            return secondResult
        }
        return try await withCheckedThrowingContinuation { continuation in
            self.firstContinuation = continuation
        }
    }

    func cancelFirstRestore() {
        firstContinuation?.resume(throwing: CancellationError())
        firstContinuation = nil
    }
}
