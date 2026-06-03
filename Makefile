.PHONY: start proto-swift dashboards build-ios lint-rs test-rs build-rs bundle-mac native-up native-down docker-up docker-down docker-logs clean

PROTO_DIR = proto
IOS_DIR = ios-app/HealthExporter

proto-swift:
	protoc \
		-I$(PROTO_DIR) \
		--swift_out=$(IOS_DIR)/Generated \
		--grpc-swift_out=$(IOS_DIR)/Generated \
		$(PROTO_DIR)/health_export.proto

start:
	./scripts/start.sh

dashboards:
	python3 scripts/generate_dashboards.py

build-ios:
	cd ios-app && ./setup.sh
	@echo "Open ios-app/HealthExporter.xcodeproj in Xcode, select your signing team, then build on a physical iPhone."

lint-rs:
	cargo fmt --all -- --check
	cargo clippy --all-targets -- -D warnings

test-rs:
	cd gateway-rs && cargo test --lib

build-rs:
	cargo build --release

# Native deployment (all-in-one binary)
bundle-mac:
	./launcher/scripts/download-binaries.sh
	cargo build --release
	@echo ""
	@echo "Bundle created:"
	@echo "  launcher: target/release/apple-health-export"
	@echo "  gateway:  target/release/apple-health-export-gateway"
	@echo "  bundled:  See bundeled/ directory"

native-up:
	target/release/apple-health-export setup
	target/release/apple-health-export start

native-down:
	target/release/apple-health-export stop

# Docker deployment (alternative)
docker-up:
	./scripts/start.sh

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f gateway

clean:
	rm -f /tmp/test_*.db
	cargo clean 2>/dev/null || true
