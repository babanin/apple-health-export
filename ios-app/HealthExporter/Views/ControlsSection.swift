import SwiftUI

struct ControlsSection: View {
    @ObservedObject var viewModel: SyncViewModel

    var body: some View {
        AppSection(title: "Sync", systemImage: "arrow.triangle.2.circlepath") {
            if viewModel.useDemoData {
                Label("Demo mode is active. Authorize Health to export real data.", systemImage: "info.circle.fill")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }

            if viewModel.isSyncing {
                SyncProgressView(progress: viewModel.syncProgress)
            } else {
                Button {
                    Task { await viewModel.startSync() }
                } label: {
                    Label("Sync Now", systemImage: "arrow.triangle.2.circlepath")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryActionButtonStyle())

                HStack(spacing: 10) {
                    Button(role: .destructive) {
                        Task { await viewModel.resyncHistory() }
                    } label: {
                        Label("Resync History", systemImage: "clock.arrow.circlepath")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(SecondaryActionButtonStyle(tint: .red))

                    Button {
                        Task { await viewModel.requestHealthAccess() }
                    } label: {
                        Label("Authorize", systemImage: "heart.text.square")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(SecondaryActionButtonStyle(tint: .blue))
                }
            }

            Divider()

            HStack(spacing: 12) {
                Button {
                    Task { await viewModel.pingGateway() }
                } label: {
                    Label("Ping", systemImage: viewModel.pingState.systemImage)
                }
                .buttonStyle(SecondaryActionButtonStyle(tint: viewModel.pingState.tint))
                .disabled(viewModel.pingState.isPinging)

                Spacer()

                HStack(spacing: 6) {
                    Circle()
                        .fill(viewModel.pingState.tint)
                        .frame(width: 7, height: 7)

                    Text(viewModel.pingState.label)
                        .font(.caption.weight(.medium))
                        .foregroundStyle(viewModel.pingState.foregroundStyle)
                }
            }
        }

        if let error = viewModel.userFacingError {
            AppSection(title: "Attention", systemImage: "exclamationmark.triangle.fill") {
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

    var tint: Color {
        switch self {
        case .success:
            return .green
        case .unreachable, .failed:
            return .red
        case .idle, .pinging:
            return .blue
        }
    }
}

private struct PrimaryActionButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.vertical, 12)
            .padding(.horizontal, 14)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.blue.opacity(configuration.isPressed ? 0.78 : 1))
            )
    }
}

private struct SecondaryActionButtonStyle: ButtonStyle {
    let tint: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(tint)
            .lineLimit(1)
            .minimumScaleFactor(0.85)
            .padding(.vertical, 10)
            .padding(.horizontal, 12)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(tint.opacity(configuration.isPressed ? 0.2 : 0.12))
            )
    }
}
