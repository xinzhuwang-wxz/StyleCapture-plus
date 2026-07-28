import ComposableArchitecture
import SwiftUI

struct JourneyView: View {
    let store: StoreOf<JourneyFeature>

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DesignTokens.spacingLarge) {
                heroSection
                outcomeCard
                emptyStateCard
                primaryAction
            }
            .padding(DesignTokens.spacingLarge)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .background(DesignTokens.canvas)
        .navigationTitle("穿搭旅程")
        .onAppear {
            store.send(.appeared)
        }
    }

    private var heroSection: some View {
        VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
            Text("StyleCapture 穿搭旅程")
                .font(.largeTitle.weight(.bold))
                .foregroundStyle(DesignTokens.ink)
                .accessibilityIdentifier("journey.title")

            Text("为 3–7 天旅行生成每天可穿、可拍、可调整的造型计划。")
                .font(.headline)
                .foregroundStyle(DesignTokens.textMuted)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("journey.subtitle")
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("StyleCapture 穿搭旅程，为 3 到 7 天旅行生成每天可穿、可拍、可调整的造型计划。")
    }

    private var outcomeCard: some View {
        VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
            Text("3–7 天旅行结果")
                .font(.title3.weight(.semibold))
                .foregroundStyle(DesignTokens.primaryPressed)

            Text("按目的地、天气与日程，把上镜主搭、备用层次和鞋包配件整理成清晰行程。")
                .font(.body)
                .foregroundStyle(DesignTokens.textMuted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(DesignTokens.spacingLarge)
        .background(DesignTokens.canvasLight)
        .clipShape(RoundedRectangle(cornerRadius: DesignTokens.cornerRadius, style: .continuous))
        .shadow(color: DesignTokens.softShadow, radius: 18, x: 0, y: 10)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("journey.outcomeCard")
    }

    private var emptyStateCard: some View {
        VStack(alignment: .leading, spacing: DesignTokens.spacingSmall) {
            Text("还没有旅行方案")
                .font(.headline)
                .foregroundStyle(DesignTokens.ink)
                .accessibilityIdentifier("journey.emptyState")

            Text("先选择出发天数和场景，Journey 会把每日穿搭目标整理成可执行清单。")
                .font(.subheadline)
                .foregroundStyle(DesignTokens.textMuted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(DesignTokens.spacingMedium)
        .background(
            RoundedRectangle(cornerRadius: DesignTokens.cornerRadius, style: .continuous)
                .fill(DesignTokens.canvasLight.opacity(0.72))
                .overlay(
                    RoundedRectangle(cornerRadius: DesignTokens.cornerRadius, style: .continuous)
                        .stroke(DesignTokens.softShadow, lineWidth: 1)
                )
        )
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("journey.emptyStateCard")
    }

    private var primaryAction: some View {
        Button {
            store.send(.startLoading)
        } label: {
            HStack(spacing: DesignTokens.spacingSmall) {
                Text("开始规划 3–7 天旅程")
                    .font(.headline)
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, DesignTokens.spacingMedium)
            .padding(.horizontal, DesignTokens.spacingLarge)
            .foregroundStyle(.white)
            .background(DesignTokens.primary)
            .clipShape(RoundedRectangle(cornerRadius: DesignTokens.cornerRadius, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("journey.primaryAction")
        .accessibilityLabel("开始规划 3 到 7 天旅程")
        .accessibilityHint("创建旅行穿搭计划")
    }
}
