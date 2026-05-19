import SwiftUI

struct LogPanelView: View {
    @ObservedObject var logger: AppLogger

    var body: some View {
        Section {
            HStack {
                Text("Recent activity")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                Spacer()

                Button(role: .destructive) {
                    logger.clear()
                } label: {
                    Label("Clear", systemImage: "trash")
                        .labelStyle(.iconOnly)
                }
                .buttonStyle(.borderless)
            }

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 4) {
                        ForEach(logger.entries) { entry in
                            LogEntryRow(entry: entry)
                                .id(entry.id)
                        }
                    }
                    .padding(.vertical, 4)
                }
                .frame(minHeight: 180, maxHeight: 260)
                .onChange(of: logger.entries.last?.id) { _, lastId in
                    guard let lastId else { return }
                    Task { @MainActor in
                        await Task.yield()
                        proxy.scrollTo(lastId, anchor: .bottom)
                    }
                }
            }
        } header: {
            Text("Logs")
        }
    }
}

private struct LogEntryRow: View {
    let entry: LogEntry

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            Text(entry.formattedTime)
                .foregroundStyle(.secondary)
                .frame(width: 52, alignment: .leading)

            Text(entry.level.rawValue)
                .fontWeight(.semibold)
                .foregroundStyle(entry.level.color)
                .frame(width: 28, alignment: .leading)

            Text(entry.message)
                .textSelection(.enabled)
        }
        .font(.system(.caption2, design: .monospaced))
    }
}
