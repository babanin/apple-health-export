import SwiftUI

struct ContentView: View {
    @ObservedObject var syncViewModel: SyncViewModel
    @ObservedObject var appConfig: AppConfig
    @ObservedObject var logger: AppLogger

    var body: some View {
        if #available(iOS 18.0, *) {
            NavigationStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HeaderView(viewModel: syncViewModel)
                        ControlsSection(viewModel: syncViewModel)
                        SyncStatusSection(viewModel: syncViewModel)
                        LogPanelView(logger: logger)
                    }
                    .padding(.horizontal, 18)
                    .padding(.top, 12)
                    .padding(.bottom, 28)
                }
                .background(AppTheme.background.ignoresSafeArea())
                .navigationTitle("Health Export")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    NavigationLink {
                        SettingsView(appConfig: appConfig)
                    } label: {
                        Image(systemName: "gearshape")
                    }
                    .accessibilityLabel("Settings")
                }
            }
        } else {
            UnsupportedVersionView()
        }
    }
}

private struct HeaderView: View {
    @ObservedObject var viewModel: SyncViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Health Export")
                        .font(.system(.largeTitle, design: .rounded, weight: .bold))

                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                StatusBadge(
                    title: viewModel.useDemoData ? "Demo" : "HealthKit",
                    systemImage: viewModel.useDemoData ? "testtube.2" : "heart.text.square.fill",
                    tint: viewModel.useDemoData ? .orange : .green
                )
            }

            if viewModel.isSyncing {
                SyncActivityStrip(progress: viewModel.syncProgress)
            }
        }
    }

    private var subtitle: String {
        guard let lastSyncTime = viewModel.lastSyncTime else {
            return "No completed sync yet"
        }
        return "Last sync \(lastSyncTime.formatted(date: .abbreviated, time: .shortened))"
    }
}

private struct SyncActivityStrip: View {
    let progress: SyncProgress

    var body: some View {
        HStack(spacing: 10) {
            ProgressView()
                .controlSize(.small)

            Text(title)
                .font(.subheadline.weight(.semibold))

            Spacer()

            if let fraction = progress.progressFraction {
                Text(fraction.formatted(.percent.precision(.fractionLength(0))))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(AppTheme.panelBackground, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var title: String {
        switch progress.phase {
        case .idle:
            return "Preparing sync"
        case .connecting:
            return "Connecting"
        case .fetching:
            return "Fetching Health data"
        case .exporting:
            return "Exporting samples"
        case .completed:
            return "Sync complete"
        case .failed:
            return "Sync failed"
        }
    }
}

struct AppSection<Content: View>: View {
    let title: String
    let systemImage: String
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(title, systemImage: systemImage)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)

            VStack(alignment: .leading, spacing: 14) {
                content
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(AppTheme.panelBackground, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(AppTheme.separator, lineWidth: 1)
            }
        }
    }
}

struct StatusBadge: View {
    let title: String
    let systemImage: String
    let tint: Color

    var body: some View {
        Label(title, systemImage: systemImage)
            .font(.caption.weight(.semibold))
            .foregroundStyle(tint)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(tint.opacity(0.14), in: Capsule())
    }
}

enum AppTheme {
    static let background = Color(uiColor: .systemBackground)
    static let panelBackground = Color(uiColor: .secondarySystemBackground)
    static let fieldBackground = Color(uiColor: .tertiarySystemBackground)
    static let separator = Color(uiColor: .separator).opacity(0.55)
}
