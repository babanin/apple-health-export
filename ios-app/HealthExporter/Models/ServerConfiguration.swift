import Foundation

struct ServerConfiguration: Equatable {
    let host: String
    let port: Int

    var displayAddress: String {
        "\(host):\(port)"
    }
}
