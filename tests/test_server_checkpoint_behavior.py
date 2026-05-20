import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

import health_export_pb2
from checkpoint_store import CheckpointStore
from server import HealthExportServicer


class FakeVMWriter:
    def __init__(self):
        self.samples = []

    def add_samples(self, samples):
        self.samples.extend(samples)


class FakeContext:
    def peer(self):
        return "test-peer"


def make_servicer(tmp_path):
    store = CheckpointStore(db_path=str(tmp_path / "checkpoints.db"))
    writer = FakeVMWriter()
    return HealthExportServicer(vm_writer=writer, checkpoint_store=store), store


def test_client_checkpoints_do_not_advance_server_checkpoint(tmp_path):
    servicer, store = make_servicer(tmp_path)

    response = servicer.SyncMetrics(
        health_export_pb2.SyncRequest(
            device_id="device",
            batch_id="client_checkpoint_only",
            checkpoint={"apple_health_blood_pressure_systolic_mmhg": 1700000000000},
        ),
        FakeContext(),
    )

    assert response.success
    assert store.get_checkpoint("device") == {}
    assert "apple_health_blood_pressure_systolic_mmhg" not in response.updated_checkpoint


def test_historical_export_clears_stale_server_checkpoints(tmp_path):
    servicer, store = make_servicer(tmp_path)
    store.update_checkpoint(
        "device",
        {
            "apple_health_blood_pressure_systolic_mmhg": 1700000000000,
            "apple_health_steps_total": 1700000000000,
        },
    )

    response = servicer.SyncMetrics(
        health_export_pb2.SyncRequest(
            device_id="device",
            batch_id="historical_resync",
            samples=[
                health_export_pb2.HealthSample(
                    metric_name="apple_health_steps_total",
                    timestamp_ms=1700001000000,
                    value=100,
                    source="test",
                )
            ],
            is_historical_export=True,
        ),
        FakeContext(),
    )

    assert response.success
    assert response.updated_checkpoint == {"apple_health_steps_total": 1700001000000}
    assert store.get_checkpoint("device") == {"apple_health_steps_total": 1700001000000}
