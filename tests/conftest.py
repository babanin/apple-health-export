import os
import time
import docker
import grpc
import pytest
import requests
import sys
from concurrent import futures

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

import health_export_pb2
import health_export_pb2_grpc
from checkpoint_store import CheckpointStore
from vm_writer import VMWriter


@pytest.fixture(scope="session")
def vm_container():
    client = docker.from_env()
    container = client.containers.run(
        "victoriametrics/victoria-metrics:latest",
        command=["--storageDataPath=/victoria-metrics-data", "--httpListenAddr=:8428", "--retentionPeriod=100y"],
        ports={"8428/tcp": None},
        detach=True,
        remove=True,
    )
    time.sleep(2)
    container.reload()
    port = container.ports["8428/tcp"][0]["HostPort"]
    vm_url = f"http://localhost:{port}"

    for _ in range(30):
        try:
            r = requests.get(f"{vm_url}/health", timeout=2)
            if r.status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(1)

    yield vm_url

    container.stop()


@pytest.fixture(scope="session")
def checkpoint_db(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("checkpoints") / "test_checkpoints.db")
    store = CheckpointStore(db_path=db_path)
    yield store
    store.close()


@pytest.fixture
def grpc_stub(vm_container):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    from server import HealthExportServicer

    vm_writer = VMWriter(vm_url=vm_container)
    checkpoint_store = CheckpointStore(db_path="/tmp/test_checkpoints_sync.db")
    servicer = HealthExportServicer(vm_writer=vm_writer, checkpoint_store=checkpoint_store)

    health_export_pb2_grpc.add_HealthExportServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("[::]:0")
    server.start()

    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = health_export_pb2_grpc.HealthExportServiceStub(channel)

    yield stub

    vm_writer.stop()
    server.stop(grace=1)
    channel.close()


@pytest.fixture
def sample_samples():
    return [
        health_export_pb2.HealthSample(
            metric_name="apple_health_heart_rate_bpm",
            timestamp_ms=1700000000000,
            value=72.5,
            unit="bpm",
            source="Apple Watch",
            labels={"device": "Apple Watch Series 9"},
        ),
        health_export_pb2.HealthSample(
            metric_name="apple_health_steps_total",
            timestamp_ms=1700000000000,
            value=150.0,
            unit="count",
            source="iPhone",
            labels={"device": "iPhone 15 Pro"},
        ),
        health_export_pb2.HealthSample(
            metric_name="apple_health_oxygen_saturation_percent",
            timestamp_ms=1700000000000,
            value=98.0,
            unit="percent",
            source="Apple Watch",
            labels={"device": "Apple Watch Series 9"},
        ),
    ]


@pytest.fixture
def vm_api_url(vm_container):
    return vm_container