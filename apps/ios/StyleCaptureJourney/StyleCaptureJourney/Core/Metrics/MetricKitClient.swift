import ComposableArchitecture
import Foundation
@preconcurrency import MetricKit

public struct MetricKitClient: Sendable {
    public var addSubscriber: @Sendable @MainActor (any MXMetricManagerSubscriber) -> Void
    public var removeSubscriber: @Sendable @MainActor (any MXMetricManagerSubscriber) -> Void

    public init(
        addSubscriber: @escaping @Sendable @MainActor (any MXMetricManagerSubscriber) -> Void,
        removeSubscriber: @escaping @Sendable @MainActor (any MXMetricManagerSubscriber) -> Void
    ) {
        self.addSubscriber = addSubscriber
        self.removeSubscriber = removeSubscriber
    }
}

extension MetricKitClient: DependencyKey {
    public static let liveValue = MetricKitClient(
        addSubscriber: { subscriber in
            MXMetricManager.shared.add(subscriber)
        },
        removeSubscriber: { subscriber in
            MXMetricManager.shared.remove(subscriber)
        }
    )

    public static let testValue = MetricKitClient(
        addSubscriber: { _ in },
        removeSubscriber: { _ in }
    )
}

public extension DependencyValues {
    var metricKitClient: MetricKitClient {
        get { self[MetricKitClient.self] }
        set { self[MetricKitClient.self] = newValue }
    }
}
