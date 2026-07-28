import ComposableArchitecture
import SwiftUI
import XCTest
@testable import StyleCaptureJourney

@MainActor
final class JourneyVisualContractTests: XCTestCase {
    func testEmptyJourneyShellExposesChineseTravelOutcomeAndNativeActions() {
        let store = Store(initialState: JourneyFeature.State()) {
            JourneyFeature()
        }
        let snapshot = SwiftUIViewContractSnapshot(JourneyView(store: store).body)

        XCTAssertTrue(
            snapshot.containsText(matching: #"StyleCapture.*[\u{4E00}-\u{9FFF}]"#),
            "The empty Journey shell should expose a Chinese StyleCapture product identity, not the old English placeholder."
        )
        XCTAssertTrue(
            snapshot.containsText(matching: #"3\s*[–-]\s*7\s*天"#),
            "The empty Journey shell should promise the approved 3-7 day travel styling outcome."
        )
        XCTAssertGreaterThanOrEqual(
            snapshot.typeNameCount(containing: "Button"),
            1,
            "The refreshed shell should provide at least one native SwiftUI action instead of a static placeholder."
        )
        XCTAssertTrue(
            snapshot.containsText(matching: #"(开始|规划|生成|创建)"#),
            "The native action copy should invite the user to start planning a Journey."
        )
    }

    func testEmptyJourneyShellDoesNotExposeFeedWardrobeOrSixTabNavigation() {
        let store = Store(initialState: JourneyFeature.State()) {
            JourneyFeature()
        }
        let snapshot = SwiftUIViewContractSnapshot(JourneyView(store: store).body)
        let forbiddenLabels = [
            "Feed",
            "For You",
            "数字衣橱",
            "Digital wardrobe",
            "Wardrobe",
            "Closet",
            "Tab 1",
            "Tab 2",
            "Tab 3",
            "Tab 4",
            "Tab 5",
            "Tab 6"
        ]

        for label in forbiddenLabels {
            XCTAssertFalse(
                snapshot.visibleText.contains(label),
                "Journey's visible empty shell must not expose Feed, digital wardrobe, or six-tab H5 navigation copy."
            )
        }
    }
}

private struct SwiftUIViewContractSnapshot {
    let visibleText: String
    private let typeNames: [String]

    init(_ view: some View) {
        var strings: [String] = []
        var types: [String] = []
        Self.walk(view, depth: 0, strings: &strings, types: &types)
        self.visibleText = strings.joined(separator: "\n")
        self.typeNames = types
    }

    func containsText(matching pattern: String) -> Bool {
        visibleText.range(of: pattern, options: .regularExpression) != nil
    }

    func typeNameCount(containing needle: String) -> Int {
        typeNames.filter { $0.contains(needle) }.count
    }

    private static func walk(_ value: Any, depth: Int, strings: inout [String], types: inout [String]) {
        guard depth < 48 else { return }

        let mirror = Mirror(reflecting: value)
        types.append(String(describing: mirror.subjectType))

        if let string = value as? String, !string.isEmpty {
            strings.append(string)
        }

        for child in mirror.children {
            walk(child.value, depth: depth + 1, strings: &strings, types: &types)
        }
    }
}
