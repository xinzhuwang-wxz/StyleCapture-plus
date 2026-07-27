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
