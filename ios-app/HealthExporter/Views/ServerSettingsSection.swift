import SwiftUI

struct ServerSettingsSection: View {
    @ObservedObject var appConfig: AppConfig

    var body: some View {
        AppSection(title: "Settings", systemImage: "gearshape") {
            VStack(spacing: 10) {
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

            Text("Saved automatically for ping, manual sync, hourly auto sync, and background sync.")
                .font(.caption)
                .foregroundStyle(.secondary)
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
