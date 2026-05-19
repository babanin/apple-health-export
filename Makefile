.PHONY: start proto dashboards test test-unit test-integration test-e2e test-docker test-all build-ios lint clean

PROTO_DIR = proto
GATEWAY_DIR = gateway
IOS_DIR = ios-app/HealthExporter

proto:
	python -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=$(GATEWAY_DIR) \
		--grpc_python_out=$(GATEWAY_DIR) \
		$(PROTO_DIR)/health_export.proto

start:
	./scripts/start.sh

proto-swift:
	protoc \
		-I$(PROTO_DIR) \
		--swift_out=$(IOS_DIR)/Generated \
		--grpc-swift_out=$(IOS_DIR)/Generated \
		$(PROTO_DIR)/health_export.proto

dashboards:
	python3 scripts/generate_dashboards.py

install:
	pip install -r gateway/requirements.txt

test: test-unit

test-unit:
	pytest tests/test_checkpoint_store.py tests/test_proto_contract.py -v

test-integration:
	pytest tests/test_grpc_gateway.py tests/test_vm_writer.py tests/test_end_to_end.py -v -m integration

test-e2e:
	docker compose up -d --build
	sleep 15
	pytest tests/test_end_to_end.py -v
	pytest tests/test_grpc_gateway.py tests/test_vm_writer.py -v

test-docker:
	RUN_DOCKER_TESTS=1 pytest tests/test_docker_stack.py tests/test_grafana_provisioning.py -v

test-all:
	pytest tests/ -v --tb=short

build-ios:
	cd ios-app && ./setup.sh
	@echo "Open ios-app/HealthExporter.xcodeproj in Xcode, select your signing team, then build on a physical iPhone."

lint:
	ruff check gateway/ tests/
	flake8 gateway/ tests/

docker-up:
	./scripts/start.sh

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f gateway

clean:
	rm -f $(GATEWAY_DIR)/health_export_pb2.py $(GATEWAY_DIR)/health_export_pb2_grpc.py
	rm -f /tmp/test_*.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
