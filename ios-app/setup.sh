#!/bin/bash
set -e

echo "=== Apple Health Export - iOS App Setup ==="
echo ""
echo "This script sets up the Xcode project for the iOS Health Export app."
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check for Xcode
if ! command -v xcodebuild &> /dev/null; then
    echo "ERROR: Xcode is not installed. Please install Xcode from the App Store."
    exit 1
fi

# Check for XcodeGen
if ! command -v xcodegen &> /dev/null; then
    echo "Installing XcodeGen via Homebrew..."
    brew install xcodegen
fi

# Generate Xcode project from project.yml
echo "Generating Xcode project..."
xcodegen generate

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Open HealthExporter.xcodeproj in Xcode"
echo "2. Select your team in Signing & Capabilities"
echo "3. Connect your iPhone"
echo "4. Build and run (⌘R)"
echo "5. Grant Health access when prompted"
echo "6. Enter your server IP address and tap Sync"
echo ""
echo "Make sure the gRPC gateway and Victoria Metrics are running:"
echo "  cd .. && ./scripts/start.sh"
