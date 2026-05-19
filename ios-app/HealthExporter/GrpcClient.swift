import Foundation
import GRPCCore
import GRPCProtobuf
import GRPCNIOTransportHTTP2
import Network

final class ResumeGuard: @unchecked Sendable {
    private let lock = NSLock()
    private var done = false

    func tryLock() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard !done else { return false }
        done = true
        return true
    }
}

@available(iOS 18.0, *)
class HealthExportClient {
    private let serverAddress: String
    private let serverPort: Int
    private var transport: HTTP2ClientTransport.Posix?
    private var grpcClient: GRPCCore.GRPCClient<HTTP2ClientTransport.Posix>?
    private var client: HealthExport_HealthExportService.Client<HTTP2ClientTransport.Posix>?
    private var connectionTask: Task<Void, Never>?

    init(serverAddress: String, serverPort: Int = 50051) {
        self.serverAddress = serverAddress
        self.serverPort = serverPort
    }

    func checkConnection(timeout: TimeInterval = 5) async -> Bool {
        await withCheckedContinuation { continuation in
            let host = NWEndpoint.Host(serverAddress)
            let port = NWEndpoint.Port(rawValue: UInt16(serverPort))!
            let connection = NWConnection(host: host, port: port, using: .tcp)
            let queue = DispatchQueue(label: "health-export-network-check")
            let resumeGuard = ResumeGuard()

            @Sendable func finish(_ result: Bool) {
                guard resumeGuard.tryLock() else { return }
                connection.stateUpdateHandler = nil
                connection.cancel()
                continuation.resume(returning: result)
            }

            connection.stateUpdateHandler = { state in
                if case .ready = state {
                    finish(true)
                } else if case .failed(let error) = state {
                    AppLogger.shared.debug("NWConnection failed: \(error)")
                    finish(false)
                } else if case .cancelled = state {
                    finish(false)
                }
            }
            connection.start(queue: queue)

            queue.asyncAfter(deadline: .now() + timeout) {
                finish(false)
            }
        }
    }

    func connect() throws {
        AppLogger.shared.info("Connecting to \(serverAddress):\(serverPort)...")
        let transport = try HTTP2ClientTransport.Posix(
            target: .ipv4(address: serverAddress, port: serverPort),
            transportSecurity: .plaintext
        )
        self.transport = transport
        let grpc = GRPCCore.GRPCClient(transport: transport)
        self.grpcClient = grpc
        self.client = HealthExport_HealthExportService.Client(wrapping: grpc)
        self.connectionTask = Task.detached {
            do {
                try await grpc.runConnections()
            } catch is CancellationError {
                AppLogger.shared.debug("gRPC client connection task cancelled")
            } catch {
                AppLogger.shared.error("gRPC client connection task failed: \(error)")
            }
        }
        AppLogger.shared.info("gRPC client created successfully")
    }

    func ping(deviceId: String) async throws -> (ok: Bool, version: String) {
        guard let client = self.client else {
            throw HealthExportClientError.notConnected
        }

        var request = HealthExport_PingRequest()
        request.deviceID = deviceId
        AppLogger.shared.info("Sending ping request to \(serverAddress):\(serverPort)...")

        let clientRequest = ClientRequest(message: request, metadata: [:])

        do {
            return try await withTimeout(seconds: 30) {
                AppLogger.shared.debug("Executing gRPC ping call...")
                let response = try await client.ping(
                    request: clientRequest,
                    serializer: ProtobufSerializer<HealthExport_PingRequest>(),
                    deserializer: ProtobufDeserializer<HealthExport_PingResponse>()
                )
                AppLogger.shared.info("Received ping response: ok=\(response.ok), version=\(response.serverVersion)")
                return (ok: response.ok, version: response.serverVersion)
            }
        } catch let err as HealthExportClientError {
            AppLogger.shared.error("Ping failed with client error: \(err)")
            throw err
        } catch {
            AppLogger.shared.error("Ping RPC failed: \(error)")
            throw error
        }
    }

    func syncMetrics(samples: [HealthMetricSample], deviceId: String) async throws -> HealthExport_SyncResponse {
        guard let client = self.client else {
            AppLogger.shared.error("syncMetrics called but client not connected")
            throw HealthExportClientError.notConnected
        }

        let checkpointManager = CheckpointManager.shared
        let checkpointDict = checkpointManager.getAllCheckpoints()
        AppLogger.shared.debug("Syncing \(samples.count) samples with \(checkpointDict.count) checkpoints")

        let grpcSamples = samples.map { sample -> HealthExport_HealthSample in
            var grpcSample = HealthExport_HealthSample()
            grpcSample.metricName = sample.metricName
            grpcSample.timestampMs = sample.timestampMs
            grpcSample.value = sample.value
            grpcSample.unit = sample.unit
            grpcSample.source = sample.source
            grpcSample.labels = sample.labels
            return grpcSample
        }

        var request = HealthExport_SyncRequest()
        request.deviceID = deviceId
        request.batchID = UUID().uuidString
        request.samples = grpcSamples
        request.checkpoint = checkpointDict
        request.isHistoricalExport = checkpointDict.isEmpty

        let clientRequest = ClientRequest(message: request, metadata: [:])

        do {
            return try await withTimeout(seconds: 60) {
                let response: HealthExport_SyncResponse = try await client.syncMetrics(
                    request: clientRequest,
                    serializer: ProtobufSerializer<HealthExport_SyncRequest>(),
                    deserializer: ProtobufDeserializer<HealthExport_SyncResponse>()
                )

                if response.success {
                    var updatedCheckpoints: [String: Int64] = [:]
                    for (key, value) in response.updatedCheckpoint {
                        updatedCheckpoints[key] = value
                    }
                    checkpointManager.updateCheckpoints(updatedCheckpoints)
                    AppLogger.shared.debug("Updated \(updatedCheckpoints.count) checkpoints from server")
                } else {
                    AppLogger.shared.warning("Server returned unsuccessful sync response")
                }

                return response
            }
        } catch let err as HealthExportClientError {
            throw err
        } catch {
            AppLogger.shared.error("gRPC syncMetrics failed: \(error.localizedDescription)")
            throw error
        }
    }

    private func withTimeout<T: Sendable>(seconds: Int64, operation: @escaping @Sendable () async throws -> T) async throws -> T {
        try await withThrowingTaskGroup(of: T.self) { group in
            group.addTask(operation: operation)
            group.addTask {
                try await Task.sleep(for: .seconds(seconds))
                throw HealthExportClientError.timeout
            }
            do {
                let result = try await group.next()!
                group.cancelAll()
                return result
            } catch {
                group.cancelAll()
                throw error
            }
        }
    }

    func getCheckpoint(deviceId: String) async throws -> [String: Int64] {
        guard let client = self.client else {
            throw HealthExportClientError.notConnected
        }

        var request = HealthExport_CheckpointRequest()
        request.deviceID = deviceId

        let clientRequest = ClientRequest(message: request, metadata: [:])

        let response: HealthExport_CheckpointResponse = try await client.getCheckpoint(
            request: clientRequest,
            serializer: ProtobufSerializer<HealthExport_CheckpointRequest>(),
            deserializer: ProtobufDeserializer<HealthExport_CheckpointResponse>()
        )

        var result: [String: Int64] = [:]
        for (key, value) in response.checkpoint {
            result[key] = value
        }
        return result
    }

    func disconnect() {
        AppLogger.shared.info("Disconnecting gRPC client")
        grpcClient?.beginGracefulShutdown()
        connectionTask?.cancel()
        connectionTask = nil
        client = nil
        grpcClient = nil
        transport = nil
    }
}

enum HealthExportClientError: Error, Sendable {
    case notConnected
    case syncFailed(String)
    case timeout
    case connectionRefused
}
