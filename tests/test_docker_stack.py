import os
import subprocess
import time
import sys
import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_TESTS") != "1",
    reason="Docker tests require RUN_DOCKER_TESTS=1"
)
class TestDockerStack:
    @pytest.fixture(scope="class", autouse=True)
    def docker_stack(self):
        compose_file = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "up", "-d", "--build"],
            check=True,
            capture_output=True,
        )
        time.sleep(15)

        for _ in range(60):
            try:
                r = requests.get("http://localhost:8428/health", timeout=2)
                if r.status_code == 200:
                    break
            except requests.ConnectionError:
                time.sleep(2)

        yield

        subprocess.run(
            ["docker", "compose", "-f", compose_file, "down", "-v"],
            check=True,
            capture_output=True,
        )

    def test_all_services_healthy(self):
        r = requests.get("http://localhost:8428/health", timeout=5)
        assert r.status_code == 200

        r = requests.get("http://localhost:3000/api/health", timeout=5)
        assert r.status_code == 200

    def test_victoriametrics_reachable(self):
        r = requests.get("http://localhost:8428/health", timeout=5)
        assert r.status_code == 200

    def test_grafana_reachable(self):
        r = requests.get("http://localhost:3000/api/health", timeout=5)
        assert r.status_code == 200

    def test_gateway_grpc_reachable(self):
        import grpc
        import sys

        gateway_path = os.path.join(os.path.dirname(__file__), "..", "gateway")
        sys.path.insert(0, gateway_path)
        import health_export_pb2_grpc

        try:
            channel = grpc.insecure_channel("localhost:50051")
            stub = health_export_pb2_grpc.HealthExportServiceStub(channel)

            import health_export_pb2
            request = health_export_pb2.CheckpointRequest(device_id="docker_test")
            response = stub.GetCheckpoint(request)
            assert response is not None
            channel.close()
        except grpc.RpcError:
            pytest.fail("gRPC gateway not reachable")

    def test_gateway_to_vm_network(self):
        import grpc
        import sys

        gateway_path = os.path.join(os.path.dirname(__file__), "..", "gateway")
        sys.path.insert(0, gateway_path)
        import health_export_pb2
        import health_export_pb2_grpc

        channel = grpc.insecure_channel("localhost:50051")
        stub = health_export_pb2_grpc.HealthExportServiceStub(channel)

        sample = health_export_pb2.HealthSample(
            metric_name="apple_health_heart_rate_bpm",
            timestamp_ms=1700080000000,
            value=72.0,
            source="docker_test",
        )
        request = health_export_pb2.SyncRequest(
            device_id="docker_test_device",
            batch_id="docker_test_batch",
            samples=[sample],
        )
        response = stub.SyncMetrics(request)
        assert response.success

        time.sleep(2)

        r = requests.get(
            "http://localhost:8428/api/v1/export",
            params={"match[]": "apple_health_heart_rate_bpm"},
            timeout=5,
        )
        assert r.status_code == 200
        channel.close()

    def test_grafana_datasource_configured(self):
        session = requests.Session()
        session.auth = ("admin", "admin")

        r = session.get("http://localhost:3000/api/datasources", timeout=5)
        assert r.status_code == 200
        datasources = r.json()
        vm_datasources = [ds for ds in datasources if ds.get("type") == "prometheus"]
        assert len(vm_datasources) >= 1

    def test_volumes_persist_after_restart(self):
        r = requests.get("http://localhost:8428/health", timeout=5)
        assert r.status_code == 200

        import grpc
        import health_export_pb2
        import health_export_pb2_grpc

        channel = grpc.insecure_channel("localhost:50051")
        stub = health_export_pb2_grpc.HealthExportServiceStub(channel)

        sample = health_export_pb2.HealthSample(
            metric_name="apple_health_steps_total",
            timestamp_ms=1700090000000,
            value=1000.0,
            source="persist_test",
        )
        stub.SyncMetrics(health_export_pb2.SyncRequest(
            device_id="persist_device",
            batch_id="persist_batch",
            samples=[sample],
        ))

        time.sleep(2)

        r = requests.get(
            "http://localhost:8428/api/v1/export",
            params={"match[]": "apple_health_steps_total"},
            timeout=5,
        )
        data_before = r.json()

        subprocess.run(
            ["docker", "compose", "-f", os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml"), "restart"],
            check=True,
            capture_output=True,
        )
        time.sleep(15)

        r = requests.get("http://localhost:8428/health", timeout=5)
        assert r.status_code == 200

        r = requests.get(
            "http://localhost:8428/api/v1/export",
            params={"match[]": "apple_health_steps_total"},
            timeout=5,
        )
        data_after = r.json()
        assert len(data_after) >= len(data_before)

        channel.close()