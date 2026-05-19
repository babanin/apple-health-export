# Apple Health Export

Sync Apple Health data from your iPhone to a local Grafana dashboard.

The project runs a local Docker stack on your Mac:

- Python gRPC gateway on port `50051`
- Victoria Metrics on port `8428`
- Grafana on port `3000`

The iOS app reads HealthKit samples, sends them to the gateway over your local Wi-Fi network, and uses checkpoints so later syncs only send new data.

## Requirements

- macOS with Docker Desktop
- Xcode 16 or newer
- iPhone running iOS 18 or newer
- iPhone and Mac on the same Wi-Fi network
- Homebrew, used by `ios-app/setup.sh` to install XcodeGen if needed
- Apple Developer Program membership for real HealthKit data

You can still test the full pipeline with demo data if HealthKit is not available or authorization is denied.

## Quick Start

### 1. Start the Local Stack

```bash
git clone <your-fork-or-this-repo-url>
cd apple-health-export
./scripts/start.sh
```

The script starts Docker Compose and prints the settings to enter in the iPhone app, for example:

```text
Grafana:
  URL:      http://localhost:3000
  Login:    admin / admin

iPhone app Server settings:
  Host:     192.168.1.25
  Port:     50051
  Address:  192.168.1.25:50051
```

Grafana is provisioned automatically with the Victoria Metrics datasource and the Apple Health dashboards.

You can also start the stack through `make`:

```bash
make start
```

### 2. Build the iPhone App

```bash
cd ios-app
./setup.sh
open HealthExporter.xcodeproj
```

In Xcode:

1. Select the `HealthExporter` target.
2. Open **Signing & Capabilities**.
3. Select your Apple developer team.
4. Change the bundle identifier if Xcode reports that it is already taken.
5. Connect your iPhone and run the app.

For real HealthKit data, make sure the HealthKit capability is present in **Signing & Capabilities**. The project already includes the HealthKit usage descriptions and entitlement.

### 3. Connect and Sync

In the iPhone app:

1. Enter the host and port printed by `./scripts/start.sh` in **Server**.
2. Do not use `localhost` on the phone; it points at the phone, not your Mac.
3. Tap **Ping**.
4. Tap **Authorize Health Access** and allow the categories you want to export.
5. Tap **Sync Now**.

Then open Grafana at `http://localhost:3000` and use the dashboards in the `Apple Health` folder.

## Troubleshooting

**Ping fails from the iPhone**

- Confirm the Mac and iPhone are on the same Wi-Fi network.
- Use the Mac LAN IP address, not `localhost`.
- Allow incoming connections if macOS Firewall prompts you.
- Check that the gateway is running:

```bash
docker compose ps
docker compose logs -f gateway
```

**Grafana is empty**

- Run a sync from the iPhone app first.
- Check the app log panel for rejected Health permissions or gateway errors.
- In Grafana, widen the time range to `Last 30 days` or `Last 1 year`.

**HealthKit data does not appear**

- Real HealthKit export requires a physical iPhone.
- Health permissions are per metric; review access in the Apple Health app or iOS Settings.
- If HealthKit is unavailable or denied, the app switches to demo data so you can still validate the backend.

**You changed dashboards but Grafana did not update**

Grafana only reloads provisioned dashboards on startup:

```bash
make dashboards
docker compose restart grafana
```

## Useful Commands

```bash
# Start or rebuild the stack
make start

# Follow gateway logs
make docker-logs

# Stop and remove stack volumes
make docker-down

# Regenerate curated Grafana dashboards
make dashboards

# Regenerate Python protobuf stubs
make proto

# Regenerate Swift protobuf stubs
make proto-swift

# Run unit tests that do not require Docker
make test-unit

# Run integration tests
make test-integration
```

## What Gets Exported

The app exports HealthKit quantity and category metrics using Prometheus-style names with the `apple_health_` prefix, for example:

- `apple_health_heart_rate_bpm`
- `apple_health_steps_total`
- `apple_health_sleep_stage`
- `apple_health_vo2_max_ml_kg_min`
- `apple_health_blood_glucose_mg_dl`

See [`HKMetricMapping.swift`](ios-app/HealthExporter/Models/HKMetricMapping.swift) for the full mapping.

## Architecture

```text
iPhone HealthKit
  -> HealthKitManager fetches samples
  -> iOS app sends gRPC batches over Wi-Fi
  -> Python gateway receives SyncMetrics requests
  -> gateway writes NDJSON samples to Victoria Metrics
  -> Grafana reads Victoria Metrics dashboards
```

Checkpoints are stored on both sides:

- iPhone: `UserDefaults`
- gateway: SQLite in the Docker volume mounted at `/data/checkpoints.db`

On each sync, the app sends its last known per-metric timestamps. The gateway merges them with server-side checkpoints and returns the latest values, so future syncs can skip previously exported samples.

## Project Layout

```text
apple-health-export/
├── docker-compose.yml
├── Makefile
├── proto/
│   └── health_export.proto
├── gateway/
│   ├── server.py
│   ├── vm_writer.py
│   └── checkpoint_store.py
├── ios-app/
│   ├── setup.sh
│   ├── project.yml
│   └── HealthExporter/
├── scripts/
│   └── generate_dashboards.py
├── dashboards/
└── grafana/provisioning/
```

## Development Notes

- Generated Swift files live in `ios-app/HealthExporter/Generated/`; regenerate them with `make proto-swift`.
- Generated Python stubs live in `gateway/`; regenerate them with `make proto`.
- Curated dashboard JSON is generated by `scripts/generate_dashboards.py`; run `make dashboards` after changing it.
- The provisioned Victoria Metrics datasource UID must stay `victoriametrics` because the dashboards reference that UID directly.
- After Swift changes, regenerate and build the Xcode project:

```bash
cd ios-app
xcodegen generate
xcodebuild -scheme HealthExporter -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 17,OS=latest' build
```
