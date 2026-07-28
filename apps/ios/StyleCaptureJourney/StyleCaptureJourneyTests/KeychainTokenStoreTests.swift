import Foundation
import Security
import XCTest
@testable import StyleCaptureJourney

final class KeychainTokenStoreTests: XCTestCase {
    func testCorruptedPayloadIsNotTreatedAsSignedOut() async {
        let store = KeychainTokenStore(
            operations: KeychainOperations(
                copyMatching: { _ in (errSecSuccess, Data("not-json".utf8)) },
                add: { _ in errSecSuccess },
                update: { _, _ in errSecSuccess },
                delete: { _ in errSecSuccess }
            )
        )

        do {
            _ = try await store.load()
            XCTFail("Corrupted credentials must surface a recovery error")
        } catch {
            XCTAssertEqual(error as? SecureTokenStoreError, .invalidPayload)
        }
    }

    func testDuplicateSaveSurfacesKeychainUpdateFailure() async {
        let store = KeychainTokenStore(
            operations: KeychainOperations(
                copyMatching: { _ in (errSecItemNotFound, nil) },
                add: { _ in errSecDuplicateItem },
                update: { _, _ in errSecInteractionNotAllowed },
                delete: { _ in errSecSuccess }
            )
        )

        do {
            try await store.save(Self.tokens)
            XCTFail("A failed Keychain update must not acknowledge persistence")
        } catch {
            XCTAssertEqual(
                error as? SecureTokenStoreError,
                .operationFailed(.update, errSecInteractionNotAllowed)
            )
        }
    }

    func testClearSurfacesUnexpectedKeychainFailure() async {
        let store = KeychainTokenStore(
            operations: KeychainOperations(
                copyMatching: { _ in (errSecItemNotFound, nil) },
                add: { _ in errSecSuccess },
                update: { _, _ in errSecSuccess },
                delete: { _ in errSecInteractionNotAllowed }
            )
        )

        do {
            try await store.clear()
            XCTFail("A failed Keychain delete must remain recoverable")
        } catch {
            XCTAssertEqual(
                error as? SecureTokenStoreError,
                .operationFailed(.delete, errSecInteractionNotAllowed)
            )
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
