import ComposableArchitecture
import SwiftUI

@main
struct StyleCaptureJourneyApp: App {
    private let store: StoreOf<AppFeature> = {
        #if DEBUG
        SimulatorAuthHarness.makeStore()
        #else
        Store(initialState: AppFeature.State()) {
            AppFeature()
        }
        #endif
    }()

    var body: some Scene {
        WindowGroup {
            AppView(store: store)
        }
    }
}
