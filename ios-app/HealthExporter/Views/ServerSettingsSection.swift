import SwiftUI

struct ServerSettingsSection: View {
    @ObservedObject var appConfig: AppConfig

    var body: some View {
        Section {
            TextField("Host or IP", text: $appConfig.grpcHost)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.numbersAndPunctuation)

            TextField("Port", value: $appConfig.grpcPort, format: .number.grouping(.never))
                .keyboardType(.numberPad)
        } header: {
            Text("Server")
        } footer: {
            Text("Saved automatically and used by ping, manual sync, and hourly auto sync.")
        }
    }
}
