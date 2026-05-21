import SwiftUI

struct SettingsView: View {
    @ObservedObject var appConfig: AppConfig

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                ServerSettingsSection(appConfig: appConfig)
            }
            .padding(.horizontal, 18)
            .padding(.top, 12)
            .padding(.bottom, 28)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
    }
}
