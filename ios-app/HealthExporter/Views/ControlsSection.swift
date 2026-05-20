import SwiftUI

struct ControlsSection: View {
    @ObservedObject var viewModel: SyncViewModel

    var body: some View {
        Section("Sync") {
            if viewModel.useDemoData {
                Label("Demo Mode - tap Authorize to enable real Health data.", systemImage: "info.circle.fill")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }

            if viewModel.isSyncing {
                SyncProgressView(progress: viewModel.syncProgress)
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    Button {
                        Task { await viewModel.startSync() }
                    } label: {
                        Label("Sync Now", systemImage: "arrow.triangle.2.circlepath")
                    }
                    .buttonStyle(.borderedProminent)

                    Button(role: .destructive) {
                        Task { await viewModel.resyncHistory() }
                    } label: {
                        Label("Resync History", systemImage: "clock.arrow.circlepath")
                    }
                    .buttonStyle(.bordered)
                }
            }

            HStack {
                Button {
                    Task { await viewModel.pingGateway() }
                } label: {
                    Label("Ping", systemImage: viewModel.pingState.systemImage)
                }
                .buttonStyle(.bordered)
                .disabled(viewModel.pingState.isPinging)

                Spacer()

                Text(viewModel.pingState.label)
                    .font(.caption)
                    .foregroundStyle(viewModel.pingState.foregroundStyle)
            }

            Button("Authorize Health Access") {
                Task { await viewModel.requestHealthAccess() }
            }
        }

        if let error = viewModel.userFacingError {
            Section {
                Label(error.message, systemImage: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(.red)
            }
        }
    }
}

private struct SyncProgressView: View {
    let progress: SyncProgress

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let fraction = progress.progressFraction {
                ProgressView(value: fraction) {
                    Text(title)
                } currentValueLabel: {
                    Text(percentText(for: fraction))
                }
            } else {
                ProgressView(title)
            }

            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)

            if let eta = progress.estimatedTimeRemaining {
                Text("ETA \(durationText(eta))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var title: String {
        switch progress.phase {
        case .idle:
            return "Waiting..."
        case .connecting:
            return "Connecting..."
        case .fetching:
            return "Fetching Health data..."
        case .exporting:
            return "Exporting samples..."
        case .completed:
            return "Sync complete"
        case .failed:
            return "Sync failed"
        }
    }

    private var detail: String {
        switch progress.phase {
        case .fetching:
            let metrics = "\(progress.metricsCompleted.formatted())/\(progress.totalMetrics.formatted()) metrics"
            return "\(progress.fetchedSamples.formatted()) samples found, \(metrics)"
        case .exporting:
            let total = progress.totalSamples ?? 0
            let remaining = progress.remainingSamples ?? 0
            return "\(progress.exportedSamples.formatted())/\(total.formatted()) exported, \(remaining.formatted()) left"
        case .completed:
            return progress.message ?? "\(progress.exportedSamples.formatted()) samples exported"
        case .failed:
            return progress.message ?? "The sync did not complete"
        case .connecting, .idle:
            return progress.message ?? "Preparing sync"
        }
    }

    private func percentText(for fraction: Double) -> String {
        fraction.formatted(.percent.precision(.fractionLength(0)))
    }

    private func durationText(_ interval: TimeInterval) -> String {
        let formatter = DateComponentsFormatter()
        formatter.allowedUnits = interval >= 3600 ? [.hour, .minute] : [.minute, .second]
        formatter.unitsStyle = .abbreviated
        formatter.maximumUnitCount = 2
        return formatter.string(from: interval) ?? "calculating"
    }
}

private extension PingState {
    var systemImage: String {
        switch self {
        case .success:
            return "checkmark.circle"
        case .unreachable, .failed:
            return "exclamationmark.triangle"
        case .idle, .pinging:
            return "network"
        }
    }

    var foregroundStyle: Color {
        switch self {
        case .success:
            return .green
        case .unreachable, .failed:
            return .red
        case .idle, .pinging:
            return .secondary
        }
    }
}
