import SwiftUI

struct ServerSettingsSection: View {
    @ObservedObject var appConfig: AppConfig
    @ObservedObject var discoveryService: GatewayDiscoveryService

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            AppSection(title: "Gateway", systemImage: "server.rack") {
                VStack(spacing: 10) {
                    if !discoveryService.discoveredGateways.isEmpty {
                        discoveredGatewaysView
                    }

                    ServerField(title: "Host", systemImage: "network") {
                        TextField("Host or IP", text: $appConfig.grpcHost)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .keyboardType(.numbersAndPunctuation)
                    }

                    ServerField(title: "Port", systemImage: "number") {
                        TextField("Port", value: $appConfig.grpcPort, format: .number.grouping(.never))
                            .keyboardType(.numberPad)
                    }
                }

                if discoveryService.discoveredGateways.isEmpty && discoveryService.isBrowsing {
                    HStack(spacing: 6) {
                        ProgressView()
                            .controlSize(.small)
                        Text("Searching for gateways on your network...")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            AppSection(title: "Sync", systemImage: "arrow.triangle.2.circlepath") {
                VStack(spacing: 10) {
                    SettingsStepper(
                        title: "Batch Size",
                        systemImage: "square.stack.3d.up",
                        value: $appConfig.syncBatchSize,
                        range: AppConfig.batchSizeRange,
                        step: 500,
                        formattedValue: appConfig.syncBatchSize.formatted()
                    )

                    SettingsStepper(
                        title: "Parallel Batches",
                        systemImage: "arrow.triangle.branch",
                        value: $appConfig.parallelBatchCount,
                        range: AppConfig.parallelBatchRange,
                        step: 1,
                        formattedValue: "\(appConfig.parallelBatchCount)"
                    )
                }
            }

            Text("Saved automatically for ping, manual sync, hourly auto sync, and background sync.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .onChange(of: discoveryService.discoveredGateways.count) { _, newCount in
            if newCount == 1, let gateway = discoveryService.discoveredGateways.first {
                appConfig.grpcHost = gateway.host
                appConfig.grpcPort = gateway.port
            }
        }
    }

    @ViewBuilder
    private var discoveredGatewaysView: some View {
        if discoveryService.discoveredGateways.count == 1,
           let gateway = discoveryService.discoveredGateways.first {
            HStack(spacing: 10) {
                Image(systemName: "dot.radiowaves.left.and.right")
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.green)
                    .frame(width: 22)

                VStack(alignment: .leading, spacing: 1) {
                    Text(gateway.name)
                        .font(.subheadline.weight(.medium))
                        .lineLimit(1)
                    Text(gateway.displayAddress)
                        .font(.caption.monospaced())
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(.green)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 11)
            .background(AppTheme.fieldBackground, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        } else {
            ForEach(discoveryService.discoveredGateways) { gateway in
                Button {
                    appConfig.grpcHost = gateway.host
                    appConfig.grpcPort = gateway.port
                } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "dot.radiowaves.left.and.right")
                            .font(.body.weight(.semibold))
                            .foregroundStyle(.blue)
                            .frame(width: 22)

                        VStack(alignment: .leading, spacing: 1) {
                            Text(gateway.name)
                                .font(.subheadline.weight(.medium))
                                .lineLimit(1)
                            Text(gateway.displayAddress)
                                .font(.caption.monospaced())
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        if gateway.host == appConfig.grpcHost && gateway.port == appConfig.grpcPort {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                        }
                    }
                    .foregroundStyle(.primary)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 11)
                .background(AppTheme.fieldBackground, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
        }
    }
}

private struct ServerField<Field: View>: View {
    let title: String
    let systemImage: String
    @ViewBuilder var field: Field

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: systemImage)
                .font(.body.weight(.semibold))
                .foregroundStyle(.secondary)
                .frame(width: 22)

            Text(title)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.secondary)
                .frame(width: 44, alignment: .leading)

            field
                .font(.body.monospacedDigit())
                .multilineTextAlignment(.trailing)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 11)
        .background(AppTheme.fieldBackground, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct SettingsStepper: View {
    let title: String
    let systemImage: String
    @Binding var value: Int
    let range: ClosedRange<Int>
    let step: Int
    let formattedValue: String

    var body: some View {
        Stepper(value: $value, in: range, step: step) {
            HStack(spacing: 10) {
                Image(systemName: systemImage)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .frame(width: 22)

                Text(title)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.secondary)

                Spacer(minLength: 12)

                Text(formattedValue)
                    .font(.body.monospacedDigit())
                    .foregroundStyle(.primary)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 11)
        .background(AppTheme.fieldBackground, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}
