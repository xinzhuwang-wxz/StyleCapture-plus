import AuthenticationServices
import ComposableArchitecture
import CryptoKit
import Foundation
import Security
import UIKit

struct AppleSignInNonce: Equatable, Sendable {
    let rawValue: String
    let hashedValue: String
}

struct AppleSignInCredential: Equatable, Sendable {
    let identityToken: String
    let authorizationCode: String
}

struct AppleSignInAuthorizationRequest: Equatable, @unchecked Sendable {
    let scopes: [ASAuthorization.Scope]
    let nonce: String
}

enum AppleSignInAuthorizationCredential: Equatable, Sendable {
    case appleID(identityToken: Data?, authorizationCode: Data?)
    case unsupportedCredential
}

protocol AppleSignInAuthorizationSession: Sendable {
    func authorize(
        _ request: AppleSignInAuthorizationRequest
    ) async throws -> AppleSignInAuthorizationCredential
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

extension AppleSignInClient {
    static func live(
        authorizationSession: any AppleSignInAuthorizationSession
    ) -> AppleSignInClient {
        AppleSignInClient { hashedNonce in
            do {
                let credential = try await authorizationSession.authorize(
                    AppleSignInAuthorizationRequest(
                        scopes: [.fullName, .email],
                        nonce: hashedNonce
                    )
                )
                return try Self.mapCredential(credential)
            } catch {
                if Self.isAppleCancellation(error) {
                    throw AuthClientError.authorizationCancelled
                }
                throw AuthClientError.invalidAppleCredential
            }
        }
    }

    private static func mapCredential(
        _ credential: AppleSignInAuthorizationCredential
    ) throws -> AppleSignInCredential {
        guard case let .appleID(identityTokenData, authorizationCodeData) = credential,
              let identityTokenData,
              let authorizationCodeData,
              let identityToken = String(data: identityTokenData, encoding: .utf8),
              let authorizationCode = String(data: authorizationCodeData, encoding: .utf8)
        else {
            throw AuthClientError.invalidAppleCredential
        }

        return AppleSignInCredential(
            identityToken: identityToken,
            authorizationCode: authorizationCode
        )
    }

    private static func isAppleCancellation(_ error: Error) -> Bool {
        let nsError = error as NSError
        return nsError.domain == ASAuthorizationError.errorDomain
            && nsError.code == ASAuthorizationError.canceled.rawValue
    }
}

extension AppleSignInClient: DependencyKey {
    static let liveValue = AppleSignInClient.live(
        authorizationSession: LiveAppleSignInAuthorizationSession()
    )
    static let testValue = liveValue
}

struct LiveAppleSignInAuthorizationSession: AppleSignInAuthorizationSession {
    func authorize(
        _ request: AppleSignInAuthorizationRequest
    ) async throws -> AppleSignInAuthorizationCredential {
        let coordinator = await AppleSignInAuthorizationCoordinator(request: request)
        return try await coordinator.start()
    }
}

@MainActor
private final class AppleSignInAuthorizationCoordinator: NSObject {
    private let request: AppleSignInAuthorizationRequest
    private var controller: ASAuthorizationController?
    private var continuation: CheckedContinuation<AppleSignInAuthorizationCredential, Error>?
    private var didResume = false

    init(request: AppleSignInAuthorizationRequest) {
        self.request = request
    }

    func start() async throws -> AppleSignInAuthorizationCredential {
        try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation

            let appleRequest = ASAuthorizationAppleIDProvider().createRequest()
            appleRequest.requestedScopes = request.scopes
            appleRequest.nonce = request.nonce

            let controller = ASAuthorizationController(authorizationRequests: [appleRequest])
            controller.delegate = self
            controller.presentationContextProvider = self
            self.controller = controller
            controller.performRequests()
        }
    }

    private func resume(
        with result: Result<AppleSignInAuthorizationCredential, Error>
    ) {
        guard !didResume else { return }
        didResume = true

        let continuation = continuation
        self.continuation = nil
        controller = nil

        continuation?.resume(with: result)
    }
}

extension AppleSignInAuthorizationCoordinator: ASAuthorizationControllerDelegate {
    func authorizationController(
        controller: ASAuthorizationController,
        didCompleteWithAuthorization authorization: ASAuthorization
    ) {
        guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential else {
            resume(with: .success(.unsupportedCredential))
            return
        }

        resume(
            with: .success(
                .appleID(
                    identityToken: credential.identityToken,
                    authorizationCode: credential.authorizationCode
                )
            )
        )
    }

    func authorizationController(
        controller: ASAuthorizationController,
        didCompleteWithError error: Error
    ) {
        resume(with: .failure(error))
    }
}

extension AppleSignInAuthorizationCoordinator: ASAuthorizationControllerPresentationContextProviding {
    func presentationAnchor(
        for controller: ASAuthorizationController
    ) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
            .first { $0.isKeyWindow } ?? UIWindow(frame: .zero)
    }
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
