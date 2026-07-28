import AuthenticationServices
import Foundation
import XCTest
@testable import StyleCaptureJourney

final class AppleCredentialStateDependencyTests: XCTestCase {
    func testLiveMapsProviderCredentialStatesAndForwardsUserIdentifier() async throws {
        let lookup = ImmediateCredentialStateLookup(result: .success(.transferred))
        let provider = LiveAppleCredentialStateProvider(
            credentialStateLookup: lookup.getCredentialState
        )
        let client = AppleCredentialStateClient.live(provider: provider)

        let state = try await client.credentialState("apple-user-id")

        XCTAssertEqual(state, .transferred)
        XCTAssertEqual(lookup.requestedUserIdentifiers, ["apple-user-id"])
    }

    func testLiveMapsCredentialLookupFailureToUnavailable() async throws {
        let lookup = ImmediateCredentialStateLookup(result: .failure(CredentialLookupError()))
        let provider = LiveAppleCredentialStateProvider(
            credentialStateLookup: lookup.getCredentialState
        )
        let client = AppleCredentialStateClient.live(provider: provider)

        let state = try await client.credentialState("apple-user-id")

        XCTAssertEqual(state, .unavailable)
    }

    func testLiveClientCredentialLookupCancellationThrowsCancellationErrorAndIgnoresLateCallback() async {
        let lookup = DelayedCredentialStateLookup()
        let provider = LiveAppleCredentialStateProvider(
            credentialStateLookup: lookup.getCredentialState
        )
        let client = AppleCredentialStateClient.live(provider: provider)
        let task = Task {
            try await client.credentialState("apple-user-id")
        }

        await lookup.waitUntilRequested()
        task.cancel()

        await XCTAssertThrowsErrorAsync(try await task.value) { error in
            XCTAssertTrue(error is CancellationError)
        }
        lookup.returnLateCredentialState(.authorized)
        XCTAssertEqual(lookup.requestedUserIdentifiers, ["apple-user-id"])
    }

    func testLiveCredentialLookupCancellationThrowsCancellationErrorAndIgnoresLateCallback() async {
        let lookup = DelayedCredentialStateLookup()
        let provider = LiveAppleCredentialStateProvider(
            credentialStateLookup: lookup.getCredentialState
        )
        let task = Task {
            try await provider.credentialState(forUserID: "apple-user-id")
        }

        await lookup.waitUntilRequested()
        task.cancel()

        await XCTAssertThrowsErrorAsync(try await task.value) { error in
            XCTAssertTrue(error is CancellationError)
        }
        lookup.returnLateCredentialState(.authorized)
        XCTAssertEqual(lookup.requestedUserIdentifiers, ["apple-user-id"])
    }

    func testRevocationEventsForwardTheProviderStream() async {
        let source = DeterministicRevocationEventSource()
        let provider = LiveAppleCredentialStateProvider(revocationEventsSource: source.stream)
        let client = AppleCredentialStateClient.live(provider: provider)
        let receivedEvent = expectation(description: "received revocation")
        let task = Task {
            for await _ in client.revocationEvents() {
                receivedEvent.fulfill()
                break
            }
        }

        await source.waitUntilSubscribed()
        source.yieldRevocation()
        await fulfillment(of: [receivedEvent], timeout: 1)
        task.cancel()
    }

    func testLiveRevocationEventsForwardInjectedEventSourceDeterministically() async {
        let source = DeterministicRevocationEventSource()
        let provider = LiveAppleCredentialStateProvider(revocationEventsSource: source.stream)
        let receivedEvent = expectation(description: "received Apple revocation")
        let task = Task {
            for await _ in provider.revocationEvents() {
                receivedEvent.fulfill()
                break
            }
        }

        await source.waitUntilSubscribed()
        source.yieldRevocation()
        await fulfillment(of: [receivedEvent], timeout: 1)
        task.cancel()
    }

    func testLiveRevocationEventsTerminateWhenConsumerIsCancelled() async {
        let provider = LiveAppleCredentialStateProvider(notificationCenter: NotificationCenter())
        let subscribed = expectation(description: "revocation stream subscribed")
        let terminated = expectation(description: "revocation stream terminated")
        let task = Task {
            var events = provider.revocationEvents().makeAsyncIterator()
            subscribed.fulfill()
            let nextEvent = await events.next()
            XCTAssertNil(nextEvent)
            terminated.fulfill()
        }

        await fulfillment(of: [subscribed], timeout: 1)
        task.cancel()

        await fulfillment(of: [terminated], timeout: 1)
    }

    func testTestDependencyFailsClosedAndDoesNotProduceRevocations() async throws {
        let client = AppleCredentialStateClient.unavailable
        let state = try await client.credentialState("apple-user-id")
        var revocations = client.revocationEvents().makeAsyncIterator()

        XCTAssertEqual(state, .unavailable)
        let nextRevocation = await revocations.next()
        XCTAssertNil(nextRevocation)
    }
}

private final class ImmediateCredentialStateLookup: @unchecked Sendable {
    private let result: Result<ASAuthorizationAppleIDProvider.CredentialState, Error>
    private(set) var requestedUserIdentifiers: [String] = []

    init(result: Result<ASAuthorizationAppleIDProvider.CredentialState, Error>) {
        self.result = result
    }

    func getCredentialState(
        forUserID userID: String,
        completion: @escaping (ASAuthorizationAppleIDProvider.CredentialState, (any Error)?) -> Void
    ) {
        requestedUserIdentifiers.append(userID)
        switch result {
        case let .success(state):
            completion(state, nil)
        case let .failure(error):
            completion(.notFound, error)
        }
    }
}

private struct CredentialLookupError: Error {}

private final class DelayedCredentialStateLookup: @unchecked Sendable {
    private let lock = NSLock()
    private var completion:
        ((ASAuthorizationAppleIDProvider.CredentialState, (any Error)?) -> Void)?
    private var requestedUserIDs: [String] = []
    private var waiters: [CheckedContinuation<Void, Never>] = []

    var requestedUserIdentifiers: [String] {
        lock.lock()
        let requestedUserIDs = requestedUserIDs
        lock.unlock()
        return requestedUserIDs
    }

    func getCredentialState(
        forUserID userID: String,
        completion: @escaping (ASAuthorizationAppleIDProvider.CredentialState, (any Error)?) -> Void
    ) {
        lock.lock()
        requestedUserIDs.append(userID)
        self.completion = completion
        let pendingWaiters = waiters
        waiters.removeAll()
        lock.unlock()

        pendingWaiters.forEach { $0.resume() }
    }

    func waitUntilRequested() async {
        await withCheckedContinuation { continuation in
            lock.lock()
            if completion != nil {
                lock.unlock()
                continuation.resume()
            } else {
                waiters.append(continuation)
                lock.unlock()
            }
        }
    }

    func returnLateCredentialState(
        _ state: ASAuthorizationAppleIDProvider.CredentialState
    ) {
        lock.lock()
        let completion = completion
        lock.unlock()

        completion?(state, nil)
    }
}

private final class DeterministicRevocationEventSource: @unchecked Sendable {
    private let lock = NSLock()
    private let eventStream: AsyncStream<Void>
    private let continuation: AsyncStream<Void>.Continuation
    private var subscribed = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    init() {
        (eventStream, continuation) = AsyncStream.makeStream()
    }

    func stream() -> AsyncStream<Void> {
        AsyncStream { downstream in
            let task = Task {
                markSubscribed()
                for await event in eventStream {
                    downstream.yield(event)
                }
                downstream.finish()
            }
            downstream.onTermination = { @Sendable _ in
                task.cancel()
            }
        }
    }

    func waitUntilSubscribed() async {
        await withCheckedContinuation { continuation in
            lock.lock()
            if subscribed {
                lock.unlock()
                continuation.resume()
            } else {
                waiters.append(continuation)
                lock.unlock()
            }
        }
    }

    func yieldRevocation() {
        continuation.yield(())
    }

    private func markSubscribed() {
        lock.lock()
        subscribed = true
        let pendingWaiters = waiters
        waiters.removeAll()
        lock.unlock()

        pendingWaiters.forEach { $0.resume() }
    }
}

private func XCTAssertThrowsErrorAsync<T>(
    _ expression: @autoclosure () async throws -> T,
    _ verify: (Error) -> Void,
    file: StaticString = #filePath,
    line: UInt = #line
) async {
    do {
        _ = try await expression()
        XCTFail("Expected error to be thrown", file: file, line: line)
    } catch {
        verify(error)
    }
}
