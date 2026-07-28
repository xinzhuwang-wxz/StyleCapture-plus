import Foundation

struct NavigationSnapshot: Codable, Equatable, Sendable {
    var selectedTab: String
    var journeyID: String?

    init(selectedTab: String = "journey", journeyID: String? = nil) {
        self.selectedTab = selectedTab
        self.journeyID = journeyID
    }
}
