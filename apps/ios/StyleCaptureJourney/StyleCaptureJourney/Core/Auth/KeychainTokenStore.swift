import Foundation
import Security

enum KeychainOperation: Equatable, Sendable {
    case read
    case add
    case update
    case delete
}

enum SecureTokenStoreError: Error, Equatable, Sendable {
    case invalidPayload
    case encodingFailed
    case operationFailed(KeychainOperation, OSStatus)
}

struct KeychainOperations: @unchecked Sendable {
    var copyMatching: ([String: Any]) -> (OSStatus, Data?)
    var add: ([String: Any]) -> OSStatus
    var update: ([String: Any], [String: Any]) -> OSStatus
    var delete: ([String: Any]) -> OSStatus

    static let live = KeychainOperations(
        copyMatching: { query in
            var result: CFTypeRef?
            let status = SecItemCopyMatching(query as CFDictionary, &result)
            return (status, result as? Data)
        },
        add: { attributes in
            SecItemAdd(attributes as CFDictionary, nil)
        },
        update: { query, attributes in
            SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        },
        delete: { query in
            SecItemDelete(query as CFDictionary)
        }
    )
}

actor KeychainTokenStore: TokenStore {
    private struct AccountDeletionIntentPayload: Codable, Equatable {
        var version: Int
        var idempotencyKey: String
        var phase: AccountDeletionIntentPhase
    }

    private static let accountDeletionIntentVersion = 1

    private let service: String
    private let account: String
    private let accountDeletionIntentAccount: String
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    private let operations: KeychainOperations

    init(
        service: String = "com.stylecapture.journey.auth",
        account: String = "stylecapture-session",
        operations: KeychainOperations = .live
    ) {
        self.service = service
        self.account = account
        self.accountDeletionIntentAccount = "\(account).account-deletion-intent"
        self.operations = operations
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
    }

    func load() throws -> StoredAuthSession {
        if let intent = try loadAccountDeletionIntent() {
            return .accountDeletionPending(intent)
        }
        guard let tokens = try loadTokens() else {
            return .signedOut
        }
        return .authenticated(tokens)
    }

    func save(_ tokens: AuthTokens) throws {
        let data: Data
        do {
            data = try encoder.encode(tokens)
        } catch {
            throw SecureTokenStoreError.encodingFailed
        }
        try deleteAccountDeletionIntent()
        try write(data, query: baseQuery(account: account))
    }

    func loadTokensForAccountDeletionRetry() throws -> AuthTokens? {
        try loadTokens()
    }

    func markAccountDeletionPending() throws -> AccountDeletionIntent {
        if let intent = try loadAccountDeletionIntent() {
            return intent
        }
        let intent = AccountDeletionIntent()
        try writeAccountDeletionIntent(intent)
        return intent
    }

    func markAccountDeletionAccepted(_ intent: AccountDeletionIntent) throws {
        try writeAccountDeletionIntent(
            AccountDeletionIntent(
                idempotencyKey: intent.idempotencyKey,
                phase: .accepted
            )
        )
        let status = operations.delete(baseQuery(account: account))
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw SecureTokenStoreError.operationFailed(.delete, status)
        }
    }

    func clear() throws {
        let tokenStatus = operations.delete(baseQuery(account: account))
        guard tokenStatus == errSecSuccess || tokenStatus == errSecItemNotFound else {
            throw SecureTokenStoreError.operationFailed(.delete, tokenStatus)
        }
        try deleteAccountDeletionIntent()
    }

    private func loadTokens() throws -> AuthTokens? {
        guard let data = try loadData(query: baseQuery(account: account)) else {
            return nil
        }
        do {
            return try decoder.decode(AuthTokens.self, from: data)
        } catch {
            throw SecureTokenStoreError.invalidPayload
        }
    }

    private func loadAccountDeletionIntent() throws -> AccountDeletionIntent? {
        guard let data = try loadData(query: baseQuery(account: accountDeletionIntentAccount)) else {
            return nil
        }
        do {
            let payload = try decoder.decode(AccountDeletionIntentPayload.self, from: data)
            guard payload.version == Self.accountDeletionIntentVersion,
                  !payload.idempotencyKey.isEmpty else {
                throw SecureTokenStoreError.invalidPayload
            }
            return AccountDeletionIntent(
                idempotencyKey: payload.idempotencyKey,
                phase: payload.phase
            )
        } catch let error as SecureTokenStoreError {
            throw error
        } catch {
            throw SecureTokenStoreError.invalidPayload
        }
    }

    private func loadData(query: [String: Any]) throws -> Data? {
        var query = query
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        let (status, data) = operations.copyMatching(query)
        if status == errSecItemNotFound {
            return nil
        }
        guard status == errSecSuccess else {
            throw SecureTokenStoreError.operationFailed(.read, status)
        }
        guard let data else {
            throw SecureTokenStoreError.invalidPayload
        }
        return data
    }

    private func writeAccountDeletionIntent(_ intent: AccountDeletionIntent) throws {
        let payload = AccountDeletionIntentPayload(
            version: Self.accountDeletionIntentVersion,
            idempotencyKey: intent.idempotencyKey,
            phase: intent.phase
        )
        let data: Data
        do {
            data = try encoder.encode(payload)
        } catch {
            throw SecureTokenStoreError.encodingFailed
        }
        try write(data, query: baseQuery(account: accountDeletionIntentAccount))
    }

    private func deleteAccountDeletionIntent() throws {
        let status = operations.delete(baseQuery(account: accountDeletionIntentAccount))
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw SecureTokenStoreError.operationFailed(.delete, status)
        }
    }

    private func write(_ data: Data, query: [String: Any]) throws {
        var attributes = query
        attributes[kSecValueData as String] = data
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly

        let status = operations.add(attributes)
        if status == errSecSuccess {
            return
        }
        if status == errSecDuplicateItem {
            let update: [String: Any] = [
                kSecValueData as String: data,
                kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            ]
            let updateStatus = operations.update(query, update)
            guard updateStatus == errSecSuccess else {
                throw SecureTokenStoreError.operationFailed(.update, updateStatus)
            }
            return
        }
        throw SecureTokenStoreError.operationFailed(.add, status)
    }

    private func baseQuery(account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}
