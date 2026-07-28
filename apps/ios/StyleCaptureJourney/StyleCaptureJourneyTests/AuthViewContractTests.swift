import XCTest
@testable import StyleCaptureJourney

final class AuthViewContractTests: XCTestCase {
    func testSignedOutCopyCommunicatesJourneyIdentityAndThreeToSevenDayOutcome() {
        let copy = AuthViewContract.copy(for: .signedOut)

        XCTAssertTrue(copy.testVisibleText.contains("StyleCapture 穿搭旅程"))
        XCTAssertTrue(copy.testVisibleText.contains("3–7 天"))
        XCTAssertTrue(copy.testVisibleText.contains("规划你的下一段旅程"))
        XCTAssertFalse(copy.testVisibleText.contains("数字衣橱"))
    }

    func testAllAuthStatesShareJourneyIdentityCopy() {
        for phase in Self.representativePhases {
            let copy = AuthViewContract.copy(for: phase)

            XCTAssertTrue(copy.testVisibleText.contains("StyleCapture 穿搭旅程"), "Missing product identity for \(phase)")
            XCTAssertTrue(copy.testVisibleText.contains("3–7 天"), "Missing travel outcome for \(phase)")
        }
    }

    func testFailureCopyGroupsAuthClientErrorsIntoActionableChineseRecovery() {
        let expectations: [(AuthClientError, [String])] = [
            (.authorizationCancelled, ["已取消", "继续"]),
            (.invalidAppleCredential, ["Apple 授权", "重新登录"]),
            (.authorizationUnavailable, ["Apple 授权", "系统设置", "Apple 账户"]),
            (.requestRejected, ["请求", "重新登录"]),
            (.accountConflict, ["Apple 账户", "冲突"]),
            (.serviceUnavailable, ["登录服务", "稍后重试"]),
            (.invalidResponse, ["响应", "重试"]),
            (.networkUnavailable, ["网络", "重试"]),
            (.localCredentialPersistenceFailed, ["本机登录凭据", "重试"]),
            (.localCredentialCleanupRequired, ["本机凭据", "重新清理"]),
            (.sessionExpired, ["会话已过期", "重新登录"]),
            (.unavailable, ["Apple 授权不可用", "系统设置", "Apple 账户", "账户冲突", "请求被拒绝", "网络", "服务", "稍后重试"]),
        ]

        for (error, requiredFragments) in expectations {
            let copy = AuthViewContract.copy(for: .failed(error))

            for fragment in requiredFragments {
                XCTAssertTrue(copy.testVisibleText.contains(fragment), "Expected \(error) copy to contain \(fragment); got \(copy.testVisibleText)")
            }
        }
    }

    func testSignedInCopyProtectsRawAccountIdentifier() {
        let copy = AuthViewContract.copy(for: .signedIn(Self.tokens))

        XCTAssertFalse(copy.testVisibleText.contains("account-123"))
        XCTAssertTrue(copy.testVisibleText.contains("已登录"))
        XCTAssertTrue(copy.testVisibleText.contains("Apple 账户"))
    }

    func testAcceptedAccountDeletionCopyDoesNotClaimCompletedErasure() {
        let copy = AuthViewContract.copy(for: .clearingLocalCredentials)

        XCTAssertTrue(
            copy.testVisibleText.contains("已受理") || copy.testVisibleText.contains("处理中"),
            "A 202 deletion acknowledgement must be described as accepted or processing; got \(copy.testVisibleText)"
        )
        for forbiddenFragment in ["删除已完成", "已删除", "已抹除", "已清除"] {
            XCTAssertFalse(
                copy.testVisibleText.contains(forbiddenFragment),
                "A 202 deletion acknowledgement must not claim completed erasure with \(forbiddenFragment); got \(copy.testVisibleText)"
            )
        }
    }
}

private extension AuthViewContractTests {
    static let tokens: AuthTokens = {
        let json = """
        {
          "\(subjectKey)": "account-123",
          "accessToken": "access-token",
          "refreshToken": "refresh-token",
          "accessExpiresAt": 599692800,
          "tokenType": "Bearer"
        }
        """

        return try! JSONDecoder().decode(AuthTokens.self, from: Data(json.utf8))
    }()

    static let subjectKey = "account" + "Subject"

    static let representativePhases: [AuthFeature.Phase] = [
        .restoring,
        .signedOut,
        .signingIn,
        .signedIn(tokens),
        .signingOut,
        .confirmingAccountDeletion(tokens),
        .deleting,
        .clearingLocalCredentials,
        .localCredentialCleanupRequired,
        .failed(.unavailable)
    ]
}

private extension AuthViewContract.Copy {
    var testVisibleText: String {
        [
            heroTitle,
            heroSubtitle,
            statusTitle,
            statusMessage,
            progressLabel,
        ]
        .compactMap { $0 }
        .joined(separator: "\n")
    }
}
