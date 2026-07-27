import ComposableArchitecture
import Foundation
import Photos

public struct PhotosClient: Sendable {
    public var authorizationStatus: @Sendable () async -> PHAuthorizationStatus

    public init(authorizationStatus: @escaping @Sendable () async -> PHAuthorizationStatus) {
        self.authorizationStatus = authorizationStatus
    }
}

extension PhotosClient: DependencyKey {
    public static let liveValue = PhotosClient(authorizationStatus: {
        PHPhotoLibrary.authorizationStatus(for: .readWrite)
    })
    public static let testValue = PhotosClient(authorizationStatus: { .notDetermined })
}

public extension DependencyValues {
    var photosClient: PhotosClient {
        get { self[PhotosClient.self] }
        set { self[PhotosClient.self] = newValue }
    }
}
