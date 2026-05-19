import Foundation

enum SyncTrigger: String {
    case manual = "Manual"
    case automatic = "Automatic"
    case background = "Background"
}

enum PingState: Equatable {
    case idle
    case pinging
    case success(version: String)
    case unreachable
    case failed(message: String)

    var isPinging: Bool {
        if case .pinging = self {
            return true
        }
        return false
    }

    var label: String {
        switch self {
        case .idle:
            return "Tap to ping"
        case .pinging:
            return "Pinging..."
        case .success(let version):
            return "OK (v\(version))"
        case .unreachable:
            return "Unreachable"
        case .failed:
            return "Failed"
        }
    }
}

struct UserFacingError: Identifiable, Equatable {
    let id = UUID()
    let message: String
}

struct SyncResult {
    let succeeded: Bool
    let exportedCount: Int
    let message: String?
    let noSamples: Bool

    static func success(exportedCount: Int, noSamples: Bool = false, message: String? = nil) -> SyncResult {
        SyncResult(
            succeeded: true,
            exportedCount: exportedCount,
            message: message,
            noSamples: noSamples
        )
    }

    static func failure(_ message: String) -> SyncResult {
        SyncResult(
            succeeded: false,
            exportedCount: 0,
            message: message,
            noSamples: false
        )
    }
}

enum PingResult {
    case success(version: String)
    case unreachable
    case failed(message: String)
}
