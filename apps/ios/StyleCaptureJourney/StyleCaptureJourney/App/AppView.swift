import ComposableArchitecture
import SwiftUI

struct AppView: View {
    let store: StoreOf<AppFeature>

    var body: some View {
        Group {
            if store.auth.phase.isAuthenticated {
                TabView(
                    selection: Binding(
                        get: { store.selectedTab },
                        set: { store.send(.selectedTabChanged($0)) }
                    )
                ) {
                    NavigationStack {
                        VStack(spacing: 0) {
                            signedInAccountControls
                            JourneyView(
                                store: store.scope(state: \.journey, action: \.journey)
                            )
                        }
                    }
                    .tabItem {
                        Label("Journey", systemImage: "suitcase")
                    }
                    .tag(AppFeature.Tab.journey)
                }
            } else {
                AuthView(
                    store: store.scope(state: \.auth, action: \.auth)
                )
            }
        }
        .onAppear {
            store.send(.launch)
        }
        .onOpenURL { url in
            store.send(.deepLink(url))
        }
    }

    @ViewBuilder
    private var signedInAccountControls: some View {
        switch store.auth.phase {
        case let .signedIn(tokens), let .refreshing(tokens):
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("StyleCapture")
                        .font(.headline)
                    Text(tokens.accountSubject)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("退出登录") {
                    store.send(.auth(.logoutButtonTapped))
                }
                .buttonStyle(.bordered)
                .accessibilityIdentifier("auth.logout.button")

                Button("删除账号", role: .destructive) {
                    store.send(.auth(.deleteAccountButtonTapped))
                }
                .buttonStyle(.bordered)
                .accessibilityIdentifier("auth.deleteAccount.button")
            }
            .padding(.horizontal, DesignTokens.spacingLarge)
            .padding(.vertical, DesignTokens.spacingSmall)
            .background(DesignTokens.canvasLight)
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("auth.account.controls")

        default:
            EmptyView()
        }
    }
}

private extension AuthFeature.Phase {
    var isAuthenticated: Bool {
        switch self {
        case .signedIn, .refreshing:
            return true
        case .restoring,
             .signedOut,
             .signingIn,
             .signingOut,
             .confirmingAccountDeletion,
             .deleting,
             .clearingLocalCredentials,
             .localCredentialCleanupRequired,
             .failed:
            return false
        }
    }
}
