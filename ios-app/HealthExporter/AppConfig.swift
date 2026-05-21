import Foundation

class AppConfig: ObservableObject {
    nonisolated(unsafe) static let shared = AppConfig()

    static let batchSizeRange = 100...20_000
    static let parallelBatchRange = 1...8

    @Published var grpcHost: String {
        didSet { UserDefaults.standard.set(grpcHost, forKey: "health_export_grpc_host") }
    }
    @Published var grpcPort: Int {
        didSet {
            let clamped = max(1, min(grpcPort, 65_535))
            if grpcPort != clamped {
                grpcPort = clamped
                return
            }
            UserDefaults.standard.set(grpcPort, forKey: "health_export_grpc_port")
        }
    }
    @Published var syncBatchSize: Int {
        didSet {
            let clamped = Self.clamp(syncBatchSize, to: Self.batchSizeRange)
            if syncBatchSize != clamped {
                syncBatchSize = clamped
                return
            }
            UserDefaults.standard.set(syncBatchSize, forKey: "health_export_sync_batch_size")
        }
    }
    @Published var parallelBatchCount: Int {
        didSet {
            let clamped = Self.clamp(parallelBatchCount, to: Self.parallelBatchRange)
            if parallelBatchCount != clamped {
                parallelBatchCount = clamped
                return
            }
            UserDefaults.standard.set(parallelBatchCount, forKey: "health_export_parallel_batch_count")
        }
    }

    private init() {
        let defaults = UserDefaults.standard
        self.grpcHost = defaults.string(forKey: "health_export_grpc_host")
            ?? (Bundle.main.object(forInfoDictionaryKey: "HEALTH_EXPORT_GRPC_HOST") as? String ?? "192.168.1.100")
        self.grpcPort = defaults.object(forKey: "health_export_grpc_port") as? Int
            ?? (Bundle.main.object(forInfoDictionaryKey: "HEALTH_EXPORT_GRPC_PORT") as? Int ?? 50051)
        self.syncBatchSize = Self.clamp(
            defaults.object(forKey: "health_export_sync_batch_size") as? Int ?? 5_000,
            to: Self.batchSizeRange
        )
        self.parallelBatchCount = Self.clamp(
            defaults.object(forKey: "health_export_parallel_batch_count") as? Int ?? 3,
            to: Self.parallelBatchRange
        )
    }

    private static func clamp(_ value: Int, to range: ClosedRange<Int>) -> Int {
        max(range.lowerBound, min(value, range.upperBound))
    }
}
