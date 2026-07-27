import ComposableArchitecture
import Foundation
import StoreKit

public struct StoreKitClient: Sendable {
    public var currentEntitlements: @Sendable () async throws -> [String]

    public init(currentEntitlements: @escaping @Sendable () async throws -> [String]) {
        self.currentEntitlements = currentEntitlements
    }
}

extension StoreKitClient: DependencyKey {
    public static let liveValue = StoreKitClient(currentEntitlements: { [] })
    public static let testValue = StoreKitClient(currentEntitlements: { [] })
}

public extension DependencyValues {
    var storeKitClient: StoreKitClient {
        get { self[StoreKitClient.self] }
        set { self[StoreKitClient.self] = newValue }
    }
}
