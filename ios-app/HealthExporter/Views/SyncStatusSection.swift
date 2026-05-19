import SwiftUI

struct SyncStatusSection: View {
    @ObservedObject var viewModel: SyncViewModel

    var body: some View {
        Section("Status") {
            LabeledContent("Last Sync") {
                Text(viewModel.lastSyncTime?.formatted() ?? "Never")
            }

            LabeledContent("Samples Exported") {
                Text("\(viewModel.totalSamplesExported)")
            }

            LabeledContent("Data Source") {
                Text(viewModel.useDemoData ? "Demo Data" : "HealthKit")
            }
        }
    }
}
