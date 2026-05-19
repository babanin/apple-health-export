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
                ProgressView("Syncing...")
            } else {
                Button {
                    Task { await viewModel.startSync() }
                } label: {
                    Label("Sync Now", systemImage: "arrow.triangle.2.circlepath")
                }
                .buttonStyle(.borderedProminent)
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
