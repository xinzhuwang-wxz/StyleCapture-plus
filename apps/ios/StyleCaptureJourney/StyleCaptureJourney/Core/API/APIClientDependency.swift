import ComposableArchitecture
import Foundation
import StyleCaptureAPI

struct APIClientConfiguration: Equatable, Sendable {
    var serverURL: URL

    static let live = APIClientConfiguration(serverURL: configuredServerURL())

    private static func configuredServerURL() -> URL {
        let configured = Bundle.main.object(
            forInfoDictionaryKey: "StyleCaptureAPIBaseURL"
        ) as? String
        if let configured,
           let url = URL(string: configured),
           isReleaseSafe(url) {
            return url
        }
        return URL(string: "https://api.stylecapture.app")!
    }

    private static func isReleaseSafe(_ url: URL) -> Bool {
        guard url.scheme == "https",
              let host = url.host?.lowercased() else {
            return false
        }
        return host != "localhost"
            && host != "127.0.0.1"
            && !host.hasSuffix(".local")
    }
}

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
        _ = GeneratedClientFactory.make(serverURL: APIClientConfiguration.live.serverURL)
    })
    public static let testValue = APIClient(health: { throw APIClientError.unavailable })
}

public extension DependencyValues {
    var apiClient: APIClient {
        get { self[APIClient.self] }
        set { self[APIClient.self] = newValue }
    }
}
