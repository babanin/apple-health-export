import Foundation

class AppConfig: ObservableObject {
    nonisolated(unsafe) static let shared = AppConfig()

    @Published var grpcHost: String {
        didSet { UserDefaults.standard.set(grpcHost, forKey: "health_export_grpc_host") }
    }
    @Published var grpcPort: Int {
        didSet { UserDefaults.standard.set(grpcPort, forKey: "health_export_grpc_port") }
    }

    private init() {
        let defaults = UserDefaults.standard
        self.grpcHost = defaults.string(forKey: "health_export_grpc_host")
            ?? (Bundle.main.object(forInfoDictionaryKey: "HEALTH_EXPORT_GRPC_HOST") as? String ?? "192.168.1.100")
        self.grpcPort = defaults.object(forKey: "health_export_grpc_port") as? Int
            ?? (Bundle.main.object(forInfoDictionaryKey: "HEALTH_EXPORT_GRPC_PORT") as? Int ?? 50051)
    }
}