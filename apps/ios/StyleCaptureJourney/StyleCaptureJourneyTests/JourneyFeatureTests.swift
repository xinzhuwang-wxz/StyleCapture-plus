import ComposableArchitecture
import XCTest
@testable import StyleCaptureJourney

@MainActor
final class JourneyFeatureTests: XCTestCase {
    func testEmptyJourneyShellStartsWithoutItems() async {
        let store = TestStore(initialState: JourneyFeature.State()) {
            JourneyFeature()
        }

        await store.send(.appeared)
        XCTAssertEqual(store.state.emptyStateTitle, "No journeys yet")
        XCTAssertFalse(store.state.isLoading)
    }

    func testLoadingEffectCanBeCancelled() async {
        let clock = TestClock()
        let store = TestStore(initialState: JourneyFeature.State()) {
            JourneyFeature()
        } withDependencies: {
            $0.continuousClock = clock
        }

        await store.send(.startLoading) {
            $0.isLoading = true
        }
        await store.send(.cancelLoading) {
            $0.isLoading = false
        }
        await clock.advance(by: .seconds(60))
    }
}
