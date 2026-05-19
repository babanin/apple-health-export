import SwiftUI

struct UnsupportedVersionView: View {
    var body: some View {
        ContentUnavailableView {
            Label("iOS 18.0+ Required", systemImage: "iphone.slash")
        } description: {
            Text("This app requires iOS 18.0 or later for gRPC support.")
        }
    }
}
