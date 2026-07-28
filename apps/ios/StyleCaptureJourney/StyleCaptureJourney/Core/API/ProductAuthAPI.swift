import Foundation
import OpenAPIRuntime
import StyleCaptureAPI

struct ProductAuthAPI {
    enum APIError: Error, Equatable, Sendable {
        case invalidCredential
        case invalidRequest
        case sessionExpired
        case conflict
        case serverUnavailable
        case unexpectedResponse
        case transportFailure
    }

    private enum Operation: Equatable {
        case authenticate
        case refresh
        case deleteAccount
    }

    private enum ResponseStatus {
        case badRequest
        case unauthorized
        case notFound
        case conflict
        case gone
        case contentTooLarge
        case unsupportedMediaType
        case unprocessableContent
        case serviceUnavailable
    }

    private let client: Client
    private let authorizedClient: @Sendable (String) -> Client

    init(clientFactory: @escaping @Sendable ([any ClientMiddleware]) -> Client) {
        client = clientFactory([])
        authorizedClient = { accessToken in
            clientFactory([BearerAuthorizationMiddleware(accessToken: accessToken)])
        }
    }

    static let live = ProductAuthAPI(
        clientFactory: { middlewares in
            GeneratedClientFactory.make(
                serverURL: APIClientConfiguration.live.serverURL,
                middlewares: middlewares
            )
        }
    )

    func authenticate(_ request: AppleSignInRequest) async throws -> AuthTokens {
        do {
            let output = try await client.authenticateWithAppleV1AuthApplePost(
                .init(body: .json(Self.appleAuthBody(from: request)))
            )
            switch output {
            case let .ok(response):
                switch response.body {
                case let .json(tokens):
                    return Self.authTokens(from: tokens)
                }
            default:
                throw Self.error(from: output)
            }
        } catch let error as CancellationError {
            throw error
        } catch let error as APIError {
            throw error
        } catch let error as ClientError where error.response != nil {
            throw APIError.unexpectedResponse
        } catch is DecodingError {
            throw APIError.unexpectedResponse
        } catch {
            throw APIError.transportFailure
        }
    }

    func refresh(refreshToken: String) async throws -> AuthTokens {
        do {
            let output = try await client.refreshSessionV1AuthRefreshPost(
                .init(body: .json(.init(refreshToken: refreshToken)))
            )
            switch output {
            case let .ok(response):
                switch response.body {
                case let .json(tokens):
                    return Self.authTokens(from: tokens)
                }
            default:
                throw Self.error(from: output)
            }
        } catch let error as CancellationError {
            throw error
        } catch let error as APIError {
            throw error
        } catch let error as ClientError where error.response != nil {
            throw APIError.unexpectedResponse
        } catch is DecodingError {
            throw APIError.unexpectedResponse
        } catch {
            throw APIError.transportFailure
        }
    }

    func deleteAccount(
        accessToken: String,
        idempotencyKey: String
    ) async throws -> AccountDeletionAcknowledgement {
        do {
            let output = try await authorizedClient(accessToken).deleteAccountV1AccountDeletePost(
                headers: .init(idempotencyKey: idempotencyKey)
            )
            guard case let .accepted(response) = output else {
                throw Self.error(from: output)
            }
            switch response.body {
            case let .json(deletion):
                return try Self.accountDeletionAcknowledgement(from: deletion)
            }
        } catch let error as CancellationError {
            throw error
        } catch let error as APIError {
            throw error
        } catch let error as ClientError where error.response != nil {
            throw APIError.unexpectedResponse
        } catch is DecodingError {
            throw APIError.unexpectedResponse
        } catch {
            throw APIError.transportFailure
        }
    }

    static func appleAuthBody(
        from request: AppleSignInRequest
    ) -> Components.Schemas.AppleAuthBody {
        .init(
            authorizationCode: request.authorizationCode,
            deviceName: request.deviceName,
            identityToken: request.identityToken,
            nonce: request.nonce
        )
    }

    static func authTokens(
        from response: Components.Schemas.AuthTokenResponse
    ) -> AuthTokens {
        AuthTokens(
            accountSubject: response.accountSubject,
            accessToken: response.accessToken,
            refreshToken: response.refreshToken,
            accessExpiresAt: response.accessExpiresAt,
            tokenType: response.tokenType
        )
    }

    static func accountDeletionAcknowledgement(
        from response: Components.Schemas.DeletionResponse
    ) throws -> AccountDeletionAcknowledgement {
        AccountDeletionAcknowledgement(
            status: try Self.accountDeletionStatus(from: response.status)
        )
    }

    private static func accountDeletionStatus(from status: String) throws -> AccountDeletionStatus {
        switch status {
        case "pending_deletion", "frozen":
            return .accepted
        default:
            throw APIError.unexpectedResponse
        }
    }

    private static func error(
        from output: Operations.AuthenticateWithAppleV1AuthApplePost.Output
    ) -> APIError {
        switch output {
        case let .badRequest(response):
            apiError(operation: .authenticate, status: .badRequest, code: try? response.body.json.error.code)
        case let .unauthorized(response):
            apiError(operation: .authenticate, status: .unauthorized, code: try? response.body.json.error.code)
        case let .notFound(response):
            apiError(operation: .authenticate, status: .notFound, code: try? response.body.json.error.code)
        case let .conflict(response):
            apiError(operation: .authenticate, status: .conflict, code: try? response.body.json.error.code)
        case let .gone(response):
            apiError(operation: .authenticate, status: .gone, code: try? response.body.json.error.code)
        case let .contentTooLarge(response):
            apiError(operation: .authenticate, status: .contentTooLarge, code: try? response.body.json.error.code)
        case let .unsupportedMediaType(response):
            apiError(operation: .authenticate, status: .unsupportedMediaType, code: try? response.body.json.error.code)
        case let .unprocessableContent(response):
            apiError(operation: .authenticate, status: .unprocessableContent, code: try? response.body.json.error.code)
        case let .serviceUnavailable(response):
            apiError(operation: .authenticate, status: .serviceUnavailable, code: try? response.body.json.error.code)
        case .ok, .undocumented:
            .unexpectedResponse
        }
    }

    private static func error(
        from output: Operations.RefreshSessionV1AuthRefreshPost.Output
    ) -> APIError {
        switch output {
        case let .badRequest(response):
            apiError(operation: .refresh, status: .badRequest, code: try? response.body.json.error.code)
        case let .unauthorized(response):
            apiError(operation: .refresh, status: .unauthorized, code: try? response.body.json.error.code)
        case let .notFound(response):
            apiError(operation: .refresh, status: .notFound, code: try? response.body.json.error.code)
        case let .conflict(response):
            apiError(operation: .refresh, status: .conflict, code: try? response.body.json.error.code)
        case let .gone(response):
            apiError(operation: .refresh, status: .gone, code: try? response.body.json.error.code)
        case let .contentTooLarge(response):
            apiError(operation: .refresh, status: .contentTooLarge, code: try? response.body.json.error.code)
        case let .unsupportedMediaType(response):
            apiError(operation: .refresh, status: .unsupportedMediaType, code: try? response.body.json.error.code)
        case let .unprocessableContent(response):
            apiError(operation: .refresh, status: .unprocessableContent, code: try? response.body.json.error.code)
        case let .serviceUnavailable(response):
            apiError(operation: .refresh, status: .serviceUnavailable, code: try? response.body.json.error.code)
        case .ok, .undocumented:
            .unexpectedResponse
        }
    }

    private static func error(
        from output: Operations.DeleteAccountV1AccountDeletePost.Output
    ) -> APIError {
        switch output {
        case let .badRequest(response):
            apiError(operation: .deleteAccount, status: .badRequest, code: try? response.body.json.error.code)
        case let .unauthorized(response):
            apiError(operation: .deleteAccount, status: .unauthorized, code: try? response.body.json.error.code)
        case let .notFound(response):
            apiError(operation: .deleteAccount, status: .notFound, code: try? response.body.json.error.code)
        case let .conflict(response):
            apiError(operation: .deleteAccount, status: .conflict, code: try? response.body.json.error.code)
        case let .gone(response):
            apiError(operation: .deleteAccount, status: .gone, code: try? response.body.json.error.code)
        case let .contentTooLarge(response):
            apiError(operation: .deleteAccount, status: .contentTooLarge, code: try? response.body.json.error.code)
        case let .unsupportedMediaType(response):
            apiError(operation: .deleteAccount, status: .unsupportedMediaType, code: try? response.body.json.error.code)
        case let .unprocessableContent(response):
            apiError(operation: .deleteAccount, status: .unprocessableContent, code: try? response.body.json.error.code)
        case let .serviceUnavailable(response):
            apiError(operation: .deleteAccount, status: .serviceUnavailable, code: try? response.body.json.error.code)
        case .accepted, .undocumented:
            .unexpectedResponse
        }
    }

    private static func apiError(
        operation: Operation,
        status: ResponseStatus,
        code: String?
    ) -> APIError {
        switch operation {
        case .authenticate:
            switch code {
            case "apple_identity_invalid", "apple_authorization_failed", "apple_nonce_invalid":
                return .invalidCredential
            case "request_invalid":
                return .invalidRequest
            case "authorization_code_replayed", "account_binding_conflict":
                return .conflict
            case "apple_identity_unavailable", "apple_authorization_unavailable":
                return .serverUnavailable
            default:
                break
            }
        case .refresh:
            switch code {
            case "request_invalid":
                return .invalidRequest
            case "session_invalid", "session_revoked", "refresh_token_expired", "account_deleted":
                return .sessionExpired
            case "refresh_token_reused":
                return .conflict
            case "processing_dispatch_unavailable":
                return .serverUnavailable
            default:
                break
            }
        case .deleteAccount:
            switch code {
            case "request_invalid":
                return .invalidRequest
            case "session_invalid", "session_revoked", "account_deleted":
                return .sessionExpired
            case "account_delete_conflict":
                return .conflict
            case "processing_dispatch_unavailable":
                return .serverUnavailable
            default:
                break
            }
        }

        switch status {
        case .badRequest, .unprocessableContent:
            return .invalidRequest
        case .unauthorized where operation != .authenticate:
            return .sessionExpired
        case .conflict:
            return .conflict
        case .serviceUnavailable:
            return .serverUnavailable
        case .unauthorized, .notFound, .gone, .contentTooLarge, .unsupportedMediaType:
            return .unexpectedResponse
        }
    }
}
