import Foundation
import SwiftUI

final class AppLogger: ObservableObject, @unchecked Sendable {
    static let shared = AppLogger()

    @Published var entries: [LogEntry] = []

    private let maxEntries = 500
    private let queue = DispatchQueue.main

    private init() {}

    func info(_ message: String, file: String = #file, line: Int = #line) {
        log(level: .info, message: message, file: file, line: line)
    }

    func warning(_ message: String, file: String = #file, line: Int = #line) {
        log(level: .warning, message: message, file: file, line: line)
    }

    func error(_ message: String, file: String = #file, line: Int = #line) {
        log(level: .error, message: message, file: file, line: line)
    }

    func debug(_ message: String, file: String = #file, line: Int = #line) {
        log(level: .debug, message: message, file: file, line: line)
    }

    func clear() {
        queue.async { [weak self] in
            self?.entries.removeAll()
        }
    }

    private func log(level: LogLevel, message: String, file: String, line: Int) {
        let filename = (file as NSString).lastPathComponent
        let entry = LogEntry(
            timestamp: Date(),
            level: level,
            message: "[\(filename):\(line)] \(message)"
        )
        queue.async { [weak self] in
            self?.appendEntry(entry)
        }
    }

    private func appendEntry(_ entry: LogEntry) {
        entries.append(entry)
        if entries.count > maxEntries {
            entries.removeFirst(entries.count - maxEntries)
        }
    }
}

enum LogLevel: String, CaseIterable {
    case debug = "DBG"
    case info = "INF"
    case warning = "WRN"
    case error = "ERR"

    var color: Color {
        switch self {
        case .debug: return .gray
        case .info: return .blue
        case .warning: return .orange
        case .error: return .red
        }
    }
}

struct LogEntry: Identifiable, Equatable {
    let id = UUID()
    let timestamp: Date
    let level: LogLevel
    let message: String

    var formattedTime: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: timestamp)
    }

    var fullText: String {
        "\(formattedTime) [\(level.rawValue)] \(message)"
    }
}
