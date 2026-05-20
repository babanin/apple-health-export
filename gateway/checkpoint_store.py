import logging
import sqlite3
from typing import Dict

logger = logging.getLogger(__name__)


class CheckpointStore:
    def __init__(self, db_path: str = "checkpoints.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    device_id TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    last_timestamp_ms INTEGER NOT NULL,
                    PRIMARY KEY (device_id, metric_type)
                )
            """)
            conn.commit()

    def get_checkpoint(self, device_id: str) -> Dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT metric_type, last_timestamp_ms FROM checkpoints WHERE device_id = ?",
                (device_id,),
            )
            checkpoint = {row[0]: row[1] for row in cursor.fetchall()}
            logger.debug("CheckpointStore get device=%s metrics=%d", device_id, len(checkpoint))
            return checkpoint

    def update_checkpoint(self, device_id: str, checkpoint: Dict[str, int]):
        if not checkpoint:
            logger.info("CheckpointStore update device=%s metrics=0", device_id)
            return

        with sqlite3.connect(self.db_path) as conn:
            for metric_type, timestamp_ms in checkpoint.items():
                conn.execute(
                    """
                    INSERT INTO checkpoints (device_id, metric_type, last_timestamp_ms)
                    VALUES (?, ?, ?)
                    ON CONFLICT(device_id, metric_type)
                    DO UPDATE SET last_timestamp_ms = MAX(excluded.last_timestamp_ms, checkpoints.last_timestamp_ms)
                    """,
                    (device_id, metric_type, timestamp_ms),
                )
            conn.commit()
        logger.info("CheckpointStore update device=%s metrics=%d", device_id, len(checkpoint))

    def get_metrics_needing_sync(self, device_id: str, available_metrics: Dict[str, int]) -> Dict[str, int]:
        current = self.get_checkpoint(device_id)
        result = {}
        for metric, latest_ts in available_metrics.items():
            if metric not in current or latest_ts > current[metric]:
                result[metric] = current.get(metric, 0)
        return result

    def delete_device(self, device_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM checkpoints WHERE device_id = ?", (device_id,))
            conn.commit()

    def close(self):
        pass
