import ComposableArchitecture
import Foundation
import Nuke

public struct ImagePipelineClient: Sendable {
    public var data: @Sendable (URL) async throws -> Data

    public init(data: @escaping @Sendable (URL) async throws -> Data) {
        self.data = data
    }
}

extension ImagePipelineClient: DependencyKey {
    public static let liveValue = ImagePipelineClient(data: { url in
        let request = ImageRequest(url: url)
        let response = try await ImagePipeline.shared.data(for: request)
        return response.0
    })

    public static let testValue = ImagePipelineClient(data: { _ in Data() })
}

public extension DependencyValues {
    var imagePipelineClient: ImagePipelineClient {
        get { self[ImagePipelineClient.self] }
        set { self[ImagePipelineClient.self] = newValue }
    }
}
