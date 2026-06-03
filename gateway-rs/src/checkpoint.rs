use std::collections::HashMap;
use std::sync::Arc;

use rusqlite::Connection;
use tracing::{debug, info};

pub struct CheckpointStore {
    db_path: String,
}

impl CheckpointStore {
    pub fn new(db_path: &str) -> rusqlite::Result<Self> {
        let store = Self {
            db_path: db_path.to_string(),
        };
        store.init_db()?;
        Ok(store)
    }

    fn connect(&self) -> rusqlite::Result<Connection> {
        let conn = Connection::open(&self.db_path)?;
        conn.execute_batch("PRAGMA journal_mode=WAL;")?;
        Ok(conn)
    }

    fn init_db(&self) -> rusqlite::Result<()> {
        let conn = self.connect()?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS checkpoints (
                device_id TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                last_timestamp_ms INTEGER NOT NULL,
                PRIMARY KEY (device_id, metric_type)
            );",
        )?;
        debug!(db_path = %self.db_path, "checkpoint database initialized");
        Ok(())
    }

    pub fn get_checkpoint(&self, device_id: &str) -> HashMap<String, i64> {
        let conn = match self.connect() {
            Ok(c) => c,
            Err(e) => {
                tracing::error!("failed to open checkpoint db for read: {e}");
                return HashMap::new();
            }
        };
        let mut stmt = match conn
            .prepare("SELECT metric_type, last_timestamp_ms FROM checkpoints WHERE device_id = ?1")
        {
            Ok(s) => s,
            Err(e) => {
                tracing::error!("failed to prepare checkpoint query: {e}");
                return HashMap::new();
            }
        };

        let rows = match stmt.query_map([device_id], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
        }) {
            Ok(r) => r,
            Err(e) => {
                tracing::error!("failed to query checkpoints: {e}");
                return HashMap::new();
            }
        };

        let mut result = HashMap::new();
        for row in rows.flatten() {
            result.insert(row.0, row.1);
        }
        debug!(device_id, metrics = result.len(), "checkpoint read");
        result
    }

    pub fn update_checkpoint(&self, device_id: &str, checkpoint: &HashMap<String, i64>) {
        if checkpoint.is_empty() {
            info!(device_id, "checkpoint update: no metrics to update");
            return;
        }
        let conn = match self.connect() {
            Ok(c) => c,
            Err(e) => {
                tracing::error!("failed to open checkpoint db for write: {e}");
                return;
            }
        };

        let tx = match conn.unchecked_transaction() {
            Ok(t) => t,
            Err(e) => {
                tracing::error!("failed to begin transaction: {e}");
                return;
            }
        };

        for (metric_type, timestamp_ms) in checkpoint {
            let _ = tx.execute(
                "INSERT INTO checkpoints (device_id, metric_type, last_timestamp_ms)
                 VALUES (?1, ?2, ?3)
                 ON CONFLICT(device_id, metric_type)
                 DO UPDATE SET last_timestamp_ms = MAX(excluded.last_timestamp_ms, checkpoints.last_timestamp_ms)",
                rusqlite::params![device_id, metric_type, timestamp_ms],
            );
        }

        if let Err(e) = tx.commit() {
            tracing::error!("failed to commit checkpoint update: {e}");
        } else {
            info!(device_id, metrics = checkpoint.len(), "checkpoint updated");
        }
    }

    pub fn get_metrics_needing_sync(
        &self,
        device_id: &str,
        available_metrics: &HashMap<String, i64>,
    ) -> HashMap<String, i64> {
        let current = self.get_checkpoint(device_id);
        let mut result = HashMap::new();
        for (metric, latest_ts) in available_metrics {
            let server_ts = current.get(metric).copied().unwrap_or(0);
            if latest_ts > &server_ts {
                result.insert(metric.clone(), server_ts);
            }
        }
        result
    }

    pub fn delete_device(&self, device_id: &str) {
        let conn = match self.connect() {
            Ok(c) => c,
            Err(e) => {
                tracing::error!("failed to open checkpoint db for delete: {e}");
                return;
            }
        };
        match conn.execute("DELETE FROM checkpoints WHERE device_id = ?1", [device_id]) {
            Ok(rows) => info!(device_id, deleted_rows = rows, "device checkpoints deleted"),
            Err(e) => tracing::error!("failed to delete device checkpoints: {e}"),
        }
    }
}

pub type SharedCheckpointStore = Arc<CheckpointStore>;
