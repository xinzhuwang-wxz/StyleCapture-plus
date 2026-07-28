import Foundation
import HTTPTypes
import OpenAPIRuntime
import OpenAPIURLSession

public struct BearerAuthorizationMiddleware: ClientMiddleware {
    private let accessToken: String

    public init(accessToken: String) {
        self.accessToken = accessToken
    }

    public func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        var authorizedRequest = request
        authorizedRequest.headerFields[.authorization] = "Bearer \(accessToken)"
        return try await next(authorizedRequest, body, baseURL)
    }
}

public enum GeneratedClientFactory {
    public static func make(
        serverURL: URL,
        middlewares: [any ClientMiddleware] = []
    ) -> Client {
        Client(
            serverURL: serverURL,
            transport: URLSessionTransport(),
            middlewares: middlewares
        )
    }
}
