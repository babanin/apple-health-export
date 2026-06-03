mod config;
mod platform;
mod supervisor;

use clap::{Parser, Subcommand};
use supervisor::{ManagedProcess, Supervisor};
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

#[derive(Parser)]
#[command(
    name = "apple-health-export",
    about = "Apple Health Export server stack"
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Start Victoria Metrics, Grafana, and the gRPC gateway
    Start,
    /// Gracefully stop all services
    Stop,
    /// Check status of all services
    Status,
    /// Create data directories and write config files
    Setup,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Start => cmd_start().await,
        Commands::Stop => cmd_stop().await,
        Commands::Status => cmd_status(),
        Commands::Setup => cmd_setup(),
    }
}

async fn cmd_start() {
    info!("Apple Health Export starting...");

    // Setup directories
    let dirs = match config::AppDirs::create() {
        Ok(d) => d,
        Err(e) => {
            error!("Failed to create data directories: {e}");
            std::process::exit(1);
        }
    };

    // Write provisioning files
    if let Err(e) = dirs.write_provisioning_files() {
        error!("Failed to write provisioning files: {e}");
        std::process::exit(1);
    }

    // Detect platform
    let platform = match platform::Platform::current() {
        Some(p) => p,
        None => {
            error!(
                "Unsupported platform: {} {}",
                std::env::consts::OS,
                std::env::consts::ARCH
            );
            std::process::exit(1);
        }
    };

    // Resolve bundled binaries
    let vm_bin = platform::resolve_binary("victoria-metrics", platform).unwrap_or_else(|| {
        // Fall back to PATH
        "victoria-metrics".into()
    });
    let grafana_bin =
        platform::resolve_binary("grafana-server", platform).unwrap_or_else(|| "grafana".into());
    let gateway_bin = platform::resolve_binary("apple-health-export-gateway", platform)
        .unwrap_or_else(|| "apple-health-export-gateway".into());

    // Build processes
    let vm_args = config::vm_args(&dirs);
    let (grafana_args, grafana_envs) = config::grafana_args(&dirs);
    let gateway_env = config::gateway_env(&dirs);

    let mut supervisor = Supervisor::new();

    // Start order: VM → Grafana → Gateway
    supervisor.add(
        ManagedProcess::new("victoria-metrics", vm_bin)
            .arg(vm_args[0].clone())
            .arg(vm_args[1].clone())
            .arg(vm_args[2].clone())
            .arg(vm_args[3].clone()),
    );

    supervisor.add(
        ManagedProcess::new("grafana", grafana_bin)
            .args(&grafana_args)
            .envs(&grafana_envs),
    );

    supervisor.add(ManagedProcess::new("gateway", gateway_bin).envs(&gateway_env));

    // Start all
    if let Err(e) = supervisor.start_all().await {
        error!("Failed to start services: {e}");
        supervisor.stop_all().await;
        std::process::exit(1);
    }

    info!("All services started. Press Ctrl+C to stop.");
    info!("  Victoria Metrics: http://localhost:8428");
    info!("  Grafana:          http://localhost:3000 (admin/admin)");
    info!("  Gateway:          port 50051 (gRPC)");

    // Wait for shutdown signal
    tokio::signal::ctrl_c().await.ok();
    info!("Shutdown signal received, stopping services...");

    supervisor.stop_all().await;
    info!("All services stopped.");
}

async fn cmd_stop() {
    info!("Stopping Apple Health Export services...");
    // Read PID files from data dir and kill

    // Simple approach: pkill by process group or name
    for name in &["apple-health-export-gateway", "grafana", "victoria-metrics"] {
        let _ = std::process::Command::new("pkill")
            .args(["-f", name])
            .output();
    }
    info!("Stop signal sent to all services.");
}

fn cmd_status() {
    let running = |name: &str| -> bool {
        std::process::Command::new("pgrep")
            .args(["-f", name])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    };

    println!("Service                  Status");
    println!("----------------------------------------");
    for (name, label) in &[
        ("victoria-metrics", "Victoria Metrics"),
        ("grafana", "Grafana"),
        ("apple-health-export-gateway", "Gateway"),
    ] {
        let status = if running(name) { "Running" } else { "Stopped" };
        println!("  {:<22} {}", label, status);
    }
}

fn cmd_setup() {
    info!("Setting up Apple Health Export data directories...");
    match config::AppDirs::create() {
        Ok(dirs) => {
            info!("Data directory: {:?}", dirs.root);
            if let Err(e) = dirs.write_provisioning_files() {
                error!("Failed to write provisioning files: {e}");
                std::process::exit(1);
            }
            info!("Setup complete.");
            info!("Run 'apple-health-export start' to start all services.");
        }
        Err(e) => {
            error!("Setup failed: {e}");
            std::process::exit(1);
        }
    }
}
