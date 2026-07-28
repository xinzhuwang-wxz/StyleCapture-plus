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

    func testSignInUsesHashedNonceForAppleAndRawNonceForServer() async {
        let nonce = AppleSignInNonce(rawValue: "raw-nonce", hashedValue: "hashed-nonce")
        let credential = AppleSignInCredential(
            identityToken: "identity-token",
            authorizationCode: "authorization-code"
        )
        let tokens = Self.tokens
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
                return tokens
            }
        }

        await store.send(.signInButtonTapped) {
            $0.phase = .signingIn
        }
        await store.receive(.signInResponse(.success(tokens))) {
            $0.phase = .signedIn(tokens)
        }
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
                .init(identityToken: "identity", authorizationCode: "code")
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
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.tokens))) {
            AuthFeature()
        } withDependencies: {
            $0.authClient.deleteAccount = {
                throw AuthClientError.localCredentialCleanupRequired
            }
            $0.authClient.clearLocalCredentials = {}
        }

        await store.send(.deleteAccountButtonTapped) {
            $0.phase = .confirmingAccountDeletion(Self.tokens)
        }
        await store.send(.confirmDeleteAccountTapped) {
            $0.phase = .deleting
        }
        await store.receive(
            .deleteAccountResponse(.failure(.localCredentialCleanupRequired))
        ) {
            $0.phase = .localCredentialCleanupRequired
        }
        await store.send(.retryLocalCleanupTapped) {
            $0.phase = .clearingLocalCredentials
        }
        await store.receive(.localCleanupResponse(.success)) {
            $0.phase = .signedOut
        }
    }

    func testDeleteConfirmationCanBeCancelledWithoutLosingSignedInSession() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.tokens))) {
            AuthFeature()
        }

        await store.send(.deleteAccountButtonTapped) {
            $0.phase = .confirmingAccountDeletion(Self.tokens)
        }
        await store.send(.cancelDeleteAccountTapped) {
            $0.phase = .signedIn(Self.tokens)
        }
    }

    func testLogoutClearsLocalSessionAndReturnsToSignedOut() async {
        let store = TestStore(initialState: AuthFeature.State(phase: .signedIn(Self.tokens))) {
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

    private static let tokens = AuthTokens(
        accountSubject: "account-1",
        accessToken: "access-1",
        refreshToken: "refresh-1",
        accessExpiresAt: Date(timeIntervalSince1970: 1_785_200_000),
        tokenType: "Bearer"
    )
}
