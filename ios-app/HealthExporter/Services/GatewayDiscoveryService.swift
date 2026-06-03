import Foundation
import Network

@MainActor
final class GatewayDiscoveryService: NSObject, ObservableObject {
    @Published private(set) var discoveredGateways: [DiscoveredGateway] = []
    @Published private(set) var isBrowsing = false

    private var browser: NWBrowser?
    private var serviceResolvers: [String: NetService] = [:]
    private var resolvedServices: [String: (host: String, port: Int)] = [:]

    struct DiscoveredGateway: Identifiable, Equatable, Sendable {
        let id: String
        let name: String
        let host: String
        let port: Int

        var displayAddress: String { "\(host):\(port)" }
    }

    func startBrowsing() {
        guard browser == nil else { return }
        isBrowsing = true

        let params = NWParameters.tcp
        let browser = NWBrowser(
            for: .bonjour(type: "_apple-health-export._tcp", domain: nil),
            using: params
        )

        browser.browseResultsChangedHandler = { [weak self] results, _ in
            Task { @MainActor in
                self?.handleResults(results)
            }
        }

        browser.stateUpdateHandler = { [weak self] state in
            if case .failed(let error) = state {
                Task { @MainActor in
                    self?.handleBrowserFailure(error)
                }
            }
        }

        browser.start(queue: .main)
        self.browser = browser
    }

    func stopBrowsing() {
        browser?.cancel()
        browser = nil
        isBrowsing = false
        for resolver in serviceResolvers.values {
            resolver.stop()
        }
        serviceResolvers.removeAll()
        resolvedServices.removeAll()
        discoveredGateways.removeAll()
    }

    private func handleResults(_ results: Set<NWBrowser.Result>) {
        let currentIds = Set(results.compactMap { result -> String? in
            guard case .service(let name, let type, let domain, _) = result.endpoint else {
                return nil
            }
            return "\(name)-\(type)-\(domain)"
        })

        discoveredGateways.removeAll { !currentIds.contains($0.id) }

        resolvedServices = resolvedServices.filter { currentIds.contains($0.key) }
        serviceResolvers = serviceResolvers.filter { currentIds.contains($0.key) }

        for result in results {
            guard case .service(let name, let type, let domain, _) = result.endpoint else {
                continue
            }
            let id = "\(name)-\(type)-\(domain)"

            if let resolved = resolvedServices[id] {
                let gateway = DiscoveredGateway(
                    id: id,
                    name: name,
                    host: resolved.host,
                    port: resolved.port
                )
                if !discoveredGateways.contains(gateway) {
                    discoveredGateways.append(gateway)
                }
                continue
            }

            guard serviceResolvers[id] == nil else { continue }

            let service = NetService(domain: domain, type: type, name: name)
            serviceResolvers[id] = service
            service.delegate = self
            service.schedule(in: .main, forMode: .common)
            service.resolve(withTimeout: 5)
        }
    }

    private func handleBrowserFailure(_ error: NWError) {
        AppLogger.shared.error("mDNS browser failed: \(error)")
    }

    private func gatewayDidResolve(id: String, host: String, port: Int) {
        resolvedServices[id] = (host, port)
        serviceResolvers[id] = nil

        // Reconstruct the name from the id: "name-type-domain"
        let parts = id.split(separator: "-", maxSplits: 2)
        let name = parts.first.map(String.init) ?? id

        let gateway = DiscoveredGateway(
            id: id,
            name: name,
            host: host,
            port: port
        )

        if !discoveredGateways.contains(gateway) {
            discoveredGateways.append(gateway)
        }

        AppLogger.shared.info("Discovered gateway: \(gateway.displayAddress) (\(name))")
    }
}

extension GatewayDiscoveryService: NetServiceDelegate {
    func netServiceDidResolveAddress(_ sender: NetService) {
        guard let hostName = sender.hostName, !hostName.isEmpty else {
            return
        }

        let id = "\(sender.name)-\(sender.type)-\(sender.domain)"
        gatewayDidResolve(id: id, host: hostName, port: sender.port)
        sender.stop()
    }

    func netService(_ sender: NetService, didNotResolve errorDict: [String: NSNumber]) {
        let id = "\(sender.name)-\(sender.type)-\(sender.domain)"
        AppLogger.shared.warning("Failed to resolve mDNS service \(sender.name): \(errorDict)")
        serviceResolvers[id] = nil
    }
}
