use std::path::{Path, PathBuf};
use tracing::{info, warn};

const DATA_DIR: &str = "apple-health-export";
const VM_PORT: &str = "8428";
const GRAFANA_PORT: &str = "3000";
const GRPC_PORT: &str = "50051";

pub struct AppDirs {
    pub root: PathBuf,
    pub bin: PathBuf,
    pub vm_data: PathBuf,
    pub grafana_data: PathBuf,
    pub grafana_provisioning: PathBuf,
    pub logs: PathBuf,
    pub db: PathBuf,
}

impl AppDirs {
    pub fn create() -> Result<Self, String> {
        let root = dirs_data_dir()
            .ok_or_else(|| "Cannot determine data directory".to_string())?
            .join(DATA_DIR);

        let dirs = AppDirs {
            bin: root.join("bin"),
            vm_data: root.join("data").join("victoria-metrics"),
            grafana_data: root.join("data").join("grafana"),
            grafana_provisioning: root.join("grafana-conf").join("provisioning"),
            logs: root.join("logs"),
            db: root.join("data").join("checkpoints.db"),
            root,
        };

        for dir in [
            &dirs.bin,
            &dirs.vm_data,
            &dirs.grafana_data,
            &dirs.grafana_provisioning,
            &dirs.grafana_provisioning.join("datasources"),
            &dirs.grafana_provisioning.join("dashboards"),
            &dirs.logs,
        ] {
            std::fs::create_dir_all(dir)
                .map_err(|e| format!("Failed to create directory {:?}: {}", dir, e))?;
        }

        info!("Data directory: {:?}", dirs.root);
        Ok(dirs)
    }

    pub fn write_provisioning_files(&self) -> Result<(), String> {
        // Datasource config
        let ds_path = self
            .grafana_provisioning
            .join("datasources")
            .join("datasource.yml");
        let ds_content = format!(
            r#"apiVersion: 1

deleteDatasources:
  - name: Victoria Metrics
    orgId: 1

datasources:
  - name: Victoria Metrics
    uid: victoriametrics
    orgId: 1
    type: prometheus
    access: proxy
    url: http://localhost:{VM_PORT}
    isDefault: true
    editable: true
"#
        );
        std::fs::write(&ds_path, &ds_content)
            .map_err(|e| format!("Failed to write datasource config: {e}"))?;

        // Dashboard provider config
        let provider_path = self
            .grafana_provisioning
            .join("dashboards")
            .join("provider.yml");
        let provider_path_str = self
            .grafana_provisioning
            .join("dashboards")
            .to_string_lossy()
            .to_string();
        let provider_content = format!(
            r#"apiVersion: 1

providers:
  - name: Apple Health
    orgId: 1
    folder: Apple Health
    type: file
    disableDeletion: false
    editable: true
    options:
      path: {}
      foldersFromFilesStructure: false
"#,
            provider_path_str
        );
        std::fs::write(&provider_path, &provider_content)
            .map_err(|e| format!("Failed to write dashboard provider config: {e}"))?;

        // Try to copy dashboards from bundle provisioning dir
        let bundled_dashboards = crate::platform::provisioning_dir().map(|p| p.join("dashboards"));
        if let Some(src) = bundled_dashboards {
            if src.exists() {
                let dst = self.grafana_provisioning.join("dashboards");
                if let Err(e) = copy_dir_recursive(&src, &dst) {
                    warn!("Failed to copy bundled dashboards: {e}");
                } else {
                    info!("Copied dashboards from {:?} to {:?}", src, dst);
                }
            }
        }

        info!(
            "Grafana provisioning files written to {:?}",
            self.grafana_provisioning
        );
        Ok(())
    }
}

fn copy_dir_recursive(src: &Path, dst: &Path) -> std::io::Result<()> {
    if !dst.exists() {
        std::fs::create_dir_all(dst)?;
    }
    for entry in std::fs::read_dir(src)? {
        let entry = entry?;
        let file_type = entry.file_type()?;
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());
        if file_type.is_dir() {
            copy_dir_recursive(&src_path, &dst_path)?;
        } else {
            std::fs::copy(&src_path, &dst_path)?;
        }
    }
    Ok(())
}

fn dirs_data_dir() -> Option<PathBuf> {
    #[cfg(target_os = "macos")]
    {
        // Use ~/Library/Application Support on macOS
        std::env::var("HOME").ok().map(|home| {
            PathBuf::from(home)
                .join("Library")
                .join("Application Support")
        })
    }
    #[cfg(target_os = "linux")]
    {
        // Use XDG_DATA_HOME or ~/.local/share on Linux
        std::env::var("XDG_DATA_HOME")
            .ok()
            .map(PathBuf::from)
            .or_else(|| {
                std::env::var("HOME")
                    .ok()
                    .map(|home| PathBuf::from(home).join(".local").join("share"))
            })
    }
    #[cfg(not(any(target_os = "macos", target_os = "linux")))]
    {
        None
    }
}

pub fn vm_args(dirs: &AppDirs) -> Vec<String> {
    vec![
        format!("-storageDataPath={}", dirs.vm_data.display()),
        "-httpListenAddr=:8428".to_string(),
        "-retentionPeriod=10y".to_string(),
        "-dedup.minScrapeInterval=1ms".to_string(),
    ]
}

pub fn grafana_args(dirs: &AppDirs) -> (Vec<String>, Vec<(String, String)>) {
    let args = vec![
        "server".to_string(),
        format!("--homepath={}", dirs.root.join("grafana-home").display()),
        format!(
            "--config={}",
            dirs.root.join("grafana-conf").join("grafana.ini").display()
        ),
    ];

    let envs = vec![
        ("GF_SECURITY_ADMIN_USER".to_string(), "admin".to_string()),
        (
            "GF_SECURITY_ADMIN_PASSWORD".to_string(),
            "admin".to_string(),
        ),
        ("GF_AUTH_ANONYMOUS_ENABLED".to_string(), "true".to_string()),
        (
            "GF_AUTH_ANONYMOUS_ORG_ROLE".to_string(),
            "Viewer".to_string(),
        ),
        (
            "GF_PATHS_PROVISIONING".to_string(),
            dirs.grafana_provisioning.to_string_lossy().to_string(),
        ),
        (
            "GF_PATHS_DATA".to_string(),
            dirs.grafana_data.to_string_lossy().to_string(),
        ),
        (
            "GF_PATHS_LOGS".to_string(),
            dirs.logs.to_string_lossy().to_string(),
        ),
        ("GF_SERVER_HTTP_PORT".to_string(), GRAFANA_PORT.to_string()),
    ];

    (args, envs)
}

pub fn gateway_env(dirs: &AppDirs) -> Vec<(String, String)> {
    vec![
        ("GRPC_PORT".to_string(), GRPC_PORT.to_string()),
        ("VM_URL".to_string(), format!("http://localhost:{VM_PORT}")),
        ("DB_PATH".to_string(), dirs.db.to_string_lossy().to_string()),
        ("RUST_LOG".to_string(), "info".to_string()),
    ]
}
