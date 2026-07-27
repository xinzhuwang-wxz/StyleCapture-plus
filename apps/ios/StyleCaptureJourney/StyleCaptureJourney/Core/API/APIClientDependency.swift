import ComposableArchitecture
import Foundation
import StyleCaptureAPI

public enum APIClientError: Error, Equatable, Sendable {
    case unavailable
}

public struct APIClient: Sendable {
    public var health: @Sendable () async throws -> Void

    public init(health: @escaping @Sendable () async throws -> Void) {
        self.health = health
    }
}

extension APIClient: DependencyKey {
    public static let liveValue = APIClient(health: {
        _ = GeneratedClientFactory.make(serverURL: URL(string: "https://api.stylecapture.local")!)
    })
    public static let testValue = APIClient(health: { throw APIClientError.unavailable })
}

public extension DependencyValues {
    var apiClient: APIClient {
        get { self[APIClient.self] }
        set { self[APIClient.self] = newValue }
    }
}
