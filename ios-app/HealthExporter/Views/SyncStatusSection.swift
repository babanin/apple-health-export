import SwiftUI

struct SyncStatusSection: View {
    @ObservedObject var viewModel: SyncViewModel

    var body: some View {
        AppSection(title: "Status", systemImage: "waveform.path.ecg") {
            StatusRow(
                title: "Last Sync",
                value: viewModel.lastSyncTime?.formatted(date: .abbreviated, time: .shortened) ?? "Never",
                systemImage: "clock"
            )

            Divider()

            StatusRow(
                title: "Samples Exported",
                value: viewModel.totalSamplesExported.formatted(),
                systemImage: "chart.bar.xaxis"
            )

            Divider()

            StatusRow(
                title: "Data Source",
                value: viewModel.useDemoData ? "Demo Data" : "HealthKit",
                systemImage: viewModel.useDemoData ? "testtube.2" : "heart.text.square"
            )
        }
    }
}

private struct StatusRow: View {
    let title: String
    let value: String
    let systemImage: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: systemImage)
                .font(.body.weight(.semibold))
                .foregroundStyle(.blue)
                .frame(width: 24)

            Text(title)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.secondary)

            Spacer(minLength: 12)

            Text(value)
                .font(.body.weight(.semibold))
                .monospacedDigit()
                .multilineTextAlignment(.trailing)
        }
    }
}
