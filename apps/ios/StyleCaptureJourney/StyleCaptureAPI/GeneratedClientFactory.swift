import Foundation
import OpenAPIURLSession

public enum GeneratedClientFactory {
    public static func make(serverURL: URL) -> Client {
        Client(serverURL: serverURL, transport: URLSessionTransport())
    }
}
