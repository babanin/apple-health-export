import time
import pytest
import requests
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

from vm_writer import VMWriter, sanitize_label


@pytest.mark.integration
class TestVMWriter:
    def test_write_single_metric(self, vm_container):
        writer = VMWriter(vm_url=vm_container)
        writer.start()
        try:
            writer.add_sample(
                metric_name="apple_health_heart_rate_bpm",
                timestamp_ms=1700010000000,
                value=72.5,
                labels={"source": "Apple Watch"},
            )
            writer.flush()
            time.sleep(1)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": "apple_health_heart_rate_bpm"},
                timeout=5,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) > 0
        finally:
            writer.stop()

    def test_write_batch_metrics(self, vm_container):
        writer = VMWriter(vm_url=vm_container)
        writer.start()
        try:
            for i in range(100):
                writer.add_sample(
                    metric_name="apple_health_steps_total",
                    timestamp_ms=1700011000000 + i * 1000,
                    value=float(100 + i),
                    labels={"source": "iPhone"},
                )
            writer.flush()
            time.sleep(1)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": "apple_health_steps_total"},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()

    def test_metric_name_format(self, vm_container):
        writer = VMWriter(vm_url=vm_container)
        writer.start()
        try:
            writer.add_sample(
                metric_name="apple_health_blood_pressure_systolic_mmhg",
                timestamp_ms=1700012000000,
                value=120.0,
                labels={"source": "test"},
            )
            writer.flush()
            time.sleep(1)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": "apple_health_blood_pressure_systolic_mmhg"},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()

    def test_label_preservation(self, vm_container):
        writer = VMWriter(vm_url=vm_container)
        writer.start()
        try:
            writer.add_sample(
                metric_name="apple_health_heart_rate_bpm",
                timestamp_ms=1700013000000,
                value=80.0,
                labels={"source": "Apple Watch", "workout_type": "running", "device": "Apple Watch Series 9"},
            )
            writer.flush()
            time.sleep(1)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": '{apple_health_heart_rate_bpm{workout_type="running"}'},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()

    def test_duplicate_timestamp_handling(self, vm_container):
        writer = VMWriter(vm_url=vm_container)
        writer.start()
        try:
            for _ in range(3):
                writer.add_sample(
                    metric_name="apple_health_oxygen_saturation_percent",
                    timestamp_ms=1700014000000,
                    value=97.0,
                    labels={"source": "test"},
                )
            writer.flush()
            time.sleep(1)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": "apple_health_oxygen_saturation_percent"},
                timeout=5,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) > 0
        finally:
            writer.stop()

    def test_timestamp_millisecond_precision(self, vm_container):
        writer = VMWriter(vm_url=vm_container)
        writer.start()
        try:
            ts = 1700015000123
            writer.add_sample(
                metric_name="apple_health_body_mass_kg",
                timestamp_ms=ts,
                value=75.3,
                labels={"source": "test"},
            )
            writer.flush()
            time.sleep(1)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": "apple_health_body_mass_kg"},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()

    def test_flush_on_threshold(self, vm_container):
        writer = VMWriter(vm_url=vm_container, flush_threshold=50)
        writer.start()
        try:
            for i in range(50):
                writer.add_sample(
                    metric_name="apple_health_uv_index",
                    timestamp_ms=1700016000000 + i * 1000,
                    value=float(i),
                    labels={"source": "test"},
                )
            time.sleep(2)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": "apple_health_uv_index"},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()

    def test_retry_on_vm_failure(self):
        writer = VMWriter(vm_url="http://localhost:9999", max_retries=2, retry_backoff_base=0.01)
        writer.start()
        try:
            writer.add_sample(
                metric_name="apple_health_heart_rate_bpm",
                timestamp_ms=1700017000000,
                value=60.0,
                labels={"source": "test"},
            )
            result = writer.flush()
            assert result is False
        finally:
            writer.stop()

    def test_incremental_sync_no_duplicates(self, vm_container):
        writer = VMWriter(vm_url=vm_container)
        writer.start()
        try:
            for i in range(10):
                writer.add_sample(
                    metric_name="apple_health_walking_speed_m_per_sec",
                    timestamp_ms=1700018000000 + i * 1000,
                    value=1.2 + i * 0.01,
                    labels={"source": "test"},
                )
            writer.flush()
            time.sleep(1)

            for i in range(10, 20):
                writer.add_sample(
                    metric_name="apple_health_walking_speed_m_per_sec",
                    timestamp_ms=1700018000000 + i * 1000,
                    value=1.2 + i * 0.01,
                    labels={"source": "test"},
                )
            writer.flush()
            time.sleep(1)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": "apple_health_walking_speed_m_per_sec"},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()

    def test_special_characters_in_labels(self, vm_container):
        writer = VMWriter(vm_url=vm_container)
        writer.start()
        try:
            writer.add_sample(
                metric_name="apple_health_heart_rate_bpm",
                timestamp_ms=1700019000000,
                value=72.0,
                labels={"source": "test", "path/with/slashes": "val", "dot.separated": "val2"},
            )
            writer.flush()
            time.sleep(1)
        finally:
            writer.stop()

    def test_sleep_stage_category_export(self, vm_container):
        writer = VMWriter(vm_url=vm_container)
        writer.start()
        try:
            for i in range(60):
                writer.add_sample(
                    metric_name="apple_health_sleep_stage",
                    timestamp_ms=1700020000000 + i * 60000,
                    value=4.0,
                    labels={"source": "Apple Watch", "stage": "Deep"},
                )
            writer.flush()
            time.sleep(1)

            resp = requests.get(
                f"{vm_container}/api/v1/export",
                params={"match[]": 'apple_health_sleep_stage{stage="Deep"}'},
                timeout=5,
            )
            assert resp.status_code == 200
        finally:
            writer.stop()

    def test_sanitize_label(self):
        assert sanitize_label("path/with/slashes") == "path_with_slashes"
        assert sanitize_label("dot.separated") == "dot_separated"
        assert sanitize_label("with spaces") == "with_spaces"
        assert sanitize_label("(parentheses)") == "parentheses"
        assert sanitize_label("normal_label") == "normal_label"