@preconcurrency import BackgroundTasks
import ComposableArchitecture
import Foundation

public enum BackgroundTaskIdentifier: String, CaseIterable, Equatable, Sendable {
    case outboxRefresh = "com.stylecapture.journey.outbox-refresh"
    case uploadResume = "com.stylecapture.journey.upload-resume"
    case imagePreprocess = "com.stylecapture.journey.image-preprocess"
}

public enum BackgroundTaskRequestKind: Equatable, Sendable {
    case appRefresh
    case processing(requiresNetworkConnectivity: Bool)
}

public enum BackgroundTaskFailure: Error, Equatable, Sendable {
    case identifierNotPermitted(BackgroundTaskIdentifier)
    case registrationRejected(BackgroundTaskIdentifier)
    case schedulerRejected(BackgroundTaskIdentifier)
}

public enum BackgroundTaskLifecycleEvent: Equatable, Sendable {
    case registered(BackgroundTaskIdentifier)
    case launched(BackgroundTaskIdentifier)
    case expired(BackgroundTaskIdentifier)
    case completed(BackgroundTaskIdentifier, success: Bool)
    case terminatedBeforeCompletion(BackgroundTaskIdentifier)
}

public struct BackgroundTaskHandlers: Sendable {
    public var execute: @Sendable () async -> Bool
    public var expire: @Sendable () async -> Void

    public init(
        execute: @escaping @Sendable () async -> Bool,
        expire: @escaping @Sendable () async -> Void
    ) {
        self.execute = execute
        self.expire = expire
    }
}

public struct BackgroundTasksClient: Sendable {
    public var permittedIdentifiers: @Sendable () -> [String]
    public var requestKind: @Sendable (BackgroundTaskIdentifier) -> BackgroundTaskRequestKind
    public var register: @Sendable (BackgroundTaskIdentifier, BackgroundTaskHandlers) async throws -> Void
    public var schedule: @Sendable (BackgroundTaskIdentifier) async throws -> Void
    public var cancel: @Sendable (BackgroundTaskIdentifier) async -> Void
    public var recordLifecycle: @Sendable (BackgroundTaskLifecycleEvent) async -> Void

    public init(
        permittedIdentifiers: @escaping @Sendable () -> [String],
        requestKind: @escaping @Sendable (BackgroundTaskIdentifier) -> BackgroundTaskRequestKind,
        register: @escaping @Sendable (BackgroundTaskIdentifier, BackgroundTaskHandlers) async throws -> Void,
        schedule: @escaping @Sendable (BackgroundTaskIdentifier) async throws -> Void,
        cancel: @escaping @Sendable (BackgroundTaskIdentifier) async -> Void,
        recordLifecycle: @escaping @Sendable (BackgroundTaskLifecycleEvent) async -> Void
    ) {
        self.permittedIdentifiers = permittedIdentifiers
        self.requestKind = requestKind
        self.register = register
        self.schedule = schedule
        self.cancel = cancel
        self.recordLifecycle = recordLifecycle
    }

    public static func kind(for identifier: BackgroundTaskIdentifier) -> BackgroundTaskRequestKind {
        switch identifier {
        case .outboxRefresh:
            return .appRefresh
        case .uploadResume:
            return .processing(requiresNetworkConnectivity: true)
        case .imagePreprocess:
            return .processing(requiresNetworkConnectivity: false)
        }
    }
}

extension BackgroundTasksClient: DependencyKey {
    public static let liveValue = BackgroundTasksClient(
        permittedIdentifiers: { BackgroundTaskIdentifier.allCases.map(\.rawValue) },
        requestKind: BackgroundTasksClient.kind(for:),
        register: { identifier, handlers in
            guard BackgroundTaskIdentifier.allCases.contains(identifier) else {
                throw BackgroundTaskFailure.identifierNotPermitted(identifier)
            }
            let registered = BGTaskScheduler.shared.register(
                forTaskWithIdentifier: identifier.rawValue,
                using: nil
            ) { task in
                task.expirationHandler = {
                    Task {
                        await handlers.expire()
                    }
                }
                Task {
                    let success = await handlers.execute()
                    task.setTaskCompleted(success: success)
                }
            }
            if !registered {
                throw BackgroundTaskFailure.registrationRejected(identifier)
            }
        },
        schedule: { identifier in
            guard BackgroundTaskIdentifier.allCases.contains(identifier) else {
                throw BackgroundTaskFailure.identifierNotPermitted(identifier)
            }
            let request: BGTaskRequest
            switch BackgroundTasksClient.kind(for: identifier) {
            case .appRefresh:
                request = BGAppRefreshTaskRequest(identifier: identifier.rawValue)
            case let .processing(requiresNetworkConnectivity):
                let processingRequest = BGProcessingTaskRequest(identifier: identifier.rawValue)
                processingRequest.requiresNetworkConnectivity = requiresNetworkConnectivity
                request = processingRequest
            }
            do {
                try BGTaskScheduler.shared.submit(request)
            } catch {
                throw BackgroundTaskFailure.schedulerRejected(identifier)
            }
        },
        cancel: { identifier in
            BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: identifier.rawValue)
        },
        recordLifecycle: { _ in }
    )

    public static let testValue = BackgroundTasksClient(
        permittedIdentifiers: { BackgroundTaskIdentifier.allCases.map(\.rawValue) },
        requestKind: BackgroundTasksClient.kind(for:),
        register: { _, _ in },
        schedule: { _ in },
        cancel: { _ in },
        recordLifecycle: { _ in }
    )
}

public extension DependencyValues {
    var backgroundTasksClient: BackgroundTasksClient {
        get { self[BackgroundTasksClient.self] }
        set { self[BackgroundTasksClient.self] = newValue }
    }
}
