import ComposableArchitecture
import CryptoKit
import Foundation
import Security

struct AppleSignInNonce: Equatable, Sendable {
    let rawValue: String
    let hashedValue: String
}

struct AppleSignInCredential: Equatable, Sendable {
    let identityToken: String
    let authorizationCode: String
}

struct AppleSignInNonceClient: Sendable {
    var generate: @Sendable () throws -> AppleSignInNonce
}

extension AppleSignInNonceClient: DependencyKey {
    static let liveValue = AppleSignInNonceClient {
        var bytes = [UInt8](repeating: 0, count: 32)
        let status = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        guard status == errSecSuccess else {
            throw AuthClientError.unavailable
        }
        let rawValue = Data(bytes)
            .base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
        let hashedValue = SHA256.hash(data: Data(rawValue.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
        return AppleSignInNonce(rawValue: rawValue, hashedValue: hashedValue)
    }

    static let testValue = AppleSignInNonceClient {
        throw AuthClientError.unavailable
    }
}

struct AppleSignInClient: Sendable {
    var authorize: @Sendable (String) async throws -> AppleSignInCredential
}

extension AppleSignInClient: DependencyKey {
    static let liveValue = AppleSignInClient {
        _ in throw AuthClientError.unavailable
    }
    static let testValue = liveValue
}

extension DependencyValues {
    var appleSignInNonce: AppleSignInNonceClient {
        get { self[AppleSignInNonceClient.self] }
        set { self[AppleSignInNonceClient.self] = newValue }
    }

    var appleSignInClient: AppleSignInClient {
        get { self[AppleSignInClient.self] }
        set { self[AppleSignInClient.self] = newValue }
    }
}
