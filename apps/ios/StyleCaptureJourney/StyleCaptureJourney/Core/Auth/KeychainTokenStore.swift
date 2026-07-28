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
    private let service: String
    private let account: String
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
        self.operations = operations
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
    }

    func load() throws -> AuthTokens? {
        var query = baseQuery()
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
        do {
            return try decoder.decode(AuthTokens.self, from: data)
        } catch {
            throw SecureTokenStoreError.invalidPayload
        }
    }

    func save(_ tokens: AuthTokens) throws {
        let data: Data
        do {
            data = try encoder.encode(tokens)
        } catch {
            throw SecureTokenStoreError.encodingFailed
        }
        var attributes = baseQuery()
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
            let updateStatus = operations.update(baseQuery(), update)
            guard updateStatus == errSecSuccess else {
                throw SecureTokenStoreError.operationFailed(.update, updateStatus)
            }
            return
        }
        throw SecureTokenStoreError.operationFailed(.add, status)
    }

    func clear() throws {
        let status = operations.delete(baseQuery())
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw SecureTokenStoreError.operationFailed(.delete, status)
        }
    }

    private func baseQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}
