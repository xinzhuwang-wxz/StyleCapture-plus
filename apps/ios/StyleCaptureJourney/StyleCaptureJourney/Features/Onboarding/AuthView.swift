import ComposableArchitecture
import SwiftUI

struct AuthView: View {
    let store: StoreOf<AuthFeature>

    var body: some View {
        let copy = AuthViewContract.copy(for: store.phase)

        ScrollView {
            VStack(alignment: .leading, spacing: DesignTokens.spacingLarge) {
                hero(copy: copy)
                statusCard(copy: copy)
                actionArea(copy: copy)
            }
            .padding(DesignTokens.spacingLarge)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .background(DesignTokens.canvas)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(AuthViewContract.shellIdentifier(for: store.phase))
    }

    private func hero(copy: AuthViewContract.Copy) -> some View {
        VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
            Text(copy.heroTitle)
                .font(.largeTitle.weight(.bold))
                .foregroundStyle(DesignTokens.ink)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("auth.hero.title")

            Text(copy.heroSubtitle)
                .font(.headline)
                .foregroundStyle(DesignTokens.textMuted)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("auth.hero.subtitle")
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(copy.heroTitle)，\(copy.heroSubtitle)")
    }

    private func statusCard(copy: AuthViewContract.Copy) -> some View {
        VStack(alignment: .leading, spacing: DesignTokens.spacingMedium) {
            HStack(alignment: .top, spacing: DesignTokens.spacingMedium) {
                statusMark(for: copy)

                VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
                    Text(copy.statusTitle)
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(DesignTokens.ink)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("auth.status.title")

                    Text(copy.statusMessage)
                        .font(.body)
                        .foregroundStyle(DesignTokens.textMuted)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("auth.status.message")
                }
            }

            if let progressLabel = copy.progressLabel,
               let progressIdentifier = copy.progressIdentifier {
                ProgressView(progressLabel)
                    .tint(DesignTokens.primary)
                    .foregroundStyle(DesignTokens.textMuted)
                    .accessibilityIdentifier(progressIdentifier)
            }
        }
        .padding(DesignTokens.spacingLarge)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(DesignTokens.canvasLight)
        .clipShape(RoundedRectangle(cornerRadius: DesignTokens.cornerRadius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: DesignTokens.cornerRadius, style: .continuous)
                .stroke(DesignTokens.cardStroke, lineWidth: 1)
        )
        .shadow(color: DesignTokens.softShadow, radius: 20, x: 0, y: 12)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier(copy.cardIdentifier)
    }

    private func statusMark(for copy: AuthViewContract.Copy) -> some View {
        Text(copy.statusGlyph)
            .font(.title2.weight(.semibold))
            .foregroundStyle(copy.statusGlyph == "!" ? DesignTokens.danger : DesignTokens.primaryPressed)
            .frame(width: 44, height: 44)
            .background(copy.statusGlyph == "!" ? DesignTokens.dangerFill : DesignTokens.primaryFill.opacity(0.18))
            .clipShape(RoundedRectangle(cornerRadius: DesignTokens.cornerRadius, style: .continuous))
            .accessibilityHidden(true)
    }

    @ViewBuilder
    private func actionArea(copy: AuthViewContract.Copy) -> some View {
        switch store.phase {
        case .signedOut:
            AppleSignInTriggerButton(
                accessibilityIdentifier: "auth.cta.apple",
                accessibilityHint: "使用 Apple 账户登录后创建旅行穿搭计划"
            ) {
                store.send(.signInButtonTapped)
            }
            .frame(maxWidth: .infinity, minHeight: 48)

        case .restoring, .signingIn, .signingOut, .deleting, .clearingLocalCredentials:
            EmptyView()

        case .signedIn:
            VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
                Text(AuthViewContract.signedInPrivacyLabel)
                    .font(.footnote)
                    .foregroundStyle(DesignTokens.textMuted)
                    .accessibilityIdentifier("auth.account.privacyLabel")

                HStack(spacing: DesignTokens.spacingSmall) {
                    Button("退出登录") {
                        store.send(.logoutButtonTapped)
                    }
                    .buttonStyle(AuthActionButtonStyle(tone: .secondary))
                    .accessibilityIdentifier("auth.logout.button")
                    .accessibilityHint("退出当前 Apple 登录会话")

                    Button("删除账号", role: .destructive) {
                        store.send(.deleteAccountButtonTapped)
                    }
                    .buttonStyle(AuthActionButtonStyle(tone: .destructive))
                    .accessibilityIdentifier("auth.deleteAccount.button")
                    .accessibilityHint("进入账号删除确认")
                }
            }
            .accessibilityIdentifier("auth.account.controls")

        case .confirmingAccountDeletion:
            VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
                HStack(spacing: DesignTokens.spacingSmall) {
                    Button("取消") {
                        store.send(.cancelDeleteAccountTapped)
                    }
                    .buttonStyle(AuthActionButtonStyle(tone: .secondary))
                    .accessibilityIdentifier("auth.cancelDelete.button")
                    .accessibilityHint("返回已登录状态")

                    Button("确认删除", role: .destructive) {
                        store.send(.confirmDeleteAccountTapped)
                    }
                    .buttonStyle(AuthActionButtonStyle(tone: .destructive))
                    .accessibilityIdentifier("auth.confirmDelete.button")
                    .accessibilityHint("删除账号并清理本机凭据")
                }
            }
            .accessibilityIdentifier("auth.delete.confirmation")

        case .localCredentialCleanupRequired:
            Button("重新清理本机凭据") {
                store.send(.retryLocalCleanupTapped)
            }
            .buttonStyle(AuthActionButtonStyle(tone: .primary))
            .accessibilityIdentifier("auth.retryLocalCleanup.button")
            .accessibilityHint("再次尝试清理本机登录凭据")

        case .failed:
            AppleSignInTriggerButton(
                accessibilityIdentifier: "auth.retrySignIn.button",
                accessibilityHint: "再次尝试登录"
            ) {
                store.send(.retrySignInTapped)
            }
            .frame(maxWidth: .infinity, minHeight: 48)
        }
    }
}

struct AuthActionButtonStyle: ButtonStyle {
    enum Tone {
        case primary
        case secondary
        case destructive
    }

    let tone: Tone
    var expands = true

    func makeBody(configuration: Configuration) -> some View {
        let palette = colors

        return configuration.label
            .font(expands ? .headline : .subheadline.weight(.semibold))
            .multilineTextAlignment(.center)
            .frame(maxWidth: expands ? .infinity : nil)
            .padding(.vertical, expands ? DesignTokens.spacingMedium : DesignTokens.spacingSmall)
            .padding(.horizontal, expands ? DesignTokens.spacingLarge : DesignTokens.spacingMedium)
            .foregroundStyle(palette.foreground)
            .background(palette.background)
            .clipShape(RoundedRectangle(cornerRadius: DesignTokens.cornerRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: DesignTokens.cornerRadius, style: .continuous)
                    .stroke(palette.border, lineWidth: palette.borderWidth)
            )
            .shadow(color: palette.shadow, radius: 14, x: 0, y: 8)
            .opacity(configuration.isPressed ? 0.86 : 1.0)
    }

    private var colors: (foreground: Color, background: Color, border: Color, borderWidth: CGFloat, shadow: Color) {
        switch tone {
        case .primary:
            return (.white, DesignTokens.primary, .clear, 0, DesignTokens.softShadow)
        case .secondary:
            return (DesignTokens.primaryPressed, DesignTokens.canvasLight, DesignTokens.primaryFill, 1, .clear)
        case .destructive:
            return (DesignTokens.danger, DesignTokens.dangerFill, DesignTokens.danger.opacity(0.28), 1, .clear)
        }
    }
}

enum AuthViewContract {
    struct Copy: Equatable {
        let heroTitle: String
        let heroSubtitle: String
        let statusTitle: String
        let statusMessage: String
        let statusGlyph: String
        let cardIdentifier: String
        let progressLabel: String?
        let progressIdentifier: String?

    }
    static func copy(for phase: AuthFeature.Phase) -> Copy {
        func make(
            statusTitle: String,
            statusMessage: String,
            statusGlyph: String,
            cardIdentifier: String,
            progressLabel: String? = nil,
            progressIdentifier: String? = nil
        ) -> Copy {
            Copy(
                heroTitle: "StyleCapture 穿搭旅程",
                heroSubtitle: "用 Apple 登录，开始为 3–7 天行程整理穿搭。",
                statusTitle: statusTitle,
                statusMessage: statusMessage,
                statusGlyph: statusGlyph,
                cardIdentifier: cardIdentifier,
                progressLabel: progressLabel,
                progressIdentifier: progressIdentifier
            )
        }

        switch phase {
        case .restoring:
            return make(
                statusTitle: "正在恢复登录状态",
                statusMessage: "我们会检查本机 Apple 登录会话，准备继续你的 3–7 天旅行穿搭计划。",
                statusGlyph: "...",
                cardIdentifier: "auth.card.restoring",
                progressLabel: "正在恢复登录状态",
                progressIdentifier: "auth.progress.restoring"
            )

        case .signedOut:
            return make(
                statusTitle: "规划你的下一段旅程",
                statusMessage: "登录后保存目的地、天数和每日造型目标，让 Journey 帮你整理可执行穿搭清单。",
                statusGlyph: "+",
                cardIdentifier: "auth.card.signedOut"
            )

        case .signingIn:
            return make(
                statusTitle: "正在登录",
                statusMessage: "正在连接 Apple 授权，完成后会进入你的旅行穿搭 Journey。",
                statusGlyph: "...",
                cardIdentifier: "auth.card.signingIn",
                progressLabel: "正在登录",
                progressIdentifier: "auth.progress.signingIn"
            )

        case .signedIn:
            return make(
                statusTitle: "已登录 Apple 账户",
                statusMessage: "账号已连接，可以继续整理 3–7 天旅行穿搭。出于隐私保护，这里不显示账号原始标识。",
                statusGlyph: "✓",
                cardIdentifier: "auth.card.signedIn"
            )

        case .signingOut:
            return make(
                statusTitle: "正在退出登录",
                statusMessage: "正在结束本机会话，不会展示或泄露 Apple 账户原始标识。",
                statusGlyph: "...",
                cardIdentifier: "auth.card.signingOut",
                progressLabel: "正在退出登录",
                progressIdentifier: "auth.progress.signingOut"
            )

        case .confirmingAccountDeletion:
            return make(
                statusTitle: "确认删除账号？",
                statusMessage: "删除会撤销当前会话，并清理本机登录凭据。你的 3–7 天 Journey 规划入口会回到登录状态。",
                statusGlyph: "!",
                cardIdentifier: "auth.card.confirmDelete"
            )

        case .deleting:
            return make(
                statusTitle: "正在删除账号",
                statusMessage: "正在撤销服务端会话并清理本机登录凭据，请保持应用打开。",
                statusGlyph: "...",
                cardIdentifier: "auth.card.deleting",
                progressLabel: "正在删除账号",
                progressIdentifier: "auth.progress.deleting"
            )

        case .clearingLocalCredentials:
            return make(
                statusTitle: "正在清理本机登录凭据",
                statusMessage: "账号删除已完成，正在清理这台设备上的登录凭据。",
                statusGlyph: "...",
                cardIdentifier: "auth.card.cleanup",
                progressLabel: "正在清理本机登录凭据",
                progressIdentifier: "auth.progress.cleanup"
            )

        case .localCredentialCleanupRequired:
            return make(
                statusTitle: "本机凭据仍需清理",
                statusMessage: "账号已删除，但这台设备上的本机凭据还需要重新清理。请重试，确保下次打开时回到安全登录状态。",
                statusGlyph: "!",
                cardIdentifier: "auth.card.cleanupRecovery"
            )

        case let .failed(error):
            let message = failureMessage(for: error)
            return make(
                statusTitle: message.title,
                statusMessage: message.body,
                statusGlyph: "!",
                cardIdentifier: "auth.card.failure"
            )
        }
    }

    static func shellIdentifier(for phase: AuthFeature.Phase) -> String {
        switch phase {
        case .restoring:
            return "auth.shell.restoring"
        case .signedOut:
            return "auth.shell.signedOut"
        case .signingIn:
            return "auth.shell.signingIn"
        case .signedIn:
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

    static let signedInPrivacyLabel = "Apple 账户已连接；为保护隐私，不显示账号原始标识。"

    private static func failureMessage(for error: AuthClientError) -> (title: String, body: String) {
        switch error {
        case .authorizationUnavailable:
            return (
                "Apple 授权暂时不可用",
                "请先确认这台设备已在系统设置登录 Apple 账户，然后再继续创建 3–7 天 Journey。"
            )
        case .requestRejected:
            return (
                "登录请求未通过",
                "这次 Apple 登录请求没有被服务接受，请重新登录以继续规划旅行穿搭。"
            )
        case .accountConflict:
            return (
                "Apple 账户需要确认",
                "这个 Apple 账户与现有账号记录冲突，请稍后重试或换用正确账号继续 3–7 天 Journey。"
            )
        case .serviceUnavailable:
            return (
                "登录服务繁忙",
                "StyleCapture 登录服务暂时不可用，你的旅行穿搭计划入口会保留在这里，请稍后重试。"
            )
        case .invalidResponse:
            return (
                "登录响应异常",
                "服务返回的信息暂时无法完成登录，请重试以继续创建 3–7 天 Journey。"
            )
        case .networkUnavailable:
            return (
                "网络连接不可用",
                "请检查网络后重试，恢复连接后即可继续规划旅行穿搭。"
            )
        case .unavailable:
            return (
                "登录暂时不可用",
                "如果系统提示 Apple 授权不可用，请先到系统设置登录 Apple 账户；如果出现账户冲突、请求被拒绝、网络或服务繁忙，请稍后重试。"
            )
        case .invalidAppleCredential:
            return (
                "Apple 授权未通过",
                "这次 Apple 授权凭据无效，请重新登录以继续创建 3–7 天 Journey。"
            )
        case .authorizationCancelled:
            return (
                "已取消 Apple 登录",
                "你已取消授权。准备好后可以继续登录并规划旅行穿搭。"
            )
        case .sessionExpired:
            return (
                "会话已过期",
                "当前登录会话已失效，请重新登录以保护你的 Journey 数据。"
            )
        case .localCredentialPersistenceFailed:
            return (
                "本机登录凭据保存失败",
                "Apple 登录已返回，但本机登录凭据没有安全保存。请重试，避免下次打开时丢失会话。"
            )
        case .localCredentialCleanupRequired:
            return (
                "本机凭据仍需清理",
                "账号操作已完成，但本机凭据还需要重新清理。请重试清理，确保设备不会保留旧会话。"
            )
        }
    }
}
