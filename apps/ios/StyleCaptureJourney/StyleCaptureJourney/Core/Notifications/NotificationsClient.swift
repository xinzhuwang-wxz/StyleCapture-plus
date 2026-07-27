import ComposableArchitecture
import Foundation
import UserNotifications

public struct NotificationsClient: Sendable {
    public var authorizationStatus: @Sendable () async -> UNAuthorizationStatus

    public init(authorizationStatus: @escaping @Sendable () async -> UNAuthorizationStatus) {
        self.authorizationStatus = authorizationStatus
    }
}

extension NotificationsClient: DependencyKey {
    public static let liveValue = NotificationsClient(authorizationStatus: {
        await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
    })
    public static let testValue = NotificationsClient(authorizationStatus: { .notDetermined })
}

public extension DependencyValues {
    var notificationsClient: NotificationsClient {
        get { self[NotificationsClient.self] }
        set { self[NotificationsClient.self] = newValue }
    }
}
