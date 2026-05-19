import json
import os
import time
import pytest
import requests
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

import health_export_pb2
import health_export_pb2_grpc


def wait_for_vm(url, timeout=30):
    for _ in range(timeout):
        try:
            r = requests.get(f"{url}/health", timeout=2)
            if r.status_code == 200:
                return True
        except requests.ConnectionError:
            time.sleep(1)
    return False


@pytest.mark.integration
class TestEndToEnd:
    def test_full_historical_export(self, vm_container):
        import grpc
        from concurrent import futures
        from server import HealthExportServicer
        from checkpoint_store import CheckpointStore
        from vm_writer import VMWriter

        writer = VMWriter(vm_url=vm_container)
        writer.start()

        checkpoint_store = CheckpointStore(db_path="/tmp/test_e2e_historical.db")
        servicer = HealthExportServicer(vm_writer=writer, checkpoint_store=checkpoint_store)

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        health_export_pb2_grpc.add_HealthExportServiceServicer_to_server(servicer, server)
        port = server.add_insecure_port("[::]:0")
        server.start()

        channel = grpc.insecure_channel(f"localhost:{port}")
        stub = health_export_pb2_grpc.HealthExportServiceStub(channel)

        try:
            fixture_path = os.path.join(
                os.path.dirname(__file__), "fixtures", "all_metric_types.json"
            )
            with open(fixture_path) as f:
                all_types = json.load(f)["all_metric_types"]

            samples = []
            base_ts = 1700030000000
            for i, (hk_type, data) in enumerate(all_types.items()):
                samples.append(health_export_pb2.HealthSample(
                    metric_name=data["metric_name"],
                    timestamp_ms=base_ts + i * 1000,
                    value=data["value"],
                    unit=data["unit"],
                    source="test_e2e",
                ))

            request = health_export_pb2.SyncRequest(
                device_id="e2e_device",
                batch_id="e2e_historical",
                samples=samples,
                is_historical_export=True,
            )
            response = stub.SyncMetrics(request)
            assert response.success
            assert response.acknowledged_count == len(all_types)

            writer.flush()
            time.sleep(2)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": 'apple_health_heart_rate_bpm{source="test_e2e"}'},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()
            server.stop(grace=1)
            channel.close()
            os.unlink("/tmp/test_e2e_historical.db")

    def test_incremental_sync_after_historical(self, vm_container):
        import grpc
        from concurrent import futures
        from server import HealthExportServicer
        from checkpoint_store import CheckpointStore
        from vm_writer import VMWriter

        writer = VMWriter(vm_url=vm_container)
        writer.start()

        checkpoint_store = CheckpointStore(db_path="/tmp/test_e2e_incremental.db")
        servicer = HealthExportServicer(vm_writer=writer, checkpoint_store=checkpoint_store)

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        health_export_pb2_grpc.add_HealthExportServiceServicer_to_server(servicer, server)
        port = server.add_insecure_port("[::]:0")
        server.start()

        channel = grpc.insecure_channel(f"localhost:{port}")
        stub = health_export_pb2_grpc.HealthExportServiceStub(channel)

        try:
            historical_samples = [
                health_export_pb2.HealthSample(
                    metric_name="apple_health_steps_total",
                    timestamp_ms=1700040000000 + i * 1000,
                    value=float(i * 10),
                    source="test_incremental",
                )
                for i in range(100)
            ]

            response1 = stub.SyncMetrics(health_export_pb2.SyncRequest(
                device_id="e2e_incremental_device",
                batch_id="incremental_1",
                samples=historical_samples,
                is_historical_export=True,
            ))
            assert response1.success
            assert "apple_health_steps_total" in response1.updated_checkpoint

            writer.flush()
            time.sleep(2)

            new_samples = [
                health_export_pb2.HealthSample(
                    metric_name="apple_health_steps_total",
                    timestamp_ms=1700040100000 + i * 1000,
                    value=float(1000 + i),
                    source="test_incremental",
                )
                for i in range(10)
            ]

            response2 = stub.SyncMetrics(health_export_pb2.SyncRequest(
                device_id="e2e_incremental_device",
                batch_id="incremental_2",
                samples=new_samples,
            ))
            assert response2.success
            assert response2.acknowledged_count == 10
        finally:
            writer.stop()
            server.stop(grace=1)
            channel.close()
            os.unlink("/tmp/test_e2e_incremental.db")

    def test_data_fidelity(self, vm_container):
        import grpc
        from concurrent import futures
        from server import HealthExportServicer
        from checkpoint_store import CheckpointStore
        from vm_writer import VMWriter

        writer = VMWriter(vm_url=vm_container)
        writer.start()

        checkpoint_store = CheckpointStore(db_path="/tmp/test_e2e_fidelity.db")
        servicer = HealthExportServicer(vm_writer=writer, checkpoint_store=checkpoint_store)

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        health_export_pb2_grpc.add_HealthExportServiceServicer_to_server(servicer, server)
        port = server.add_insecure_port("[::]:0")
        server.start()

        channel = grpc.insecure_channel(f"localhost:{port}")
        stub = health_export_pb2_grpc.HealthExportServiceStub(channel)

        try:
            sample = health_export_pb2.HealthSample(
                metric_name="apple_health_heart_rate_bpm",
                timestamp_ms=1700050000123,
                value=72.345,
                unit="bpm",
                source="Apple Watch",
            )
            response = stub.SyncMetrics(health_export_pb2.SyncRequest(
                device_id="e2e_fidelity_device",
                batch_id="fidelity_batch",
                samples=[sample],
            ))
            assert response.success

            writer.flush()
            time.sleep(2)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": 'apple_health_heart_rate_bpm{source="Apple Watch"}'},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()
            server.stop(grace=1)
            channel.close()
            os.unlink("/tmp/test_e2e_fidelity.db")

    def test_two_devices_concurrent(self, vm_container):
        import grpc
        from concurrent import futures
        from server import HealthExportServicer
        from checkpoint_store import CheckpointStore
        from vm_writer import VMWriter

        writer = VMWriter(vm_url=vm_container)
        writer.start()

        checkpoint_store = CheckpointStore(db_path="/tmp/test_e2e_two_devices.db")
        servicer = HealthExportServicer(vm_writer=writer, checkpoint_store=checkpoint_store)

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        health_export_pb2_grpc.add_HealthExportServiceServicer_to_server(servicer, server)
        port = server.add_insecure_port("[::]:0")
        server.start()

        channel = grpc.insecure_channel(f"localhost:{port}")
        stub = health_export_pb2_grpc.HealthExportServiceStub(channel)

        try:
            for device in ["device_alpha", "device_beta"]:
                sample = health_export_pb2.HealthSample(
                    metric_name="apple_health_steps_total",
                    timestamp_ms=1700060000000,
                    value=5000.0,
                    source=device,
                )
                response = stub.SyncMetrics(health_export_pb2.SyncRequest(
                    device_id=device,
                    batch_id=f"two_dev_{device}",
                    samples=[sample],
                ))
                assert response.success

            writer.flush()
            time.sleep(2)

            cp_alpha = checkpoint_store.get_checkpoint("device_alpha")
            cp_beta = checkpoint_store.get_checkpoint("device_beta")
            assert "apple_health_steps_total" in cp_alpha
            assert "apple_health_steps_total" in cp_beta

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": "apple_health_steps_total"},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()
            server.stop(grace=1)
            channel.close()
            os.unlink("/tmp/test_e2e_two_devices.db")

    def test_sleep_analysis_interval_sampling(self, vm_container):
        import grpc
        from concurrent import futures
        from server import HealthExportServicer
        from checkpoint_store import CheckpointStore
        from vm_writer import VMWriter

        writer = VMWriter(vm_url=vm_container)
        writer.start()

        checkpoint_store = CheckpointStore(db_path="/tmp/test_e2e_sleep.db")
        servicer = HealthExportServicer(vm_writer=writer, checkpoint_store=checkpoint_store)

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        health_export_pb2_grpc.add_HealthExportServiceServicer_to_server(servicer, server)
        port = server.add_insecure_port("[::]:0")
        server.start()

        channel = grpc.insecure_channel(f"localhost:{port}")
        stub = health_export_pb2_grpc.HealthExportServiceStub(channel)

        try:
            samples = []
            for i in range(60):
                samples.append(health_export_pb2.HealthSample(
                    metric_name="apple_health_sleep_stage",
                    timestamp_ms=1700070000000 + i * 60000,
                    value=4.0,
                    unit="",
                    source="Apple Watch",
                    labels={"stage": "Deep"},
                ))

            response = stub.SyncMetrics(health_export_pb2.SyncRequest(
                device_id="e2e_sleep_device",
                batch_id="sleep_batch",
                samples=samples,
            ))
            assert response.success
            assert response.acknowledged_count == 60

            writer.flush()
            time.sleep(2)
        finally:
            writer.stop()
            server.stop(grace=1)
            channel.close()
            os.unlink("/tmp/test_e2e_sleep.db")