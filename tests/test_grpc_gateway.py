import json
import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

import health_export_pb2


@pytest.mark.integration
class TestGRPCGateway:
    def test_sync_single_metric(self, grpc_stub, vm_api_url):
        sample = health_export_pb2.HealthSample(
            metric_name="apple_health_heart_rate_bpm",
            timestamp_ms=1700000000000,
            value=72.0,
            unit="bpm",
            source="Apple Watch",
            labels={"device": "test"},
        )
        request = health_export_pb2.SyncRequest(
            device_id="test_device",
            batch_id="batch_1",
            samples=[sample],
            is_historical_export=True,
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success
        assert response.acknowledged_count == 1

    def test_sync_batch_metrics(self, grpc_stub, sample_samples):
        request = health_export_pb2.SyncRequest(
            device_id="test_device",
            batch_id="batch_2",
            samples=sample_samples,
            is_historical_export=True,
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success
        assert response.acknowledged_count == len(sample_samples)

    def test_sync_multiple_metric_types(self, grpc_stub):
        samples = [
            health_export_pb2.HealthSample(
                metric_name=f"apple_health_metric_{i}",
                timestamp_ms=1700000000000 + i * 1000,
                value=float(i),
                unit="count",
                source="test",
            )
            for i in range(10)
        ]
        request = health_export_pb2.SyncRequest(
            device_id="test_device_multi",
            batch_id="batch_3",
            samples=samples,
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success
        assert response.acknowledged_count == 10

    def test_sync_with_labels(self, grpc_stub):
        sample = health_export_pb2.HealthSample(
            metric_name="apple_health_heart_rate_bpm",
            timestamp_ms=1700000100000,
            value=75.0,
            unit="bpm",
            source="Apple Watch",
            labels={"workout_type": "running", "device": "Apple Watch 9"},
        )
        request = health_export_pb2.SyncRequest(
            device_id="test_device_labels",
            batch_id="batch_labels",
            samples=[sample],
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success

    def test_sync_empty_batch(self, grpc_stub):
        request = health_export_pb2.SyncRequest(
            device_id="test_device",
            batch_id="batch_empty",
            samples=[],
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success
        assert response.acknowledged_count == 0

    def test_checkpoint_returned_on_sync(self, grpc_stub):
        ts = 1700000500000
        sample = health_export_pb2.HealthSample(
            metric_name="apple_health_steps_total",
            timestamp_ms=ts,
            value=500.0,
            unit="count",
            source="iPhone",
        )
        request = health_export_pb2.SyncRequest(
            device_id="test_device_checkpoint",
            batch_id="batch_cp",
            samples=[sample],
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success
        assert "apple_health_steps_total" in response.updated_checkpoint
        assert response.updated_checkpoint["apple_health_steps_total"] == ts

    def test_checkpoint_fidelity_across_syncs(self, grpc_stub):
        device_id = "test_device_fidelity"
        ts1 = 1700001000000
        ts2 = 1700002000000

        sample1 = health_export_pb2.HealthSample(
            metric_name="apple_health_heart_rate_bpm",
            timestamp_ms=ts1,
            value=70.0,
            source="test",
        )
        request1 = health_export_pb2.SyncRequest(
            device_id=device_id,
            batch_id="fidelity_1",
            samples=[sample1],
        )
        response1 = grpc_stub.SyncMetrics(request1)
        assert response1.success

        sample2 = health_export_pb2.HealthSample(
            metric_name="apple_health_heart_rate_bpm",
            timestamp_ms=ts2,
            value=75.0,
            source="test",
        )
        request2 = health_export_pb2.SyncRequest(
            device_id=device_id,
            batch_id="fidelity_2",
            samples=[sample2],
        )
        response2 = grpc_stub.SyncMetrics(request2)
        assert response2.success
        assert response2.updated_checkpoint["apple_health_heart_rate_bpm"] == ts2

    def test_concurrent_sync_requests(self, grpc_stub):
        import threading

        results = []
        errors = []

        def sync_worker(device_suffix):
            try:
                sample = health_export_pb2.HealthSample(
                    metric_name="apple_health_heart_rate_bpm",
                    timestamp_ms=1700003000000 + device_suffix * 1000,
                    value=60.0 + device_suffix,
                    source=f"device_{device_suffix}",
                )
                request = health_export_pb2.SyncRequest(
                    device_id=f"concurrent_device_{device_suffix}",
                    batch_id=f"concurrent_batch_{device_suffix}",
                    samples=[sample],
                )
                response = grpc_stub.SyncMetrics(request)
                results.append((device_suffix, response.success, response.acknowledged_count))
            except Exception as e:
                errors.append((device_suffix, str(e)))

        threads = []
        for i in range(5):
            t = threading.Thread(target=sync_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 5
        for _, success, count in results:
            assert success
            assert count == 1

    def test_sync_with_future_timestamps(self, grpc_stub):
        future_ts = 2700000000000
        sample = health_export_pb2.HealthSample(
            metric_name="apple_health_heart_rate_bpm",
            timestamp_ms=future_ts,
            value=80.0,
            source="test",
        )
        request = health_export_pb2.SyncRequest(
            device_id="test_future",
            batch_id="future_batch",
            samples=[sample],
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success
        assert response.acknowledged_count == 1

    def test_metric_name_mapping_all_types(self, grpc_stub, vm_api_url):
        fixture_path = os.path.join(
            os.path.dirname(__file__), "fixtures", "all_metric_types.json"
        )
        with open(fixture_path) as f:
            all_types = json.load(f)["all_metric_types"]

        samples = []
        base_ts = 1700004000000
        for i, (hk_type, data) in enumerate(all_types.items()):
            samples.append(
                health_export_pb2.HealthSample(
                    metric_name=data["metric_name"],
                    timestamp_ms=base_ts + i * 1000,
                    value=data["value"],
                    unit=data["unit"],
                    source="test",
                )
            )

        request = health_export_pb2.SyncRequest(
            device_id="test_all_types",
            batch_id="batch_all_types",
            samples=samples,
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success
        assert response.acknowledged_count == len(all_types)

    def test_invalid_metric_name_does_not_crash(self, grpc_stub):
        sample = health_export_pb2.HealthSample(
            metric_name="invalid_metric_$$$",
            timestamp_ms=1700005000000,
            value=1.0,
            source="test",
        )
        request = health_export_pb2.SyncRequest(
            device_id="test_invalid",
            batch_id="invalid_batch",
            samples=[sample],
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success
        assert response.acknowledged_count == 1

    def test_large_payload(self, grpc_stub):
        samples = [
            health_export_pb2.HealthSample(
                metric_name="apple_health_steps_total",
                timestamp_ms=1700006000000 + i,
                value=float(i),
                source="test",
            )
            for i in range(5000)
        ]
        request = health_export_pb2.SyncRequest(
            device_id="test_large",
            batch_id="large_batch",
            samples=samples,
        )
        response = grpc_stub.SyncMetrics(request)
        assert response.success
        assert response.acknowledged_count == 5000

    def test_get_checkpoint(self, grpc_stub):
        device_id = "test_checkpoint_fetch"
        ts = 1700007000000

        sample = health_export_pb2.HealthSample(
            metric_name="apple_health_steps_total",
            timestamp_ms=ts,
            value=100.0,
            source="test",
        )
        grpc_stub.SyncMetrics(health_export_pb2.SyncRequest(
            device_id=device_id,
            batch_id="cp_fetch_batch",
            samples=[sample],
        ))

        cp_request = health_export_pb2.CheckpointRequest(device_id=device_id)
        cp_response = grpc_stub.GetCheckpoint(cp_request)
        assert "apple_health_steps_total" in cp_response.checkpoint
        assert cp_response.checkpoint["apple_health_steps_total"] == ts