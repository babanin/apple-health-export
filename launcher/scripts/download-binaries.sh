#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUNDLED_DIR="$ROOT_DIR/bundled"

VM_VERSION="1.108.0"
GRAFANA_VERSION="13.0.2"

ARCH_MAP_AMD64="macos-x86_64"
ARCH_MAP_ARM64="macos-aarch64"

download_vm() {
    local goarch="$1"
    local dirname_var="ARCH_MAP_${goarch}"
    local dirname="${!dirname_var}"
    local dir="$BUNDLED_DIR/$dirname"
    mkdir -p "$dir"

    if [ -f "$dir/victoria-metrics" ]; then
        echo "  victoria-metrics ($goarch) already exists, skipping"
        return
    fi

    echo "  Downloading Victoria Metrics $VM_VERSION ($goarch)..."
    local url="https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/v${VM_VERSION}/victoria-metrics-darwin-${goarch}-v${VM_VERSION}.tar.gz"
    curl -fsSL "$url" -o /tmp/vm-${goarch}.tar.gz
    tar xzf /tmp/vm-${goarch}.tar.gz -C "$dir"
    chmod +x "$dir/victoria-metrics"
    rm /tmp/vm-${goarch}.tar.gz
    echo "  victoria-metrics ($dirname): $(file "$dir/victoria-metrics")"
}

download_grafana() {
    local goarch="$1"
    local dirname_var="ARCH_MAP_${goarch}"
    local dirname="${!dirname_var}"
    local dir="$BUNDLED_DIR/$dirname"
    mkdir -p "$dir"

    if [ -f "$dir/grafana-server" ]; then
        echo "  grafana-server ($goarch) already exists, skipping"
        return
    fi

    echo "  Downloading Grafana $GRAFANA_VERSION ($goarch)..."
    local url="https://dl.grafana.com/oss/release/grafana-${GRAFANA_VERSION}.darwin-${goarch}.tar.gz"
    curl -fsSL "$url" -o /tmp/grafana-${goarch}.tar.gz
    tar xzf /tmp/grafana-${goarch}.tar.gz -C /tmp
    cp "/tmp/grafana-${GRAFANA_VERSION}/bin/grafana-server" "$dir/grafana-server"
    chmod +x "$dir/grafana-server"
    rm -rf "/tmp/grafana-${GRAFANA_VERSION}" /tmp/grafana-${goarch}.tar.gz
    echo "  grafana-server ($dirname): $(file "$dir/grafana-server")"
}

echo "Downloading bundled binaries..."
echo

echo "Victoria Metrics:"
download_vm "amd64"
download_vm "arm64"

echo
echo "Grafana:"
download_grafana "amd64"
download_grafana "arm64"

echo
echo "All binaries downloaded to $BUNDLED_DIR"
ls -lhR "$BUNDLED_DIR"
