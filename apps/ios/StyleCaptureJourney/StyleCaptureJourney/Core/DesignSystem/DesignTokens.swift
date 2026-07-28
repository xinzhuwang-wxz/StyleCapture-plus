import SwiftUI

public enum DesignTokens {
    public static let spacingSmall: CGFloat = 8
    public static let spacingMedium: CGFloat = 16
    public static let spacingLarge: CGFloat = 24
    public static let spacingXLarge: CGFloat = 32
    public static let cornerRadius: CGFloat = 8

    public static let canvas = sRGB(red: 0xF7, green: 0xF3, blue: 0xFC)
    public static let canvasLight = sRGB(red: 0xFA, green: 0xF7, blue: 0xFE)
    public static let primary = sRGB(red: 0x8B, green: 0x5C, blue: 0xF6)
    public static let primaryFill = sRGB(red: 0xA7, green: 0x8B, blue: 0xFA)
    public static let primaryPressed = sRGB(red: 0x7C, green: 0x3A, blue: 0xED)
    public static let textMuted = sRGB(red: 0x7C, green: 0x6A, blue: 0xA8)
    public static let textDim = sRGB(red: 0xA8, green: 0x9C, blue: 0xC9)
    public static let softShadow = sRGB(red: 0xEC, green: 0xE5, blue: 0xF8)

    public static let accent = primary
    public static let ink = sRGB(red: 0x21, green: 0x18, blue: 0x36)

    private static func sRGB(red: Int, green: Int, blue: Int) -> Color {
        Color(
            .sRGB,
            red: Double(red) / 255.0,
            green: Double(green) / 255.0,
            blue: Double(blue) / 255.0,
            opacity: 1.0
        )
    }
}
