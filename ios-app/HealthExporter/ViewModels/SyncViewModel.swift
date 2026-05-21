import Foundation
import HealthKit

@available(iOS 18.0, *)
@MainActor
final class SyncViewModel: ObservableObject {
    @Published private(set) var isSyncing = false
    @Published private(set) var lastSyncTime: Date?
    @Published private(set) var totalSamplesExported = 0
    @Published private(set) var healthKitAuthorized = false
    @Published private(set) var pingState: PingState = .idle
    @Published private(set) var syncProgress: SyncProgress = .idle
    @Published var useDemoData = false
    @Published var userFacingError: UserFacingError?

    private let syncService: SyncService
    private let logger: AppLogger
    private let healthKitManagerFactory: () -> HealthKitManager
    private let autoSyncInterval: TimeInterval = 60 * 60
    private let lastAutoSyncAttemptKey = "health_export_last_auto_sync_attempt"
    private var autoSyncTask: Task<Void, Never>?

    init(
        syncService: SyncService = SyncService(),
        logger: AppLogger = .shared,
        healthKitManagerFactory: @escaping () -> HealthKitManager = { HealthKitManager() }
    ) {
        self.syncService = syncService
        self.logger = logger
        self.healthKitManagerFactory = healthKitManagerFactory
    }

    func startAutoSync() {
        guard autoSyncTask == nil else { return }

        logger.info("Hourly auto sync loop started")
        autoSyncTask = Task { [weak self] in
            guard let self else { return }
            _ = await self.runAutomaticSyncIfDue(trigger: .automatic)

            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(60 * 60))
                guard !Task.isCancelled else { return }
                _ = await self.runAutomaticSyncIfDue(trigger: .automatic)
            }
        }
    }

    func requestHealthAccess() async {
        logger.info("Requesting HealthKit authorization...")

        guard HKHealthStore.isHealthDataAvailable() else {
            showError("HealthKit not available on this device. Using demo data.")
            useDemoData = true
            logger.warning("HealthKit not available on this device")
            return
        }

        do {
            let authorized = try await healthKitManagerFactory().requestAuthorization()
            healthKitAuthorized = authorized
            useDemoData = !authorized

            if authorized {
                logger.info("HealthKit authorization granted")
            } else {
                showError("Health access denied. Using demo data.")
                logger.warning("Health access denied, switching to demo data")
            }
        } catch {
            showError("HealthKit error: \(error.localizedDescription). Using demo data.")
            useDemoData = true
            logger.error("HealthKit authorization failed: \(error.localizedDescription)")
        }
    }

    func startSync() async {
        await runSync(trigger: .manual)
    }

    func resyncHistory() async {
        logger.info("Clearing local checkpoints for historical resync")
        CheckpointManager.shared.clearAll()
        await runSync(trigger: .manual)
    }

    func runBackgroundAutoSync() async -> Bool {
        await runAutomaticSyncIfDue(trigger: .background)
    }

    func pingGateway() async {
        pingState = .pinging

        switch await syncService.pingGateway() {
        case .success(let version):
            pingState = .success(version: version)
        case .unreachable:
            pingState = .unreachable
        case .failed(let message):
            pingState = .failed(message: message)
        }
    }

    private func runAutomaticSyncIfDue(trigger: SyncTrigger) async -> Bool {
        let now = Date()
        if let lastAttempt = UserDefaults.standard.object(forKey: lastAutoSyncAttemptKey) as? Date {
            let secondsUntilNextAttempt = autoSyncInterval - now.timeIntervalSince(lastAttempt)
            if secondsUntilNextAttempt > 0 {
                let minutes = Int(ceil(secondsUntilNextAttempt / 60))
                logger.info("\(trigger.rawValue) sync skipped; next attempt due in about \(minutes) min")
                return true
            }
        }

        UserDefaults.standard.set(now, forKey: lastAutoSyncAttemptKey)
        return await runSync(trigger: trigger)
    }

    @discardableResult
    private func runSync(trigger: SyncTrigger) async -> Bool {
        guard !isSyncing else {
            logger.info("\(trigger.rawValue) sync skipped; another sync is already running")
            return true
        }

        isSyncing = true
        userFacingError = nil
        syncProgress = .idle
        defer { isSyncing = false }

        if trigger != .background && !useDemoData && !healthKitAuthorized {
            await requestHealthAccess()
            if useDemoData {
                logger.warning("\(trigger.rawValue) sync will use demo data because HealthKit authorization is unavailable")
            }
        }

        let result = await syncService.performSync(trigger: trigger, useDemoData: useDemoData) { [weak self] progress in
            self?.syncProgress = progress
        }
        if result.succeeded {
            totalSamplesExported += result.exportedCount
            if !result.noSamples {
                lastSyncTime = Date()
            } else if trigger == .manual, let message = result.message {
                showError(message)
            }
            return true
        }

        if let message = result.message {
            showError(message)
        }
        return false
    }

    private func showError(_ message: String) {
        userFacingError = UserFacingError(message: message)
    }
}
