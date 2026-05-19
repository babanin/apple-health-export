import os
import subprocess
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))


@pytest.mark.integration
class TestProtoContract:
    def test_python_stub_generation(self):
        proto_path = os.path.join(os.path.dirname(__file__), "..", "proto", "health_export.proto")
        out_dir = os.path.join(os.path.dirname(__file__), "..", "gateway")

        result = subprocess.run(
            [
                sys.executable, "-m", "grpc_tools.protoc",
                f"-I{os.path.dirname(proto_path)}",
                f"--python_out={out_dir}",
                f"--grpc_python_out={out_dir}",
                os.path.basename(proto_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"protoc failed: {result.stderr}"

        assert os.path.exists(os.path.join(out_dir, "health_export_pb2.py"))
        assert os.path.exists(os.path.join(out_dir, "health_export_pb2_grpc.py"))

    def test_field_types(self):
        import health_export_pb2

        sample = health_export_pb2.HealthSample()
        sample.metric_name = "test_metric"
        sample.timestamp_ms = 1700000000000
        sample.value = 72.5
        sample.unit = "bpm"
        sample.source = "Apple Watch"
        sample.labels["key1"] = "value1"

        assert isinstance(sample.metric_name, str)
        assert isinstance(sample.timestamp_ms, int)
        assert isinstance(sample.value, float)
        assert isinstance(sample.unit, str)
        assert isinstance(sample.source, str)
        assert len(sample.labels) == 1
        assert sample.labels["key1"] == "value1"

    def test_sync_request_structure(self):
        import health_export_pb2

        request = health_export_pb2.SyncRequest()
        request.device_id = "test_device"
        request.batch_id = "batch_1"
        request.is_historical_export = True

        sample = request.samples.add()
        sample.metric_name = "test"
        sample.timestamp_ms = 1700000000000
        sample.value = 1.0

        request.checkpoint["metric_1"] = 1700000000000

        assert request.device_id == "test_device"
        assert len(request.samples) == 1
        assert request.checkpoint["metric_1"] == 1700000000000
        assert request.is_historical_export is True

    def test_sync_response_structure(self):
        import health_export_pb2

        response = health_export_pb2.SyncResponse()
        response.acknowledged_count = 42
        response.success = True
        response.error_message = ""
        response.updated_checkpoint["steps"] = 1700000000000

        assert response.acknowledged_count == 42
        assert response.success is True
        assert response.updated_checkpoint["steps"] == 1700000000000

    def test_checkpoint_request_response(self):
        import health_export_pb2

        request = health_export_pb2.CheckpointRequest()
        request.device_id = "device_1"

        response = health_export_pb2.CheckpointResponse()
        response.checkpoint["steps"] = 1700000000000
        response.checkpoint["hr"] = 1700000001000

        assert request.device_id == "device_1"
        assert len(response.checkpoint) == 2

    def test_max_message_size_config(self):
        import grpc
        from concurrent import futures

        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=1),
            options=[
                ("grpc.max_send_message_length", 100 * 1024 * 1024),
                ("grpc.max_receive_message_length", 100 * 1024 * 1024),
            ],
        )
        port = server.add_insecure_port("[::]:0")
        assert port > 0
        server.stop(grace=0)

    def test_all_metric_names_serializable(self):
        import json
        import health_export_pb2

        fixture_path = os.path.join(
            os.path.dirname(__file__), "fixtures", "all_metric_types.json"
        )
        with open(fixture_path) as f:
            all_types = json.load(f)["all_metric_types"]

        samples = []
        for hk_type, data in all_types.items():
            sample = health_export_pb2.HealthSample()
            sample.metric_name = data["metric_name"]
            sample.timestamp_ms = 1700000000000
            sample.value = data["value"]
            sample.unit = data["unit"]
            sample.source = "test"
            samples.append(sample)

        request = health_export_pb2.SyncRequest()
        request.device_id = "test"
        request.samples.extend(samples)

        serialized = request.SerializeToString()
        deserialized = health_export_pb2.SyncRequest()
        deserialized.ParseFromString(serialized)

        assert len(deserialized.samples) == len(all_types)
        for original, parsed in zip(samples, deserialized.samples):
            assert original.metric_name == parsed.metric_name
            assert original.value == parsed.value