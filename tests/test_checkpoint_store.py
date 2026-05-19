import os
import tempfile
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

from checkpoint_store import CheckpointStore


class TestCheckpointStore:
    def test_save_and_load_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = CheckpointStore(db_path=db_path)
            result = store.get_checkpoint("device_1")
            assert result == {}
            store.close()
        finally:
            os.unlink(db_path)

    def test_save_single_checkpoint(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = CheckpointStore(db_path=db_path)
            store.update_checkpoint("device_1", {"heart_rate_bpm": 1700000000000})
            result = store.get_checkpoint("device_1")
            assert result == {"heart_rate_bpm": 1700000000000}
            store.close()
        finally:
            os.unlink(db_path)

    def test_save_multiple_metrics(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = CheckpointStore(db_path=db_path)
            data = {f"metric_{i}": 1700000000000 + i * 1000 for i in range(90)}
            store.update_checkpoint("device_1", data)
            result = store.get_checkpoint("device_1")
            assert len(result) == 90
            for key, value in data.items():
                assert result[key] == value
            store.close()
        finally:
            os.unlink(db_path)

    def test_checkpoint_update(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = CheckpointStore(db_path=db_path)
            store.update_checkpoint("device_1", {"heart_rate": 1700000000000})
            store.update_checkpoint("device_1", {"heart_rate": 1700000100000})
            result = store.get_checkpoint("device_1")
            assert result["heart_rate"] == 1700000100000
            store.close()
        finally:
            os.unlink(db_path)

    def test_checkpoint_persistence_across_db_close(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store1 = CheckpointStore(db_path=db_path)
            store1.update_checkpoint("device_1", {"steps": 1700000000000, "hr": 1700000001000})
            store1.close()

            store2 = CheckpointStore(db_path=db_path)
            result = store2.get_checkpoint("device_1")
            assert result["steps"] == 1700000000000
            assert result["hr"] == 1700000001000
            store2.close()
        finally:
            os.unlink(db_path)

    def test_concurrent_checkpoint_writes(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = CheckpointStore(db_path=db_path)
            errors = []

            def writer(metric, ts):
                try:
                    store.update_checkpoint("device_concurrent", {metric: ts})
                except Exception as e:
                    errors.append(str(e))

            threads = [
                threading.Thread(target=writer, args=(f"metric_{i}", 1700000000000 + i * 1000))
                for i in range(20)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Errors: {errors}"
            result = store.get_checkpoint("device_concurrent")
            assert len(result) == 20
            store.close()
        finally:
            os.unlink(db_path)

    def test_device_id_isolation(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = CheckpointStore(db_path=db_path)
            store.update_checkpoint("device_1", {"hr": 1700000000000})
            store.update_checkpoint("device_2", {"hr": 1800000000000})

            cp1 = store.get_checkpoint("device_1")
            cp2 = store.get_checkpoint("device_2")
            assert cp1["hr"] == 1700000000000
            assert cp2["hr"] == 1800000000000
            store.close()
        finally:
            os.unlink(db_path)

    def test_query_metrics_needing_sync(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = CheckpointStore(db_path=db_path)
            store.update_checkpoint("device_1", {
                "heart_rate": 1700000000000,
                "steps": 1700000005000,
            })

            available = {
                "heart_rate": 1700000001000,
                "steps": 1700000010000,
                "oxygen": 1700000000000,
            }

            needing = store.get_metrics_needing_sync("device_1", available)
            assert "heart_rate" in needing
            assert needing["heart_rate"] == 1700000000000
            assert "steps" in needing
            assert needing["steps"] == 1700000005000
            assert "oxygen" in needing
            assert needing["oxygen"] == 0
            store.close()
        finally:
            os.unlink(db_path)

    def test_delete_device(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = CheckpointStore(db_path=db_path)
            store.update_checkpoint("device_to_delete", {"hr": 1700000000000})
            store.delete_device("device_to_delete")
            result = store.get_checkpoint("device_to_delete")
            assert result == {}
            store.close()
        finally:
            os.unlink(db_path)