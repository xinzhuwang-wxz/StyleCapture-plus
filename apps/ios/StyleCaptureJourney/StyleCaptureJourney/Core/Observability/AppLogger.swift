import ComposableArchitecture
import Foundation
import OSLog

public struct AppLogger: Sendable {
    public let logger: Logger

    public init(subsystem: String = "com.stylecapture.journey", category: String) {
        self.logger = Logger(subsystem: subsystem, category: category)
    }

    public func appLaunched() {
        logger.info("StyleCapture Journey app launched")
    }

    public func userRecoverableError(_ message: String) {
        logger.error("Recoverable error: \(message, privacy: .private)")
    }
}

extension AppLogger: DependencyKey {
    public static let liveValue = AppLogger(category: "app")
    public static let testValue = AppLogger(subsystem: "com.stylecapture.journey.tests", category: "test")
}

public extension DependencyValues {
    var appLogger: AppLogger {
        get { self[AppLogger.self] }
        set { self[AppLogger.self] = newValue }
    }
}
