import ComposableArchitecture
import SwiftUI

struct AppView: View {
    let store: StoreOf<AppFeature>

    var body: some View {
        Group {
            if let error = store.launchError {
                launchFailureView(error: error)
            } else if store.auth.phase.showsAuthenticatedShell {
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

    private func launchFailureView(error: AppFeature.AppError) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DesignTokens.spacingLarge) {
                VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
                    Text("StyleCapture 穿搭旅程")
                        .font(.largeTitle.weight(.bold))
                        .foregroundStyle(DesignTokens.ink)
                        .fixedSize(horizontal: false, vertical: true)

                    Text("启动准备尚未完成")
                        .font(.headline)
                        .foregroundStyle(DesignTokens.textMuted)
                        .fixedSize(horizontal: false, vertical: true)
                }

                VStack(alignment: .leading, spacing: DesignTokens.spacingMedium) {
                    HStack(alignment: .top, spacing: DesignTokens.spacingMedium) {
                        Text("!")
                            .font(.title2.weight(.semibold))
                            .foregroundStyle(DesignTokens.danger)
                            .frame(width: 44, height: 44)
                            .background(DesignTokens.dangerFill)
                            .clipShape(
                                RoundedRectangle(
                                    cornerRadius: DesignTokens.cornerRadius,
                                    style: .continuous
                                )
                            )
                            .accessibilityHidden(true)

                        VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
                            Text(launchFailureTitle(for: error))
                                .font(.title3.weight(.semibold))
                                .foregroundStyle(DesignTokens.ink)
                                .fixedSize(horizontal: false, vertical: true)

                            Text(launchFailureMessage(for: error))
                                .font(.body)
                                .foregroundStyle(DesignTokens.textMuted)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(DesignTokens.spacingLarge)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(DesignTokens.canvasLight)
                .clipShape(
                    RoundedRectangle(
                        cornerRadius: DesignTokens.cornerRadius,
                        style: .continuous
                    )
                )
                .overlay(
                    RoundedRectangle(
                        cornerRadius: DesignTokens.cornerRadius,
                        style: .continuous
                    )
                    .stroke(DesignTokens.cardStroke, lineWidth: 1)
                )
                .shadow(color: DesignTokens.softShadow, radius: 20, x: 0, y: 12)
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("app.launchFailure.card")

                Button("重试启动") {
                    store.send(.launch)
                }
                .buttonStyle(AuthActionButtonStyle(tone: .primary))
                .accessibilityIdentifier("app.launchFailure.retry.button")
                .accessibilityHint("重新执行启动准备并恢复登录状态")
            }
            .padding(DesignTokens.spacingLarge)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .background(DesignTokens.canvas)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("app.launchFailure.shell")
    }

    private func launchFailureTitle(for error: AppFeature.AppError) -> String {
        switch error {
        case .databaseMigrationFailed:
            return "本机资料库准备失败"
        }
    }

    private func launchFailureMessage(for error: AppFeature.AppError) -> String {
        switch error {
        case .databaseMigrationFailed:
            return "StyleCapture 需要先完成本机资料库迁移，才能安全恢复登录状态并打开 Journey。请重试启动准备。"
        }
    }

    @ViewBuilder
    private var signedInAccountControls: some View {
        switch store.auth.phase {
        case .signedIn:
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("StyleCapture 穿搭旅程")
                        .font(.headline)
                    Text(AuthViewContract.signedInPrivacyLabel)
                        .font(.caption)
                        .foregroundStyle(DesignTokens.textMuted)
                }
                Spacer()
                Button("退出登录") {
                    store.send(.auth(.logoutButtonTapped))
                }
                .buttonStyle(AuthActionButtonStyle(tone: .secondary, expands: false))
                .accessibilityIdentifier("auth.logout.button")

                Button("删除账号", role: .destructive) {
                    store.send(.auth(.deleteAccountButtonTapped))
                }
                .buttonStyle(AuthActionButtonStyle(tone: .destructive, expands: false))
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
    var showsAuthenticatedShell: Bool {
        switch self {
        case .signedIn:
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
