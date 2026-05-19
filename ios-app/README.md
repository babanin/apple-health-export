# HealthExporter iOS App

This app runs on a physical iPhone, reads Apple Health data through HealthKit, and sends it to the local gateway over Wi-Fi.

## Setup

```bash
cd ios-app
./setup.sh
open HealthExporter.xcodeproj
```

In Xcode:

1. Select the `HealthExporter` target.
2. Select your team in **Signing & Capabilities**.
3. Change the bundle identifier if needed.
4. Connect your iPhone.
5. Build and run.

The app requires iOS 18 or newer.

## HealthKit

For real health data:

1. Use a physical iPhone.
2. Sign with an Apple Developer Program team.
3. Keep the HealthKit capability enabled.
4. Tap **Authorize Health Access** in the app and approve the metrics you want to export.

If HealthKit is unavailable or authorization is denied, the app can still send demo data through the same gRPC pipeline.

## Connect to the Gateway

Start the backend from the repo root:

```bash
./scripts/start.sh
```

Enter the host and port printed by the script in the app's **Server** section. Use **Ping** before syncing.

Do not use `localhost` on the phone; it points at the phone, not your Mac.

## Regenerate the Xcode Project

If `project.yml` changes:

```bash
xcodegen generate
```
