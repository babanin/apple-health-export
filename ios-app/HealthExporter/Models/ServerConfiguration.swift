import Foundation

struct ServerConfiguration: Equatable, Sendable {
    let host: String
    let port: Int

    var displayAddress: String {
        "\(host):\(port)"
    }
}
