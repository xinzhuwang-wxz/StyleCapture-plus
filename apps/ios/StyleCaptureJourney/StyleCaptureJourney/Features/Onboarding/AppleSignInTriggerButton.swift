import AuthenticationServices
import SwiftUI

@MainActor
struct AppleSignInTriggerButton: UIViewRepresentable {
    let accessibilityIdentifier: String
    let accessibilityHint: String
    let action: @MainActor () -> Void

    func makeUIView(context: Context) -> ASAuthorizationAppleIDButton {
        let button = ASAuthorizationAppleIDButton(type: .signIn, style: .black)
        button.cornerRadius = DesignTokens.cornerRadius
        button.accessibilityIdentifier = accessibilityIdentifier
        button.accessibilityHint = accessibilityHint
        button.addTarget(
            context.coordinator,
            action: #selector(Coordinator.buttonTapped),
            for: .touchUpInside
        )
        return button
    }

    func updateUIView(_ uiView: ASAuthorizationAppleIDButton, context: Context) {
        uiView.accessibilityIdentifier = accessibilityIdentifier
        uiView.accessibilityHint = accessibilityHint
        context.coordinator.action = action
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(action: action)
    }

    @MainActor
    final class Coordinator: NSObject {
        var action: @MainActor () -> Void

        init(action: @escaping @MainActor () -> Void) {
            self.action = action
        }

        @objc func buttonTapped() {
            action()
        }
    }
}
