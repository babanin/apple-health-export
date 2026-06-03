#![allow(clippy::unwrap_used, clippy::expect_used)]

fn main() {
    let proto_path = "../proto/health_export.proto";
    tonic_build::configure()
        .build_server(true)
        .build_client(false)
        .compile_protos(&[proto_path], &["../proto"])
        .expect("Failed to compile protobuf definitions");
}
