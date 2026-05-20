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

enum SyncProgressPhase: Equatable {
    case idle
    case connecting
    case fetching
    case exporting
    case completed
    case failed
}

struct SyncProgress: Equatable {
    let phase: SyncProgressPhase
    let startedAt: Date?
    let updatedAt: Date
    let metricsCompleted: Int
    let totalMetrics: Int
    let fetchedSamples: Int
    let exportedSamples: Int
    let totalSamples: Int?
    let message: String?

    static let idle = SyncProgress(
        phase: .idle,
        startedAt: nil,
        updatedAt: Date(),
        metricsCompleted: 0,
        totalMetrics: 0,
        fetchedSamples: 0,
        exportedSamples: 0,
        totalSamples: nil,
        message: nil
    )

    var remainingSamples: Int? {
        guard let totalSamples else { return nil }
        return max(totalSamples - exportedSamples, 0)
    }

    var progressFraction: Double? {
        switch phase {
        case .fetching:
            guard totalMetrics > 0 else { return nil }
            return min(Double(metricsCompleted) / Double(totalMetrics), 1)
        case .exporting:
            guard let totalSamples, totalSamples > 0 else { return nil }
            return min(Double(exportedSamples) / Double(totalSamples), 1)
        case .completed:
            return 1
        case .idle, .connecting, .failed:
            return nil
        }
    }

    var estimatedTimeRemaining: TimeInterval? {
        guard phase == .exporting,
              let totalSamples,
              let startedAt,
              exportedSamples > 0,
              totalSamples > exportedSamples else {
            return nil
        }

        let elapsed = updatedAt.timeIntervalSince(startedAt)
        guard elapsed > 0 else { return nil }

        let samplesPerSecond = Double(exportedSamples) / elapsed
        guard samplesPerSecond > 0 else { return nil }

        return Double(totalSamples - exportedSamples) / samplesPerSecond
    }
}

struct HealthKitFetchProgress {
    let completedMetrics: Int
    let totalMetrics: Int
    let fetchedSamples: Int
    let currentMetricName: String?
}
