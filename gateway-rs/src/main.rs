pub mod checkpoint;
pub mod server;
pub mod vm_writer;

use std::env;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;

use tonic::transport::Server;
use tracing::{info, warn};
use tracing_subscriber::EnvFilter;

use crate::checkpoint::CheckpointStore;
use crate::server::HealthExportService;
use crate::vm_writer::VmWriter;

mod proto {
    #![allow(clippy::unwrap_used, clippy::expect_used)]
    include!(concat!(env!("OUT_DIR"), "/health_export.rs"));
}

pub use proto::*;

fn parse_env(name: &str, default: &str) -> String {
    env::var(name).unwrap_or_else(|_| default.to_string())
}

fn parse_env_int(name: &str, default: i32) -> i32 {
    env::var(name)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    let port = parse_env_int("GRPC_PORT", 50051);
    let vm_url = parse_env("VM_URL", "http://victoriametrics:8428");
    let db_path = parse_env("DB_PATH", "/data/checkpoints.db");

    #[allow(clippy::expect_used)]
    let addr: SocketAddr = format!("0.0.0.0:{port}")
        .parse()
        .expect("invalid bind address");

    let vm_writer = Arc::new(VmWriter::new(
        vm_url,
        Duration::from_secs(1),
        5000,
        5,
        Duration::from_millis(500),
    ));

    vm_writer.start().await;

    #[allow(clippy::expect_used)]
    let checkpoint_store =
        CheckpointStore::new(&db_path).expect("failed to open checkpoint database");

    let service = HealthExportService::new(vm_writer.clone(), checkpoint_store);

    let max_msg_size = 100 * 1024 * 1024;

    info!(port, ?addr, "starting Apple Health Export gRPC gateway");

    start_mdns_advertising(port as u16);

    let shutdown = async {
        if let Err(e) = tokio::signal::ctrl_c().await {
            tracing::error!("failed to install signal handler: {e}");
        }
        info!("received shutdown signal");
    };

    let result = Server::builder()
        .add_service(
            proto::health_export_service_server::HealthExportServiceServer::new(service)
                .max_encoding_message_size(max_msg_size)
                .max_decoding_message_size(max_msg_size),
        )
        .serve_with_shutdown(addr, shutdown)
        .await;

    vm_writer.stop().await;

    if let Err(e) = result {
        tracing::error!("server error: {e}");
    }
}

fn start_mdns_advertising(port: u16) {
    let hostname = gethostname::gethostname().to_string_lossy().to_string();
    let instance = format!("{hostname} — Apple Health Export");

    tokio::spawn(async move {
        match mdns_sd::ServiceDaemon::new() {
            Ok(daemon) => {
                let svc = mdns_sd::ServiceInfo::new(
                    "_apple-health-export._tcp",
                    &instance,
                    &instance,
                    "",
                    port,
                    std::collections::HashMap::<String, String>::new(),
                );
                match svc {
                    Ok(info) => {
                        if let Err(e) = daemon.register(info) {
                            warn!("mDNS registration failed: {e}");
                        } else {
                            info!("mDNS advertising on _apple-health-export._tcp:{port}");
                        }
                    }
                    Err(e) => warn!("mDNS service info creation failed: {e}"),
                }
                tokio::signal::ctrl_c().await.ok();
                let _ = daemon.shutdown();
            }
            Err(e) => warn!("mDNS daemon creation failed: {e}"),
        }
    });
}
