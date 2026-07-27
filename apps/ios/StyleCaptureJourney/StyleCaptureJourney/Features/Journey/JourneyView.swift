import ComposableArchitecture
import SwiftUI

struct JourneyView: View {
    let store: StoreOf<JourneyFeature>

    var body: some View {
        VStack(alignment: .leading, spacing: DesignTokens.spacingMedium) {
            Text("StyleCapture Journey")
                .font(.title2.weight(.semibold))
                .foregroundStyle(DesignTokens.ink)
                .accessibilityIdentifier("journey.title")

            Text(store.emptyStateTitle)
                .font(.body)
                .foregroundStyle(.secondary)
                .accessibilityIdentifier("journey.emptyState")

            Spacer(minLength: DesignTokens.spacingLarge)
        }
        .padding(DesignTokens.spacingLarge)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(DesignTokens.canvas)
        .navigationTitle("Journey")
        .onAppear {
            store.send(.appeared)
        }
    }
}
