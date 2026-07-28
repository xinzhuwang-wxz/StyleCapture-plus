import SwiftUI
import UIKit
import XCTest
@testable import StyleCaptureJourney

@MainActor
final class DesignTokensTests: XCTestCase {
    func testJourneyLavenderPaletteResolvesToApprovedSRGBTokens() throws {
        try assertColor(DesignTokens.canvas, equals: "#F7F3FC", named: "canvas")
        try assertColor(DesignTokens.canvasLight, equals: "#FAF7FE", named: "canvasLight")
        try assertColor(DesignTokens.primary, equals: "#8B5CF6", named: "primary")
        try assertColor(DesignTokens.primaryFill, equals: "#A78BFA", named: "primaryFill")
        try assertColor(DesignTokens.primaryPressed, equals: "#7C3AED", named: "primaryPressed")
        try assertColor(DesignTokens.textMuted, equals: "#7C6AA8", named: "textMuted")
        try assertColor(DesignTokens.textDim, equals: "#A89CC9", named: "textDim")
        try assertColor(DesignTokens.softShadow, equals: "#ECE5F8", named: "softShadow")
    }

    func testFunctionalInactiveTextUsesMutedTokenNotDecorativeDimToken() throws {
        let muted = try ResolvedSRGBColor(DesignTokens.textMuted)
        let dim = try ResolvedSRGBColor(DesignTokens.textDim)

        XCTAssertNotEqual(muted, dim, "textMuted must remain distinct from textDim so inactive controls do not use decorative copy color.")
        XCTAssertLessThan(
            muted.relativeLuminance,
            dim.relativeLuminance,
            "textMuted should be the more legible inactive functional text color; textDim is only for redundant or decorative copy."
        )
    }

    private func assertColor(
        _ color: Color,
        equals expectedHex: String,
        named name: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws {
        let expected = try ResolvedSRGBColor(hex: expectedHex)
        let actual = try ResolvedSRGBColor(color)

        XCTAssertEqual(actual.red, expected.red, accuracy: 0.002, "\(name) red", file: file, line: line)
        XCTAssertEqual(actual.green, expected.green, accuracy: 0.002, "\(name) green", file: file, line: line)
        XCTAssertEqual(actual.blue, expected.blue, accuracy: 0.002, "\(name) blue", file: file, line: line)
        XCTAssertEqual(actual.alpha, 1.0, accuracy: 0.002, "\(name) alpha", file: file, line: line)
    }
}

private struct ResolvedSRGBColor: Equatable {
    let red: CGFloat
    let green: CGFloat
    let blue: CGFloat
    let alpha: CGFloat

    init(_ color: Color) throws {
        let uiColor = UIColor(color).resolvedColor(with: UITraitCollection(userInterfaceStyle: .light))
        var red: CGFloat = 0
        var green: CGFloat = 0
        var blue: CGFloat = 0
        var alpha: CGFloat = 0

        guard uiColor.getRed(&red, green: &green, blue: &blue, alpha: &alpha) else {
            throw XCTSkip("Unable to resolve SwiftUI color into sRGB components.")
        }

        self.red = red
        self.green = green
        self.blue = blue
        self.alpha = alpha
    }

    init(hex: String) throws {
        let trimmed = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard trimmed.count == 6, let value = Int(trimmed, radix: 16) else {
            XCTFail("Invalid color hex \(hex)")
            self.red = 0
            self.green = 0
            self.blue = 0
            self.alpha = 0
            return
        }

        self.red = CGFloat((value >> 16) & 0xFF) / 255.0
        self.green = CGFloat((value >> 8) & 0xFF) / 255.0
        self.blue = CGFloat(value & 0xFF) / 255.0
        self.alpha = 1.0
    }

    var relativeLuminance: CGFloat {
        0.2126 * red + 0.7152 * green + 0.0722 * blue
    }
}
