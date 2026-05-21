import Foundation
import UIKit

@available(iOS 18.0, *)
@MainActor
final class SyncService {
    typealias ClientFactory = (ServerConfiguration) -> HealthExportClient

    private let appConfig: AppConfig
    private let logger: AppLogger
    private let clientFactory: ClientFactory
    private let healthKitManagerFactory: () -> HealthKitManager
    private let demoDataManager: DemoDataManager
    private var isRunning = false

    init(
        appConfig: AppConfig = .shared,
        logger: AppLogger = .shared,
        clientFactory: @escaping ClientFactory = {
            HealthExportClient(serverAddress: $0.host, serverPort: $0.port)
        },
        healthKitManagerFactory: @escaping () -> HealthKitManager = { HealthKitManager() },
        demoDataManager: DemoDataManager = .shared
    ) {
        self.appConfig = appConfig
        self.logger = logger
        self.clientFactory = clientFactory
        self.healthKitManagerFactory = healthKitManagerFactory
        self.demoDataManager = demoDataManager
    }

    var running: Bool {
        isRunning
    }

    func performSync(
        trigger: SyncTrigger,
        useDemoData: Bool,
        progress: @escaping @MainActor (SyncProgress) -> Void = { _ in }
    ) async -> SyncResult {
        guard !isRunning else {
            logger.info("\(trigger.rawValue) sync skipped; another sync is already running")
            return .success(exportedCount: 0, message: "Sync already running")
        }

        isRunning = true
        defer { isRunning = false }

        let syncStartedAt = Date()
        let configuration = currentConfiguration()
        logger.info("Starting \(trigger.rawValue.lowercased()) sync using \(configuration.displayAddress)...")
        progress(SyncProgress(
            phase: .connecting,
            startedAt: syncStartedAt,
            updatedAt: Date(),
            metricsCompleted: 0,
            totalMetrics: 0,
            fetchedSamples: 0,
            exportedSamples: 0,
            totalSamples: nil,
            message: "Connecting to \(configuration.displayAddress)"
        ))

        let client = clientFactory(configuration)
        guard await client.checkConnection() else {
            logger.error("TCP connection refused")
            progress(SyncProgress(
                phase: .failed,
                startedAt: syncStartedAt,
                updatedAt: Date(),
                metricsCompleted: 0,
                totalMetrics: 0,
                fetchedSamples: 0,
                exportedSamples: 0,
                totalSamples: nil,
                message: "Server unreachable at \(configuration.displayAddress)"
            ))
            return .failure("Server unreachable at \(configuration.displayAddress)")
        }
        logger.info("TCP connection OK")

        do {
            try client.connect()
            logger.info("Connected to \(configuration.displayAddress)")
        } catch {
            logger.error("Connection failed: \(error.localizedDescription)")
            progress(SyncProgress(
                phase: .failed,
                startedAt: syncStartedAt,
                updatedAt: Date(),
                metricsCompleted: 0,
                totalMetrics: 0,
                fetchedSamples: 0,
                exportedSamples: 0,
                totalSamples: nil,
                message: "Connection failed: \(error.localizedDescription)"
            ))
            return .failure("Connection failed: \(error.localizedDescription)")
        }

        defer {
            client.disconnect()
            logger.info("Disconnected from server")
        }

        let deviceId = deviceIdentifier()
        do {
            logger.info("Pinging gateway...")
            let (ok, version) = try await client.ping(deviceId: deviceId)
            guard ok else {
                logger.error("Gateway ping failed")
                progress(SyncProgress(
                    phase: .failed,
                    startedAt: syncStartedAt,
                    updatedAt: Date(),
                    metricsCompleted: 0,
                    totalMetrics: 0,
                    fetchedSamples: 0,
                    exportedSamples: 0,
                    totalSamples: nil,
                    message: "Gateway returned unhealthy"
                ))
                return .failure("Gateway returned unhealthy")
            }
            logger.info("Gateway responded (version: \(version))")
        } catch {
            let message = gatewayErrorMessage(for: error)
            logger.error(message)
            progress(SyncProgress(
                phase: .failed,
                startedAt: syncStartedAt,
                updatedAt: Date(),
                metricsCompleted: 0,
                totalMetrics: 0,
                fetchedSamples: 0,
                exportedSamples: 0,
                totalSamples: nil,
                message: message
            ))
            return .failure(message)
        }

        do {
            logger.info("Device ID: \(deviceId)")

            if useDemoData {
                logger.info("Using demo data")
                let samples = demoDataManager.generateDemoSamples()
                progress(SyncProgress(
                    phase: .fetching,
                    startedAt: syncStartedAt,
                    updatedAt: Date(),
                    metricsCompleted: 1,
                    totalMetrics: 1,
                    fetchedSamples: samples.count,
                    exportedSamples: 0,
                    totalSamples: nil,
                    message: "Generated demo samples"
                ))
                let summary = try await exportBufferedSamples(
                    samples,
                    client: client,
                    deviceId: deviceId,
                    syncStartedAt: syncStartedAt,
                    totalMetrics: 1,
                    metricsCompleted: 1,
                    progress: progress
                )
                if summary.exportedCount == 0 {
                    return noSamplesResult(syncStartedAt: syncStartedAt, totalMetrics: 1, progress: progress)
                }
                return completedResult(summary, trigger: trigger, syncStartedAt: syncStartedAt, progress: progress)
            }

            logger.info("Streaming HealthKit data...")
            progress(SyncProgress(
                phase: .fetching,
                startedAt: syncStartedAt,
                updatedAt: Date(),
                metricsCompleted: 0,
                totalMetrics: HKMetricMapping.all.count + 1,
                fetchedSamples: 0,
                exportedSamples: 0,
                totalSamples: nil,
                message: "Streaming HealthKit data"
            ))
            let summary = try await exportHealthKitSamplesStreaming(
                client: client,
                deviceId: deviceId,
                syncStartedAt: syncStartedAt,
                progress: progress
            )
            if summary.exportedCount == 0 {
                return noSamplesResult(syncStartedAt: syncStartedAt, totalMetrics: HKMetricMapping.all.count + 1, progress: progress)
            }
            return completedResult(summary, trigger: trigger, syncStartedAt: syncStartedAt, progress: progress)
        } catch {
            logger.error("Sync failed: \(error.localizedDescription)")
            progress(SyncProgress(
                phase: .failed,
                startedAt: syncStartedAt,
                updatedAt: Date(),
                metricsCompleted: 0,
                totalMetrics: 0,
                fetchedSamples: 0,
                exportedSamples: 0,
                totalSamples: nil,
                message: error.localizedDescription
            ))
            return .failure(error.localizedDescription)
        }
    }

    func pingGateway() async -> PingResult {
        let configuration = currentConfiguration()
        logger.info("Pinging gateway at \(configuration.displayAddress)...")

        let client = clientFactory(configuration)
        guard await client.checkConnection() else {
            logger.error("TCP connection refused")
            return .unreachable
        }

        do {
            try client.connect()
            defer {
                client.disconnect()
                logger.info("Disconnected from server")
            }

            let (ok, version) = try await client.ping(deviceId: deviceIdentifier())
            guard ok else {
                logger.error("Gateway returned unhealthy")
                return .failed(message: "Gateway returned unhealthy")
            }

            logger.info("Gateway ping successful (version: \(version))")
            return .success(version: version)
        } catch {
            let message = gatewayErrorMessage(for: error)
            logger.error(message)
            return .failed(message: message)
        }
    }

    private func exportBufferedSamples(
        _ samples: [HealthMetricSample],
        client: HealthExportClient,
        deviceId: String,
        syncStartedAt: Date,
        totalMetrics: Int,
        metricsCompleted: Int,
        progress: @escaping @MainActor (SyncProgress) -> Void
    ) async throws -> SyncExportSummary {
        let fetchElapsed = Date().timeIntervalSince(syncStartedAt)
        logger.info("Fetched \(samples.count) samples in \(durationText(fetchElapsed))")

        guard !samples.isEmpty else {
            return SyncExportSummary(
                fetchedCount: 0,
                exportedCount: 0,
                totalSamples: 0,
                totalMetrics: totalMetrics,
                metricsCompleted: metricsCompleted,
                exportStartedAt: Date(),
                bloodPressureDiagnostics: .fromSamples([])
            )
        }

        let batchSize = appConfig.syncBatchSize
        let totalBatches = Int(ceil(Double(samples.count) / Double(batchSize)))
        var batches: [SyncBatch] = []
        batches.reserveCapacity(totalBatches)
        for start in stride(from: 0, to: samples.count, by: batchSize) {
            let end = min(start + batchSize, samples.count)
            batches.append(SyncBatch(
                number: batches.count + 1,
                total: totalBatches,
                samples: Array(samples[start..<end])
            ))
        }

        let exportStartedAt = Date()
        var exportedCount = 0
        let checkpointSnapshot = CheckpointManager.shared.getAllCheckpoints()
        let isHistoricalExport = checkpointSnapshot.isEmpty

        logger.info("Exporting \(samples.count) samples as \(totalBatches) batches; batch_size=\(batchSize), parallelism=\(appConfig.parallelBatchCount)")
        progress(SyncProgress(
            phase: .exporting,
            startedAt: exportStartedAt,
            updatedAt: Date(),
            metricsCompleted: metricsCompleted,
            totalMetrics: totalMetrics,
            fetchedSamples: samples.count,
            exportedSamples: 0,
            totalSamples: samples.count,
            message: "Exporting samples"
        ))

        if isHistoricalExport, let resetBatch = batches.first {
            let result = try await sendAndRecordBatch(
                resetBatch,
                client: client,
                deviceId: deviceId,
                checkpoint: checkpointSnapshot,
                isHistoricalExport: true,
                exportedCount: &exportedCount
            )
            progress(SyncProgress(
                phase: .exporting,
                startedAt: exportStartedAt,
                updatedAt: Date(),
                metricsCompleted: metricsCompleted,
                totalMetrics: totalMetrics,
                fetchedSamples: samples.count,
                exportedSamples: exportedCount,
                totalSamples: samples.count,
                message: "Exported batch \(result.displayName)"
            ))
            batches.removeFirst()
        }

        try await withThrowingTaskGroup(of: SyncBatchResult.self) { group in
            var nextBatchIndex = 0

            func scheduleNextBatch() {
                guard nextBatchIndex < batches.count else { return }
                let batch = batches[nextBatchIndex]
                nextBatchIndex += 1
                logger.info("Sending batch \(batch.displayName): \(batch.samples.count) samples")
                group.addTask {
                    try await sendSyncBatch(
                        batch,
                        client: client,
                        deviceId: deviceId,
                        checkpoint: checkpointSnapshot,
                        isHistoricalExport: false
                    )
                }
            }

            for _ in 0..<min(appConfig.parallelBatchCount, batches.count) {
                scheduleNextBatch()
            }

            while let result = try await group.next() {
                recordBatchResult(result, exportedCount: &exportedCount)
                progress(SyncProgress(
                    phase: .exporting,
                    startedAt: exportStartedAt,
                    updatedAt: Date(),
                    metricsCompleted: metricsCompleted,
                    totalMetrics: totalMetrics,
                    fetchedSamples: samples.count,
                    exportedSamples: exportedCount,
                    totalSamples: samples.count,
                    message: "Exported batch \(result.displayName)"
                ))
                scheduleNextBatch()
            }
        }

        return SyncExportSummary(
            fetchedCount: samples.count,
            exportedCount: exportedCount,
            totalSamples: samples.count,
            totalMetrics: totalMetrics,
            metricsCompleted: metricsCompleted,
            exportStartedAt: exportStartedAt,
            bloodPressureDiagnostics: .fromSamples(samples)
        )
    }

    private func exportHealthKitSamplesStreaming(
        client: HealthExportClient,
        deviceId: String,
        syncStartedAt: Date,
        progress: @escaping @MainActor (SyncProgress) -> Void
    ) async throws -> SyncExportSummary {
        let healthKitManager = healthKitManagerFactory()
        let checkpointSnapshot = CheckpointManager.shared.getAllCheckpoints()
        let isHistoricalExport = checkpointSnapshot.isEmpty
        let batchSize = appConfig.syncBatchSize
        let totalMetrics = HKMetricMapping.all.count + 1
        let exportStartedAt = Date()

        var fetchedCount = 0
        var exportedCount = 0
        var metricsCompleted = 0
        var batchNumber = 0
        var resetSent = false
        var batchBuffer: [HealthMetricSample] = []
        var bloodPressureDiagnostics = BloodPressureSyncDiagnostics()
        batchBuffer.reserveCapacity(batchSize)

        logger.info("Streaming export started; batch_size=\(batchSize)")

        func flushBatch(_ samples: [HealthMetricSample], message: String? = nil) async throws {
            guard !samples.isEmpty else { return }
            batchNumber += 1
            let batch = SyncBatch(number: batchNumber, total: nil, samples: samples)
            let historicalReset = isHistoricalExport && !resetSent
            if historicalReset {
                resetSent = true
            }

            let result = try await sendAndRecordBatch(
                batch,
                client: client,
                deviceId: deviceId,
                checkpoint: checkpointSnapshot,
                isHistoricalExport: historicalReset,
                exportedCount: &exportedCount
            )
            progress(SyncProgress(
                phase: .exporting,
                startedAt: exportStartedAt,
                updatedAt: Date(),
                metricsCompleted: metricsCompleted,
                totalMetrics: totalMetrics,
                fetchedSamples: fetchedCount,
                exportedSamples: exportedCount,
                totalSamples: nil,
                message: message ?? "Exported batch \(result.displayName)"
            ))
        }

        func appendSamples(_ samples: [HealthMetricSample]) async throws {
            var offset = samples.startIndex
            while offset < samples.endIndex {
                let capacity = batchSize - batchBuffer.count
                let end = min(offset + capacity, samples.endIndex)
                batchBuffer.append(contentsOf: samples[offset..<end])
                offset = end

                if batchBuffer.count == batchSize {
                    let batchSamples = batchBuffer
                    batchBuffer.removeAll(keepingCapacity: true)
                    try await flushBatch(batchSamples)
                }
            }
        }

        for (index, mapping) in HKMetricMapping.all.enumerated() {
            let startDate = CheckpointManager.shared.getStartTime(for: mapping.metricName)
            logger.info("[\(index + 1)/\(totalMetrics)] Fetching \(mapping.metricName)...")
            progress(SyncProgress(
                phase: .fetching,
                startedAt: syncStartedAt,
                updatedAt: Date(),
                metricsCompleted: metricsCompleted,
                totalMetrics: totalMetrics,
                fetchedSamples: fetchedCount,
                exportedSamples: exportedCount,
                totalSamples: nil,
                message: "Fetching \(mapping.metricName)"
            ))

            do {
                let samples = try await healthKitManager.fetchSamples(for: mapping, from: startDate)
                bloodPressureDiagnostics.recordFetch(metricName: mapping.metricName, sampleCount: samples.count)
                fetchedCount += samples.count
                metricsCompleted = index + 1
                let remaining = totalMetrics - metricsCompleted
                logger.info("[\(metricsCompleted)/\(totalMetrics)] \(mapping.metricName): +\(samples.count) samples (streamed total: \(fetchedCount), \(remaining) metrics left)")
                try await appendSamples(samples)
                progress(SyncProgress(
                    phase: .exporting,
                    startedAt: exportStartedAt,
                    updatedAt: Date(),
                    metricsCompleted: metricsCompleted,
                    totalMetrics: totalMetrics,
                    fetchedSamples: fetchedCount,
                    exportedSamples: exportedCount,
                    totalSamples: nil,
                    message: "Streamed \(mapping.metricName)"
                ))
            } catch {
                metricsCompleted = index + 1
                bloodPressureDiagnostics.recordFailure(metricName: mapping.metricName, error: error)
                logger.error("Failed to fetch \(mapping.metricName): \(error.localizedDescription)")
            }
        }

        let workoutStartDate = CheckpointManager.shared.getStartTime(for: "apple_health_workout_duration_seconds")
        let workoutRouteStartDate = CheckpointManager.shared.getStartTime(for: "apple_health_workout_route_latitude_degrees")
        logger.info("Fetching workouts...")
        do {
            let workoutSamples = try await healthKitManager.fetchWorkoutSamples(from: workoutStartDate, routeStartDate: workoutRouteStartDate)
            fetchedCount += workoutSamples.count
            logger.info("Workouts: +\(workoutSamples.count) samples (streamed total: \(fetchedCount))")
            try await appendSamples(workoutSamples)
        } catch {
            logger.error("Failed to fetch workouts: \(error.localizedDescription)")
        }
        metricsCompleted = totalMetrics

        if !batchBuffer.isEmpty {
            let batchSamples = batchBuffer
            batchBuffer.removeAll(keepingCapacity: true)
            try await flushBatch(batchSamples)
        }

        let fetchElapsed = Date().timeIntervalSince(syncStartedAt)
        logger.info("Streaming export finished; fetched=\(fetchedCount), exported=\(exportedCount), elapsed=\(durationText(fetchElapsed))")
        return SyncExportSummary(
            fetchedCount: fetchedCount,
            exportedCount: exportedCount,
            totalSamples: nil,
            totalMetrics: totalMetrics,
            metricsCompleted: metricsCompleted,
            exportStartedAt: exportStartedAt,
            bloodPressureDiagnostics: bloodPressureDiagnostics
        )
    }

    private func sendAndRecordBatch(
        _ batch: SyncBatch,
        client: HealthExportClient,
        deviceId: String,
        checkpoint: [String: Int64],
        isHistoricalExport: Bool,
        exportedCount: inout Int
    ) async throws -> SyncBatchResult {
        logger.info("Sending batch \(batch.displayName): \(batch.samples.count) samples")
        let result = try await sendSyncBatch(
            batch,
            client: client,
            deviceId: deviceId,
            checkpoint: checkpoint,
            isHistoricalExport: isHistoricalExport
        )
        recordBatchResult(result, exportedCount: &exportedCount)
        return result
    }

    private func recordBatchResult(_ result: SyncBatchResult, exportedCount: inout Int) {
        CheckpointManager.shared.updateCheckpoints(result.updatedCheckpoints)
        exportedCount += result.sampleCount
        logger.info("Batch \(result.displayName) acknowledged in \(durationText(result.elapsed)); exported=\(exportedCount)")
    }

    private func noSamplesResult(
        syncStartedAt: Date,
        totalMetrics: Int,
        progress: @escaping @MainActor (SyncProgress) -> Void
    ) -> SyncResult {
        logger.warning("No samples to sync")
        progress(SyncProgress(
            phase: .completed,
            startedAt: syncStartedAt,
            updatedAt: Date(),
            metricsCompleted: totalMetrics,
            totalMetrics: totalMetrics,
            fetchedSamples: 0,
            exportedSamples: 0,
            totalSamples: 0,
            message: "No samples to sync"
        ))
        return .success(exportedCount: 0, noSamples: true, message: "No samples to sync")
    }

    private func completedResult(
        _ summary: SyncExportSummary,
        trigger: SyncTrigger,
        syncStartedAt: Date,
        progress: @escaping @MainActor (SyncProgress) -> Void
    ) -> SyncResult {
        let exportElapsed = Date().timeIntervalSince(summary.exportStartedAt)
        let totalElapsed = Date().timeIntervalSince(syncStartedAt)
        logger.info("\(trigger.rawValue) sync complete - \(summary.exportedCount) samples exported in \(durationText(exportElapsed)) (total \(durationText(totalElapsed)))")
        summary.bloodPressureDiagnostics.logSummary(logger: logger)
        progress(SyncProgress(
            phase: .completed,
            startedAt: syncStartedAt,
            updatedAt: Date(),
            metricsCompleted: summary.metricsCompleted,
            totalMetrics: summary.totalMetrics,
            fetchedSamples: summary.fetchedCount,
            exportedSamples: summary.exportedCount,
            totalSamples: summary.totalSamples ?? summary.exportedCount,
            message: "\(summary.exportedCount) samples exported"
        ))
        return .success(exportedCount: summary.exportedCount)
    }

    private func durationText(_ interval: TimeInterval) -> String {
        let milliseconds = interval * 1000
        if milliseconds < 1_000 {
            return "\(Int(milliseconds.rounded())) ms"
        }
        return String(format: "%.2f s", interval)
    }

    private func currentConfiguration() -> ServerConfiguration {
        ServerConfiguration(host: appConfig.grpcHost, port: appConfig.grpcPort)
    }

    private func deviceIdentifier() -> String {
        let device = UIDevice.current
        return "\(device.name)-\(device.systemName)-\(device.model)"
    }

    private func gatewayErrorMessage(for error: Error) -> String {
        if case HealthExportClientError.timeout = error {
            return "Gateway timed out (30s)"
        }
        if case HealthExportClientError.notConnected = error {
            return "Client not connected"
        }
        return "Gateway unreachable: \(error.localizedDescription)"
    }
}

enum SyncServiceError: LocalizedError {
    case batchFailed(String)

    var errorDescription: String? {
        switch self {
        case .batchFailed(let message):
            return message
        }
    }
}

private struct SyncBatch: Sendable {
    let number: Int
    let total: Int?
    let samples: [HealthMetricSample]

    var sampleCount: Int {
        samples.count
    }

    var displayName: String {
        if let total {
            return "\(number)/\(total)"
        }
        return "\(number)"
    }
}

private struct SyncBatchResult: Sendable {
    let number: Int
    let total: Int?
    let sampleCount: Int
    let elapsed: TimeInterval
    let updatedCheckpoints: [String: Int64]

    var displayName: String {
        if let total {
            return "\(number)/\(total)"
        }
        return "\(number)"
    }
}

private struct SyncExportSummary: Sendable {
    let fetchedCount: Int
    let exportedCount: Int
    let totalSamples: Int?
    let totalMetrics: Int
    let metricsCompleted: Int
    let exportStartedAt: Date
    let bloodPressureDiagnostics: BloodPressureSyncDiagnostics
}

private struct BloodPressureSyncDiagnostics: Sendable {
    private static let systolicMetric = "apple_health_blood_pressure_systolic_mmhg"
    private static let diastolicMetric = "apple_health_blood_pressure_diastolic_mmhg"

    private var systolicFetched = 0
    private var diastolicFetched = 0
    private var systolicError: String?
    private var diastolicError: String?

    static func fromSamples(_ samples: [HealthMetricSample]) -> BloodPressureSyncDiagnostics {
        var diagnostics = BloodPressureSyncDiagnostics()
        diagnostics.systolicFetched = samples.filter { $0.metricName == systolicMetric }.count
        diagnostics.diastolicFetched = samples.filter { $0.metricName == diastolicMetric }.count
        return diagnostics
    }

    mutating func recordFetch(metricName: String, sampleCount: Int) {
        switch metricName {
        case Self.systolicMetric:
            systolicFetched = sampleCount
            systolicError = nil
        case Self.diastolicMetric:
            diastolicFetched = sampleCount
            diastolicError = nil
        default:
            break
        }
    }

    mutating func recordFailure(metricName: String, error: Error) {
        switch metricName {
        case Self.systolicMetric:
            systolicError = error.localizedDescription
        case Self.diastolicMetric:
            diastolicError = error.localizedDescription
        default:
            break
        }
    }

    @MainActor
    func logSummary(logger: AppLogger) {
        let failureText = [
            systolicError.map { "systolic_error=\($0)" },
            diastolicError.map { "diastolic_error=\($0)" }
        ]
        .compactMap { $0 }
        .joined(separator: "; ")

        let errorSuffix = failureText.isEmpty ? "no fetch errors" : failureText
        logger.info("Blood pressure diagnostic: fetched systolic=\(systolicFetched), diastolic=\(diastolicFetched); \(errorSuffix)")
    }
}

@available(iOS 18.0, *)
private func sendSyncBatch(
    _ batch: SyncBatch,
    client: HealthExportClient,
    deviceId: String,
    checkpoint: [String: Int64],
    isHistoricalExport: Bool
) async throws -> SyncBatchResult {
    let batchStartedAt = Date()
    let response = try await client.syncMetrics(
        samples: batch.samples,
        deviceId: deviceId,
        checkpoint: checkpoint,
        isHistoricalExport: isHistoricalExport,
        updateLocalCheckpoints: false
    )
    guard response.success else {
        throw SyncServiceError.batchFailed(response.errorMessage)
    }

    var updatedCheckpoints: [String: Int64] = [:]
    for (key, value) in response.updatedCheckpoint {
        updatedCheckpoints[key] = value
    }

    return SyncBatchResult(
        number: batch.number,
        total: batch.total,
        sampleCount: batch.sampleCount,
        elapsed: Date().timeIntervalSince(batchStartedAt),
        updatedCheckpoints: updatedCheckpoints
    )
}
