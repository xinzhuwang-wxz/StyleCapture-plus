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

    func testDeletionPendingMarkerRoundTripsWithoutTokenMaterial() async throws {
        let item = KeychainItemBox()
        let store = KeychainTokenStore(
            operations: KeychainOperations(
                copyMatching: { query in
                    guard let data = item.data(for: query) else {
                        return (errSecItemNotFound, nil)
                    }
                    return (errSecSuccess, data)
                },
                add: { attributes in
                    item.setData(from: attributes)
                    return errSecSuccess
                },
                update: { _, attributes in
                    item.setData(from: attributes)
                    return errSecSuccess
                },
                delete: { query in
                    item.deleteData(for: query)
                    return errSecSuccess
                }
            )
        )

        try await store.save(Self.tokens)
        XCTAssertEqual(try await store.load(), .authenticated(Self.tokens))

        let intent = try await store.markAccountDeletionPending()

        XCTAssertEqual(try await store.load(), .accountDeletionPending(intent))
        XCTAssertEqual(try await store.loadTokensForAccountDeletionRetry(), Self.tokens)
        let markerText = String(
            data: try XCTUnwrap(item.dataByAccount["stylecapture-session.account-deletion-intent"]),
            encoding: .utf8
        )
        XCTAssertFalse(try XCTUnwrap(markerText).contains("access-1"))
        XCTAssertFalse(try XCTUnwrap(markerText).contains("refresh-1"))
        let tokenText = String(
            data: try XCTUnwrap(item.dataByAccount["stylecapture-session"]),
            encoding: .utf8
        )
        XCTAssertTrue(try XCTUnwrap(tokenText).contains("access-1"))
    }

    func testDeletionPendingMarkerWriteFailureLeavesStoredTokensReadable() async throws {
        let encodedTokens = try JSONEncoder.iso8601AuthTokens.encode(Self.tokens)
        let store = KeychainTokenStore(
            operations: KeychainOperations(
                copyMatching: { query in
                    if (query[kSecAttrAccount as String] as? String) == "stylecapture-session" {
                        return (errSecSuccess, encodedTokens)
                    }
                    return (errSecItemNotFound, nil)
                },
                add: { _ in errSecInteractionNotAllowed },
                update: { _, _ in errSecInteractionNotAllowed },
                delete: { _ in errSecSuccess }
            )
        )

        do {
            try await store.markAccountDeletionPending()
            XCTFail("A failed marker write must fail closed before network submission")
        } catch {
            XCTAssertEqual(
                error as? SecureTokenStoreError,
                .operationFailed(.add, errSecInteractionNotAllowed)
            )
        }
        XCTAssertEqual(try await store.load(), .authenticated(Self.tokens))
    }

    func testDuplicateDeletionMarkerUpdateUsesExactMarkerAccountQuery() async throws {
        let item = KeychainItemBox()
        var updatedAccount: String?
        let store = KeychainTokenStore(
            operations: KeychainOperations(
                copyMatching: { query in
                    guard let data = item.data(for: query) else {
                        return (errSecItemNotFound, nil)
                    }
                    return (errSecSuccess, data)
                },
                add: { attributes in
                    guard (attributes[kSecAttrAccount as String] as? String)
                        == "stylecapture-session.account-deletion-intent" else {
                        item.setData(from: attributes)
                        return errSecSuccess
                    }
                    return errSecDuplicateItem
                },
                update: { query, attributes in
                    updatedAccount = query[kSecAttrAccount as String] as? String
                    item.setData(
                        attributes.merging(query) { attributesValue, _ in attributesValue }
                    )
                    return errSecSuccess
                },
                delete: { query in
                    item.deleteData(for: query)
                    return errSecSuccess
                }
            )
        )

        let intent = try await store.markAccountDeletionPending()

        XCTAssertEqual(updatedAccount, "stylecapture-session.account-deletion-intent")
        XCTAssertEqual(try await store.load(), .accountDeletionPending(intent))
        XCTAssertNil(item.dataByAccount["stylecapture-session"])
    }

    private static let tokens = AuthTokens(
        accountSubject: "account-1",
        accessToken: "access-1",
        refreshToken: "refresh-1",
        accessExpiresAt: Date(timeIntervalSince1970: 1_785_200_000),
        tokenType: "Bearer"
    )
}

private final class KeychainItemBox: @unchecked Sendable {
    var dataByAccount: [String: Data] = [:]

    func data(for query: [String: Any]) -> Data? {
        guard let account = query[kSecAttrAccount as String] as? String else {
            return nil
        }
        return dataByAccount[account]
    }

    func setData(from attributes: [String: Any]) {
        guard let account = attributes[kSecAttrAccount as String] as? String,
              let data = attributes[kSecValueData as String] as? Data else {
            return
        }
        dataByAccount[account] = data
    }

    func deleteData(for query: [String: Any]) {
        guard let account = query[kSecAttrAccount as String] as? String else {
            return
        }
        dataByAccount[account] = nil
    }
}

private extension JSONEncoder {
    static var iso8601AuthTokens: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }
}
