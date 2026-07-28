import AuthenticationServices
import SwiftUI

struct AppleSignInTriggerButton: UIViewRepresentable {
    let accessibilityIdentifier: String
    let accessibilityHint: String
    let action: () -> Void

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

    final class Coordinator: NSObject {
        var action: () -> Void

        init(action: @escaping () -> Void) {
            self.action = action
        }

        @objc func buttonTapped() {
            action()
        }
    }
}
