use std::path::PathBuf;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Platform {
    MacOSX86_64,
    MacOSAarch64,
    LinuxX86_64,
}

impl Platform {
    pub fn current() -> Option<Self> {
        let os = std::env::consts::OS;
        let arch = std::env::consts::ARCH;
        match (os, arch) {
            ("macos", "x86_64") => Some(Platform::MacOSX86_64),
            ("macos", "aarch64") => Some(Platform::MacOSAarch64),
            ("linux", "x86_64") => Some(Platform::LinuxX86_64),
            _ => None,
        }
    }

    pub fn dir_name(&self) -> &'static str {
        match self {
            Platform::MacOSX86_64 => "macos-x86_64",
            Platform::MacOSAarch64 => "macos-aarch64",
            Platform::LinuxX86_64 => "linux-x86_64",
        }
    }
}

pub fn exe_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    exe.parent().map(|p| p.to_path_buf())
}

pub fn bundled_bin_dir(platform: Platform) -> Option<PathBuf> {
    let base = exe_dir()?;
    Some(base.join("bundled").join(platform.dir_name()))
}

pub fn resolve_binary(name: &str, platform: Platform) -> Option<PathBuf> {
    let dir = bundled_bin_dir(platform)?;
    let path = dir.join(name);
    if path.exists() {
        Some(path)
    } else {
        None
    }
}

pub fn provisioning_dir() -> Option<PathBuf> {
    let base = exe_dir()?;
    let dir = base.join("provisioning");
    if dir.exists() {
        Some(dir)
    } else {
        None
    }
}
