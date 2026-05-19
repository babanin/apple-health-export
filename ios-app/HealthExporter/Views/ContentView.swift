import SwiftUI

struct ContentView: View {
    @ObservedObject var syncViewModel: SyncViewModel
    @ObservedObject var appConfig: AppConfig
    @ObservedObject var logger: AppLogger

    var body: some View {
        if #available(iOS 18.0, *) {
            NavigationStack {
                Form {
                    ControlsSection(viewModel: syncViewModel)
                    ServerSettingsSection(appConfig: appConfig)
                    SyncStatusSection(viewModel: syncViewModel)
                    LogPanelView(logger: logger)
                }
                .navigationTitle("Health Export")
            }
        } else {
            UnsupportedVersionView()
        }
    }
}
