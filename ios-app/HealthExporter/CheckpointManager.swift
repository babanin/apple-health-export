import Foundation

class CheckpointManager: @unchecked Sendable {
    static let shared = CheckpointManager()
    private let defaults = UserDefaults.standard
    private let checkpointsKey = "health_export_checkpoints"

    private init() {}

    func getCheckpoint(for metricType: String) -> Int64? {
        let checkpoints = loadCheckpoints()
        return checkpoints[metricType]
    }

    func getAllCheckpoints() -> [String: Int64] {
        loadCheckpoints()
    }

    func updateCheckpoint(for metricType: String, timestampMs: Int64) {
        var checkpoints = loadCheckpoints()
        if let existing = checkpoints[metricType] {
            checkpoints[metricType] = max(existing, timestampMs)
        } else {
            checkpoints[metricType] = timestampMs
        }
        saveCheckpoints(checkpoints)
    }

    func updateCheckpoints(_ updates: [String: Int64]) {
        var checkpoints = loadCheckpoints()
        for (metricType, timestampMs) in updates {
            if let existing = checkpoints[metricType] {
                checkpoints[metricType] = max(existing, timestampMs)
            } else {
                checkpoints[metricType] = timestampMs
            }
        }
        saveCheckpoints(checkpoints)
    }

    func getStartTime(for metricType: String) -> Date {
        if let lastTs = getCheckpoint(for: metricType) {
            return Date(timeIntervalSince1970: Double(lastTs) / 1000.0 + 0.001)
        }
        return Date.distantPast
    }

    func clearAll() {
        defaults.removeObject(forKey: checkpointsKey)
    }

    private func loadCheckpoints() -> [String: Int64] {
        guard let data = defaults.data(forKey: checkpointsKey) else { return [:] }
        guard let dict = try? JSONDecoder().decode([String: Int64].self, from: data) else { return [:] }
        return dict
    }

    private func saveCheckpoints(_ checkpoints: [String: Int64]) {
        guard let data = try? JSONEncoder().encode(checkpoints) else { return }
        defaults.set(data, forKey: checkpointsKey)
    }
}