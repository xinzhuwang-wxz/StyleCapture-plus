import XCTest
@testable import StyleCaptureJourney

final class PrivacyAndBackgroundTests: XCTestCase {
    func testBackgroundTaskIdentifiersMatchPublishedAllowlist() {
        XCTAssertEqual(
            BackgroundTaskIdentifier.allCases.map(\.rawValue),
            [
                "com.stylecapture.journey.outbox-refresh",
                "com.stylecapture.journey.upload-resume",
                "com.stylecapture.journey.image-preprocess",
            ]
        )
    }

    func testBackgroundTaskKindsKeepOutboxOnRefreshAndHeavyWorkOnProcessing() {
        XCTAssertEqual(BackgroundTasksClient.kind(for: .outboxRefresh), .appRefresh)
        XCTAssertEqual(
            BackgroundTasksClient.kind(for: .uploadResume),
            .processing(requiresNetworkConnectivity: true)
        )
        XCTAssertEqual(
            BackgroundTasksClient.kind(for: .imagePreprocess),
            .processing(requiresNetworkConnectivity: false)
        )
    }

    func testBackgroundSchedulingDeniedIsTyped() async {
        let client = BackgroundTasksClient(
            permittedIdentifiers: { BackgroundTaskIdentifier.allCases.map(\.rawValue) },
            requestKind: BackgroundTasksClient.kind(for:),
            register: { _, _ in },
            schedule: { identifier in
                throw BackgroundTaskFailure.schedulerRejected(identifier)
            },
            cancel: { _ in },
            recordLifecycle: { _ in }
        )

        do {
            try await client.schedule(.uploadResume)
            XCTFail("Expected scheduling to fail")
        } catch {
            XCTAssertEqual(error as? BackgroundTaskFailure, .schedulerRejected(.uploadResume))
        }
    }

    func testBackgroundLifecycleSeamsCoverRegistrationExpirationAndRelaunch() async throws {
        let recorder = BackgroundLifecycleRecorder()
        let client = BackgroundTasksClient(
            permittedIdentifiers: { BackgroundTaskIdentifier.allCases.map(\.rawValue) },
            requestKind: BackgroundTasksClient.kind(for:),
            register: { identifier, handlers in
                await recorder.record(.registered(identifier))
                await recorder.record(.launched(identifier))
                await handlers.expire()
                let success = await handlers.execute()
                await recorder.record(.completed(identifier, success: success))
            },
            schedule: { _ in },
            cancel: { _ in },
            recordLifecycle: { await recorder.record($0) }
        )

        try await client.register(
            .outboxRefresh,
            .init(
                execute: { true },
                expire: {
                    await client.recordLifecycle(.expired(.outboxRefresh))
                    await client.recordLifecycle(.terminatedBeforeCompletion(.outboxRefresh))
                }
            )
        )

        XCTAssertEqual(
            await recorder.events(),
            [
                .registered(.outboxRefresh),
                .launched(.outboxRefresh),
                .expired(.outboxRefresh),
                .terminatedBeforeCompletion(.outboxRefresh),
                .completed(.outboxRefresh, success: true),
            ]
        )
    }

    func testLoggerAcceptsSensitiveRecoverableErrorsThroughPrivateAPI() {
        let logger = AppLogger(category: "privacy-test")
        logger.userRecoverableError("city=Shanghai hotel=redacted-by-oslog")
    }
}

private actor BackgroundLifecycleRecorder {
    private var recorded: [BackgroundTaskLifecycleEvent] = []

    func record(_ event: BackgroundTaskLifecycleEvent) {
        recorded.append(event)
    }

    func events() -> [BackgroundTaskLifecycleEvent] {
        recorded
    }
}
