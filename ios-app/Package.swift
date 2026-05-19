// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "HealthExporter",
    platforms: [.iOS(.v18)],
    dependencies: [
        .package(url: "https://github.com/grpc/grpc-swift.git", from: "2.0.0"),
        .package(url: "https://github.com/apple/swift-protobuf.git", from: "1.28.0"),
    ],
    targets: [
        .executableTarget(
            name: "HealthExporter",
            dependencies: [
                .product(name: "GRPCCore", package: "grpc-swift"),
                .product(name: "GRPCProtobuf", package: "grpc-swift"),
                .product(name: "SwiftProtobuf", package: "swift-protobuf"),
                .product(name: "NIOCore", package: "grpc-swift"),
            ],
            path: "HealthExporter",
            exclude: [
                "HealthExporter.entitlements",
                "Info.plist",
                "Generated",
            ],
            resources: [
                .copy("Generated"),
            ]
        ),
    ]
)