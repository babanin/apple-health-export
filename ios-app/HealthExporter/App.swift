import SwiftUI

@main
struct HealthExporterApp: App {
    @StateObject private var syncViewModel = SyncViewModel()
    @StateObject private var appConfig = AppConfig.shared
    @StateObject private var logger = AppLogger.shared

    private let backgroundSyncScheduler = BackgroundSyncScheduler()

    var body: some Scene {
        WindowGroup {
            ContentView(
                syncViewModel: syncViewModel,
                appConfig: appConfig,
                logger: logger
            )
            .onAppear {
                backgroundSyncScheduler.register {
                    await syncViewModel.runBackgroundAutoSync()
                }
                backgroundSyncScheduler.schedule()
                syncViewModel.startAutoSync()
            }
        }
    }
}
