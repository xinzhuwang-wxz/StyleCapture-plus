import ComposableArchitecture
import SwiftUI

struct AppView: View {
    let store: StoreOf<AppFeature>

    var body: some View {
        TabView(
            selection: Binding(
                get: { store.selectedTab },
                set: { store.send(.selectedTabChanged($0)) }
            )
        ) {
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
