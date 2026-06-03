use std::path::PathBuf;
use std::process::Stdio;
use tokio::process::{Child, Command};
use tracing::{error, info, warn};

#[allow(dead_code)]
pub struct ManagedProcess {
    name: &'static str,
    child: Option<Child>,
    bin_path: PathBuf,
    args: Vec<String>,
    envs: Vec<(String, String)>,
}

impl ManagedProcess {
    pub fn new(name: &'static str, bin_path: PathBuf) -> Self {
        Self {
            name,
            child: None,
            bin_path,
            args: Vec::new(),
            envs: Vec::new(),
        }
    }

    pub fn arg(mut self, arg: impl Into<String>) -> Self {
        self.args.push(arg.into());
        self
    }

    pub fn args(mut self, args: &[String]) -> Self {
        self.args.extend_from_slice(args);
        self
    }

    pub fn env(mut self, key: impl Into<String>, val: impl Into<String>) -> Self {
        self.envs.push((key.into(), val.into()));
        self
    }

    pub fn envs(mut self, envs: &[(String, String)]) -> Self {
        self.envs.extend_from_slice(envs);
        self
    }

    pub async fn start(&mut self) -> Result<(), String> {
        let mut cmd = Command::new(&self.bin_path);
        cmd.args(&self.args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        for (k, v) in &self.envs {
            cmd.env(k, v);
        }

        match cmd.spawn() {
            Ok(child) => {
                info!("Started {} (pid: {})", self.name, child.id().unwrap_or(0));
                self.child = Some(child);
                Ok(())
            }
            Err(e) => {
                let msg = format!("Failed to start {}: {}", self.name, e);
                error!("{msg}");
                Err(msg)
            }
        }
    }

    pub async fn stop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let pid = child.id().unwrap_or(0);
            info!("Stopping {} (pid: {})...", self.name, pid);

            // Send SIGTERM
            let _ = child.start_kill();

            // Wait up to 10 seconds for graceful shutdown
            match tokio::time::timeout(std::time::Duration::from_secs(10), child.wait()).await {
                Ok(Ok(status)) => {
                    info!("{} stopped with status: {}", self.name, status);
                }
                Ok(Err(e)) => {
                    warn!("{} wait error: {}", self.name, e);
                }
                Err(_) => {
                    warn!("{} did not stop in 10s, killing", self.name);
                    let _ = child.kill().await;
                }
            }
        }
    }

    pub fn pid(&self) -> Option<u32> {
        self.child.as_ref().and_then(|c| c.id())
    }

    pub fn is_running(&self) -> bool {
        self.child.is_some()
    }
}

pub struct Supervisor {
    processes: Vec<ManagedProcess>,
}

impl Supervisor {
    pub fn new() -> Self {
        Self {
            processes: Vec::new(),
        }
    }

    pub fn add(&mut self, process: ManagedProcess) -> &mut Self {
        self.processes.push(process);
        self
    }

    pub async fn start_all(&mut self) -> Result<(), String> {
        for process in &mut self.processes {
            process.start().await?;
        }
        Ok(())
    }

    pub async fn stop_all(&mut self) {
        // Stop in reverse order (gateway first, then grafana, then VM)
        for process in self.processes.iter_mut().rev() {
            process.stop().await;
        }
    }

    pub fn status(&self) -> Vec<(&'static str, Option<u32>)> {
        self.processes.iter().map(|p| (p.name, p.pid())).collect()
    }
}
