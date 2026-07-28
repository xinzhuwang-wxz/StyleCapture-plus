import ComposableArchitecture
import SwiftUI

struct AuthView: View {
    let store: StoreOf<AuthFeature>

    var body: some View {
        VStack(alignment: .leading, spacing: DesignTokens.spacingMedium) {
            Text("StyleCapture")
                .font(.largeTitle.weight(.semibold))
                .foregroundStyle(DesignTokens.ink)

            Text("用 Apple 登录，开始为 3-7 天行程整理穿搭。")
                .font(.body)
                .foregroundStyle(.secondary)

            content

            Spacer(minLength: DesignTokens.spacingLarge)
        }
        .padding(DesignTokens.spacingLarge)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(DesignTokens.canvas)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AuthViewContract.shellIdentifier(for: store.phase))
    }

    @ViewBuilder
    private var content: some View {
        switch store.phase {
        case .restoring:
            ProgressView("正在恢复登录状态")
                .accessibilityIdentifier("auth.progress.restoring")

        case .signedOut:
            Button("通过 Apple 登录") {
                store.send(.signInButtonTapped)
            }
            .buttonStyle(.borderedProminent)
            .accessibilityIdentifier("auth.cta.apple")

        case .signingIn:
            ProgressView("正在登录")
                .accessibilityIdentifier("auth.progress.signingIn")

        case let .signedIn(tokens), let .refreshing(tokens):
            VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
                Text("已登录")
                    .font(.headline)
                Text(tokens.accountSubject)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                HStack {
                    Button("退出登录") {
                        store.send(.logoutButtonTapped)
                    }
                    .buttonStyle(.bordered)
                    .accessibilityIdentifier("auth.logout.button")

                    Button("删除账号", role: .destructive) {
                        store.send(.deleteAccountButtonTapped)
                    }
                    .buttonStyle(.bordered)
                    .accessibilityIdentifier("auth.deleteAccount.button")
                }
            }
            .accessibilityIdentifier("auth.account.controls")

        case .signingOut:
            ProgressView("正在退出登录")
                .accessibilityIdentifier("auth.progress.signingOut")

        case .confirmingAccountDeletion:
            VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
                Text("确认删除账号？")
                    .font(.headline)
                Text("删除会撤销会话，并清理本机登录凭据。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                HStack {
                    Button("取消") {
                        store.send(.cancelDeleteAccountTapped)
                    }
                    .buttonStyle(.bordered)
                    .accessibilityIdentifier("auth.cancelDelete.button")

                    Button("确认删除", role: .destructive) {
                        store.send(.confirmDeleteAccountTapped)
                    }
                    .buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("auth.confirmDelete.button")
                }
            }
            .accessibilityIdentifier("auth.delete.confirmation")

        case .deleting:
            ProgressView("正在删除账号")
                .accessibilityIdentifier("auth.progress.deleting")

        case .clearingLocalCredentials:
            ProgressView("正在清理本机登录凭据")
                .accessibilityIdentifier("auth.progress.cleanup")

        case .localCredentialCleanupRequired:
            VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
                Text("账号已删除，本机凭据仍需清理")
                    .font(.headline)
                Button("重新清理本机凭据") {
                    store.send(.retryLocalCleanupTapped)
                }
                .buttonStyle(.borderedProminent)
                .accessibilityIdentifier("auth.retryLocalCleanup.button")
            }

        case .failed:
            VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
                Text("登录暂时不可用")
                    .font(.headline)
                Button("重试") {
                    store.send(.retrySignInTapped)
                }
                .buttonStyle(.borderedProminent)
                .accessibilityIdentifier("auth.retrySignIn.button")
            }
        }
    }
}

enum AuthViewContract {
    static func shellIdentifier(for phase: AuthFeature.Phase) -> String {
        switch phase {
        case .restoring:
            return "auth.shell.restoring"
        case .signedOut:
            return "auth.shell.signedOut"
        case .signingIn:
            return "auth.shell.signingIn"
        case .signedIn, .refreshing:
            return "auth.shell.signedIn"
        case .signingOut:
            return "auth.shell.signingOut"
        case .confirmingAccountDeletion:
            return "auth.shell.confirmDelete"
        case .deleting:
            return "auth.shell.deleting"
        case .clearingLocalCredentials:
            return "auth.shell.cleanup"
        case .localCredentialCleanupRequired:
            return "auth.shell.cleanupRecovery"
        case .failed:
            return "auth.shell.failure"
        }
    }

    static func accessibilityIdentifiers(for state: AuthFeature.State) -> [String] {
        switch state.phase {
        case .restoring:
            return ["auth.shell.restoring", "auth.progress.restoring"]
        case .signedOut:
            return ["auth.shell.signedOut", "auth.cta.apple"]
        case .signingIn:
            return ["auth.shell.signingIn", "auth.progress.signingIn"]
        case .signedIn, .refreshing:
            return [
                "auth.shell.signedIn",
                "auth.account.controls",
                "auth.logout.button",
                "auth.deleteAccount.button",
            ]
        case .signingOut:
            return ["auth.shell.signingOut", "auth.progress.signingOut"]
        case .confirmingAccountDeletion:
            return [
                "auth.shell.confirmDelete",
                "auth.delete.confirmation",
                "auth.cancelDelete.button",
                "auth.confirmDelete.button",
            ]
        case .deleting:
            return ["auth.shell.deleting", "auth.progress.deleting"]
        case .clearingLocalCredentials:
            return ["auth.shell.cleanup", "auth.progress.cleanup"]
        case .localCredentialCleanupRequired:
            return ["auth.shell.cleanupRecovery", "auth.retryLocalCleanup.button"]
        case .failed:
            return ["auth.shell.failure", "auth.retrySignIn.button"]
        }
    }
}
