import SwiftUI
import UIKit

struct LogPanelView: View {
    @ObservedObject var logger: AppLogger

    var body: some View {
        AppSection(title: "Logs", systemImage: "terminal") {
            HStack {
                Text("\(logger.entries.count.formatted()) recent entries")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.secondary)

                Spacer()

                Button {
                    UIPasteboard.general.string = logger.entries.map(\.fullText).joined(separator: "\n")
                } label: {
                    Label("Copy all logs", systemImage: "doc.on.doc")
                        .labelStyle(.iconOnly)
                }
                .buttonStyle(LogToolbarButtonStyle(tint: .blue))
                .disabled(logger.entries.isEmpty)

                Button(role: .destructive) {
                    logger.clear()
                } label: {
                    Label("Clear", systemImage: "trash")
                        .labelStyle(.iconOnly)
                }
                .buttonStyle(LogToolbarButtonStyle(tint: .red))
                .disabled(logger.entries.isEmpty)
            }

            ScrollViewReader { proxy in
                ScrollView {
                    if logger.entries.isEmpty {
                        Text("No log entries yet")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, minHeight: 120)
                    } else {
                        LazyVStack(alignment: .leading, spacing: 6) {
                            ForEach(logger.entries) { entry in
                                LogEntryRow(entry: entry)
                                    .id(entry.id)
                            }
                        }
                        .padding(10)
                    }
                }
                .frame(minHeight: 180, maxHeight: 260)
                .background(Color.black.opacity(0.88), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                .task(id: logger.entries.last?.id) {
                    let lastId = logger.entries.last?.id
                    guard let lastId else { return }
                    try? await Task.sleep(for: .milliseconds(75))

                    await MainActor.run {
                        proxy.scrollTo(lastId, anchor: .bottom)
                    }
                }
            }
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
                .fixedSize(horizontal: false, vertical: true)
        }
        .font(.system(.caption2, design: .monospaced))
        .foregroundStyle(.white.opacity(0.92))
    }
}

private struct LogToolbarButtonStyle: ButtonStyle {
    let tint: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(tint)
            .frame(width: 34, height: 34)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(tint.opacity(configuration.isPressed ? 0.22 : 0.12))
            )
    }
}
