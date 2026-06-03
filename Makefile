.PHONY: start proto-swift dashboards build-ios lint-rs test-rs build-rs docker-up docker-down docker-logs clean

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
	cd gateway-rs && cargo fmt --all -- --check
	cd gateway-rs && cargo clippy --all-targets -- -D warnings

test-rs:
	cd gateway-rs && cargo test --lib

build-rs:
	cd gateway-rs && cargo build --release

docker-up:
	./scripts/start.sh

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f gateway

clean:
	rm -f /tmp/test_*.db
	cd gateway-rs && cargo clean 2>/dev/null || true
