import Foundation
import StyleCaptureAPI

enum ProductAuthAPI {
    static func appleAuthBody(
        from request: AppleSignInRequest
    ) -> Components.Schemas.AppleAuthBody {
        .init(
            authorizationCode: request.authorizationCode,
            deviceName: request.deviceName,
            identityToken: request.identityToken,
            nonce: request.nonce
        )
    }

    static func authTokens(
        from response: Components.Schemas.AuthTokenResponse
    ) -> AuthTokens {
        AuthTokens(
            accountSubject: response.accountSubject,
            accessToken: response.accessToken,
            refreshToken: response.refreshToken,
            accessExpiresAt: response.accessExpiresAt,
            tokenType: response.tokenType
        )
    }
}
