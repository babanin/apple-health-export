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

    func performSync(trigger: SyncTrigger, useDemoData: Bool) async -> SyncResult {
        guard !isRunning else {
            logger.info("\(trigger.rawValue) sync skipped; another sync is already running")
            return .success(exportedCount: 0, message: "Sync already running")
        }

        isRunning = true
        defer { isRunning = false }

        let configuration = currentConfiguration()
        logger.info("Starting \(trigger.rawValue.lowercased()) sync using \(configuration.displayAddress)...")

        let client = clientFactory(configuration)
        guard await client.checkConnection() else {
            logger.error("TCP connection refused")
            return .failure("Server unreachable at \(configuration.displayAddress)")
        }
        logger.info("TCP connection OK")

        do {
            try client.connect()
            logger.info("Connected to \(configuration.displayAddress)")
        } catch {
            logger.error("Connection failed: \(error.localizedDescription)")
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
                return .failure("Gateway returned unhealthy")
            }
            logger.info("Gateway responded (version: \(version))")
        } catch {
            let message = gatewayErrorMessage(for: error)
            logger.error(message)
            return .failure(message)
        }

        do {
            logger.info("Device ID: \(deviceId)")

            let samples: [HealthMetricSample]
            if useDemoData {
                logger.info("Using demo data")
                samples = demoDataManager.generateDemoSamples()
            } else {
                logger.info("Fetching HealthKit data...")
                samples = try await healthKitManagerFactory().fetchAllMetrics()
            }
            logger.info("Fetched \(samples.count) samples")

            guard !samples.isEmpty else {
                logger.warning("No samples to sync")
                return .success(exportedCount: 0, noSamples: true, message: "No samples to sync")
            }

            let batchSize = 500
            var exportedCount = 0

            for start in stride(from: 0, to: samples.count, by: batchSize) {
                let end = min(start + batchSize, samples.count)
                let batch = Array(samples[start..<end])
                logger.info("Sending batch \(start / batchSize + 1): \(batch.count) samples")

                let response = try await client.syncMetrics(samples: batch, deviceId: deviceId)
                guard response.success else {
                    logger.error("Batch failed: \(response.errorMessage)")
                    throw SyncServiceError.batchFailed(response.errorMessage)
                }

                exportedCount += batch.count
                logger.info("Batch response: success=\(response.success), exported=\(exportedCount)")
            }

            logger.info("\(trigger.rawValue) sync complete - \(exportedCount) samples exported")
            return .success(exportedCount: exportedCount)
        } catch {
            logger.error("Sync failed: \(error.localizedDescription)")
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
