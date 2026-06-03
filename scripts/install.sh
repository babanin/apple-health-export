#!/bin/sh
set -e

REPO="babanin/apple-health-export"
INSTALL_DIR="/opt/apple-health-export"
BIN_DIR="/usr/local/bin"

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$OS-$ARCH" in
    darwin-arm64)  PKG="apple-health-export-macos-aarch64.tar.gz" ;;
    darwin-x86_64) PKG="apple-health-export-macos-x86_64.tar.gz" ;;
    linux-x86_64)  PKG="apple-health-export-linux-x86_64.tar.gz" ;;
    *) echo "Unsupported: $OS-$ARCH"; exit 1 ;;
esac

if [ "$(id -u)" -ne 0 ]; then
    echo "Root required. Run with sudo."
    exit 1
fi

echo "Downloading Apple Health Export for $OS-$ARCH ..."
LATEST=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | grep '"tag_name"' | cut -d'"' -f4)

[ -z "$LATEST" ] && echo "Failed to detect latest version" && exit 1

rm -rf /tmp/apple-health-export-install
mkdir -p /tmp/apple-health-export-install
cd /tmp/apple-health-export-install

curl -fsSL "https://github.com/$REPO/releases/download/$LATEST/$PKG" | tar xz

rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -R apple-health-export/* "$INSTALL_DIR/"

chmod 755 "$INSTALL_DIR/apple-health-export"
for f in "$INSTALL_DIR"/bundled/*/*; do
    [ -f "$f" ] && chmod 755 "$f"
done

rm -f "$BIN_DIR/apple-health-export"
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/apple-health-export" "$BIN_DIR/apple-health-export"

rm -rf /tmp/apple-health-export-install

echo ""
echo "Apple Health Export $LATEST installed"
echo "  $INSTALL_DIR/apple-health-export"
echo "  $BIN_DIR/apple-health-export -> $INSTALL_DIR/apple-health-export"
echo ""
echo "To start: apple-health-export start"
echo "iOS app will auto-discover via mDNS."
