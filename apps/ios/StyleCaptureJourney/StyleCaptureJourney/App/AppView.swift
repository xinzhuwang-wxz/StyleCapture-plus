import ComposableArchitecture
import SwiftUI

struct AppView: View {
    let store: StoreOf<AppFeature>

    var body: some View {
        @Bindable var store = store

        TabView(selection: $store.selectedTab) {
            NavigationStack {
                JourneyView(
                    store: store.scope(state: \.journey, action: \.journey)
                )
            }
            .tabItem {
                Label("Journey", systemImage: "suitcase")
            }
            .tag(AppFeature.Tab.journey)
        }
        .onAppear {
            store.send(.launch)
        }
        .onOpenURL { url in
            store.send(.deepLink(url))
        }
    }
}
