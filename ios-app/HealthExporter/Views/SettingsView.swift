import SwiftUI

struct SettingsView: View {
    @ObservedObject var appConfig: AppConfig
    @StateObject private var discoveryService = GatewayDiscoveryService()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                ServerSettingsSection(
                    appConfig: appConfig,
                    discoveryService: discoveryService
                )
            }
            .padding(.horizontal, 18)
            .padding(.top, 12)
            .padding(.bottom, 28)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            discoveryService.startBrowsing()
        }
        .onDisappear {
            discoveryService.stopBrowsing()
        }
    }
}
