import ComposableArchitecture
import Foundation

@Reducer
struct JourneyFeature {
    @ObservableState
    struct State: Equatable {
        var isLoading = false
        var emptyStateTitle = "No journeys yet"
    }

    enum Action: Equatable {
        case appeared
        case startLoading
        case cancelLoading
        case loadingFinished
    }

    private enum LoadingID: Hashable {
        case load
    }

    @Dependency(\.continuousClock) var clock

    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .appeared:
                return .none

            case .startLoading:
                state.isLoading = true
                return .run { send in
                    try await clock.sleep(for: .seconds(60))
                    await send(.loadingFinished)
                }
                .cancellable(id: LoadingID.load, cancelInFlight: true)

            case .cancelLoading:
                state.isLoading = false
                return .cancel(id: LoadingID.load)

            case .loadingFinished:
                state.isLoading = false
                return .none
            }
        }
    }
}
