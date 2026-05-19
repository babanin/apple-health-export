import BackgroundTasks
import Foundation

final class BackgroundSyncScheduler {
    private let identifier = "com.apple-health-export.health.sync"
    private let logger: AppLogger
    private var didRegister = false

    init(logger: AppLogger = .shared) {
        self.logger = logger
    }

    func register(syncHandler: @escaping @MainActor () async -> Bool) {
        guard !didRegister else { return }
        didRegister = true

        BGTaskScheduler.shared.register(forTaskWithIdentifier: identifier, using: nil) { [weak self] task in
            guard let self, let task = task as? BGProcessingTask else { return }
            self.handle(task: task, syncHandler: syncHandler)
        }
    }

    func schedule() {
        let request = BGProcessingTaskRequest(identifier: identifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 60 * 60)
        request.requiresNetworkConnectivity = true

        do {
            try BGTaskScheduler.shared.submit(request)
            logger.info("Background sync scheduled in about 1 hour")
        } catch {
            logger.error("Failed to schedule background sync: \(error.localizedDescription)")
        }
    }

    private func handle(
        task: BGProcessingTask,
        syncHandler: @escaping @MainActor () async -> Bool
    ) {
        schedule()
        let completion = BackgroundTaskCompletion(task: task)

        task.expirationHandler = { [logger] in
            logger.warning("Background sync expired")
            completion.finish(success: false)
        }

        Task { @MainActor in
            let success = await syncHandler()
            completion.finish(success: success)
        }
    }
}

private final class BackgroundTaskCompletion: @unchecked Sendable {
    private let task: BGProcessingTask
    private let completionGuard = ResumeGuard()

    init(task: BGProcessingTask) {
        self.task = task
    }

    func finish(success: Bool) {
        guard completionGuard.tryLock() else { return }
        task.setTaskCompleted(success: success)
    }
}
