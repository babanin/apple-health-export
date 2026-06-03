use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

use tokio_stream::wrappers::ReceiverStream;
use tokio_stream::StreamExt;
use tonic::{Request, Response, Status};

use crate::checkpoint::SharedCheckpointStore;
use crate::vm_writer::VmWriter;

const SERVER_VERSION: &str = "0.1.0";
const MAX_LOG_ITEMS: usize = 80;

const BLOOD_PRESSURE_METRICS: &[&str] = &[
    "apple_health_blood_pressure_systolic_mmhg",
    "apple_health_blood_pressure_diastolic_mmhg",
];

fn format_timestamp_ms(timestamp_ms: i64) -> String {
    let secs = timestamp_ms / 1000;
    let nanos = (timestamp_ms % 1000) as u32 * 1_000_000;
    chrono::DateTime::from_timestamp(secs, nanos)
        .map(|dt| dt.to_rfc3339_opts(chrono::SecondsFormat::Millis, true))
        .unwrap_or_else(|| format!("invalid_ts({timestamp_ms})"))
}

fn format_counts(counts: &HashMap<String, usize>, limit: usize) -> String {
    let mut items: Vec<_> = counts.iter().collect();
    items.sort_by(|a, b| a.0.cmp(b.0));
    let visible = &items[..items.len().min(limit)];
    let mut s = visible
        .iter()
        .fold(String::new(), |mut acc, (name, count)| {
            if !acc.is_empty() {
                acc.push_str(", ");
            }
            use std::fmt::Write;
            let _ = write!(acc, "{name}={count}");
            acc
        });
    if items.len() > limit {
        use std::fmt::Write;
        let _ = write!(s, ", ... +{} more", items.len() - limit);
    }
    if s.is_empty() {
        s.push_str("none");
    }
    s
}

fn format_names(names: &[&str], limit: usize) -> String {
    let mut items: Vec<_> = names.to_vec();
    items.sort();
    let visible = &items[..items.len().min(limit)];
    let mut s = visible.iter().fold(String::new(), |mut acc, name| {
        if !acc.is_empty() {
            acc.push_str(", ");
        }
        acc.push_str(name);
        acc
    });
    if items.len() > limit {
        use std::fmt::Write;
        let _ = write!(s, ", ... +{} more", items.len() - limit);
    }
    if s.is_empty() {
        s.push_str("none");
    }
    s
}

fn format_timestamp_ranges(ranges: &HashMap<String, (i64, i64)>, limit: usize) -> String {
    let mut items: Vec<_> = ranges.iter().collect();
    items.sort_by(|a, b| a.0.cmp(b.0));
    let visible = &items[..items.len().min(limit)];
    let mut s = visible
        .iter()
        .fold(String::new(), |mut acc, (name, (start, end))| {
            if !acc.is_empty() {
                acc.push_str(", ");
            }
            use std::fmt::Write;
            let _ = write!(
                acc,
                "{}={}..{}",
                name,
                format_timestamp_ms(*start),
                format_timestamp_ms(*end)
            );
            acc
        });
    if items.len() > limit {
        use std::fmt::Write;
        let _ = write!(s, ", ... +{} more", items.len() - limit);
    }
    if s.is_empty() {
        s.push_str("none");
    }
    s
}

struct SampleSummary {
    metric_counts: HashMap<String, usize>,
    source_counts: HashMap<String, usize>,
    timestamp_ranges: HashMap<String, (i64, i64)>,
}

fn summarize_samples(samples: &[crate::HealthSample]) -> SampleSummary {
    let mut metric_counts: HashMap<String, usize> = HashMap::new();
    let mut source_counts: HashMap<String, usize> = HashMap::new();
    let mut timestamp_ranges: HashMap<String, (i64, i64)> = HashMap::new();

    for sample in samples {
        let metric_name = if sample.metric_name.is_empty() {
            "<empty>"
        } else {
            &sample.metric_name
        };
        let source = if sample.source.is_empty() {
            "<empty>"
        } else {
            &sample.source
        };

        *metric_counts.entry(metric_name.to_string()).or_insert(0) += 1;
        *source_counts.entry(source.to_string()).or_insert(0) += 1;

        let range = timestamp_ranges
            .entry(metric_name.to_string())
            .or_insert((i64::MAX, 0));
        range.0 = range.0.min(sample.timestamp_ms);
        range.1 = range.1.max(sample.timestamp_ms);
    }

    SampleSummary {
        metric_counts,
        source_counts,
        timestamp_ranges,
    }
}

pub struct HealthExportService {
    vm_writer: Arc<VmWriter>,
    checkpoint_store: SharedCheckpointStore,
}

impl HealthExportService {
    pub fn new(
        vm_writer: Arc<VmWriter>,
        checkpoint_store: crate::checkpoint::CheckpointStore,
    ) -> Self {
        Self {
            vm_writer,
            checkpoint_store: Arc::new(checkpoint_store),
        }
    }
}

#[tonic::async_trait]
impl crate::proto::health_export_service_server::HealthExportService for HealthExportService {
    async fn ping(
        &self,
        request: Request<crate::PingRequest>,
    ) -> Result<Response<crate::PingResponse>, Status> {
        let req = request.into_inner();
        tracing::info!(device_id = %req.device_id, "Ping");
        Ok(Response::new(crate::PingResponse {
            ok: true,
            server_version: SERVER_VERSION.to_string(),
        }))
    }

    async fn sync_metrics(
        &self,
        request: Request<crate::SyncRequest>,
    ) -> Result<Response<crate::SyncResponse>, Status> {
        let result = self.handle_sync_metrics(request.into_inner()).await;
        match result {
            Ok(response) => Ok(Response::new(response)),
            Err(e) => {
                tracing::error!("Error in SyncMetrics: {e}");
                Ok(Response::new(crate::SyncResponse {
                    acknowledged_count: 0,
                    updated_checkpoint: HashMap::new(),
                    success: false,
                    error_message: e.to_string(),
                }))
            }
        }
    }

    async fn get_checkpoint(
        &self,
        request: Request<crate::CheckpointRequest>,
    ) -> Result<Response<crate::CheckpointResponse>, Status> {
        let req = request.into_inner();
        tracing::info!(device_id = %req.device_id, "GetCheckpoint");
        let checkpoint = self.checkpoint_store.get_checkpoint(&req.device_id);
        tracing::info!(
            device_id = %req.device_id,
            metrics = checkpoint.len(),
            "GetCheckpoint response"
        );
        Ok(Response::new(crate::CheckpointResponse { checkpoint }))
    }

    type SyncStreamStream = ReceiverStream<Result<crate::SyncResponse, Status>>;

    async fn sync_stream(
        &self,
        request: Request<tonic::Streaming<crate::SyncRequest>>,
    ) -> Result<Response<Self::SyncStreamStream>, Status> {
        let mut stream = request.into_inner();
        let (tx, rx) = tokio::sync::mpsc::channel(128);

        let vm_writer = self.vm_writer.clone();
        let checkpoint_store = self.checkpoint_store.clone();

        tokio::spawn(async move {
            while let Some(result) = stream.next().await {
                let req = match result {
                    Ok(r) => r,
                    Err(e) => {
                        tracing::error!("SyncStream error receiving: {e}");
                        break;
                    }
                };

                let device_id = req.device_id.clone();
                let batch_id = req.batch_id.clone();

                let response = match Self::handle_sync_stream_message(
                    &vm_writer,
                    &checkpoint_store,
                    req,
                )
                .await
                {
                    Ok(r) => r,
                    Err(e) => {
                        tracing::error!(
                            device_id = %device_id,
                            batch_id = %batch_id,
                            error = %e,
                            "SyncStream: error processing message"
                        );
                        crate::SyncResponse {
                            acknowledged_count: 0,
                            updated_checkpoint: HashMap::new(),
                            success: false,
                            error_message: e.to_string(),
                        }
                    }
                };

                if tx.send(Ok(response)).await.is_err() {
                    break;
                }
            }
        });

        Ok(Response::new(ReceiverStream::new(rx)))
    }
}

impl HealthExportService {
    async fn handle_sync_metrics(
        &self,
        req: crate::SyncRequest,
    ) -> Result<crate::SyncResponse, Box<dyn std::error::Error + Send + Sync>> {
        let start = Instant::now();
        let device_id = req.device_id;
        let batch_id = req.batch_id;
        let num_samples = req.samples.len();
        let num_checkpoints = req.checkpoint.len();
        let is_historical = req.is_historical_export;

        tracing::info!(
            device_id = %device_id,
            batch_id = %batch_id,
            samples = num_samples,
            checkpoints = num_checkpoints,
            historical = is_historical,
            "SyncMetrics receive"
        );

        if is_historical {
            tracing::info!(
                device_id = %device_id,
                batch_id = %batch_id,
                "SyncMetrics: historical export requested; clearing server checkpoints"
            );
            self.checkpoint_store.delete_device(&device_id);
        }

        if req.samples.is_empty() && req.checkpoint.is_empty() {
            tracing::info!(
                device_id = %device_id,
                batch_id = %batch_id,
                "SyncMetrics: empty request, acknowledging"
            );
            let current = self.checkpoint_store.get_checkpoint(&device_id);
            return Ok(crate::SyncResponse {
                acknowledged_count: 0,
                updated_checkpoint: current,
                success: true,
                error_message: String::new(),
            });
        }

        let summary = summarize_samples(&req.samples);
        let empty_count = summary.metric_counts.get("<empty>").copied().unwrap_or(0);
        if empty_count > 0 {
            tracing::warn!(
                device_id = %device_id,
                batch_id = %batch_id,
                empty_metric_count = empty_count,
                "SyncMetrics: received samples with empty metric_name"
            );
        }
        tracing::info!(
            device_id = %device_id,
            batch_id = %batch_id,
            unique_metrics = summary.metric_counts.len(),
            metric_counts = %format_counts(&summary.metric_counts, MAX_LOG_ITEMS),
            "SyncMetrics metric summary"
        );
        tracing::info!(
            device_id = %device_id,
            batch_id = %batch_id,
            unique_sources = summary.source_counts.len(),
            source_counts = %format_counts(&summary.source_counts, MAX_LOG_ITEMS),
            "SyncMetrics source summary"
        );
        tracing::info!(
            device_id = %device_id,
            batch_id = %batch_id,
            systolic = summary.metric_counts.get(BLOOD_PRESSURE_METRICS[0]).copied().unwrap_or(0),
            diastolic = summary.metric_counts.get(BLOOD_PRESSURE_METRICS[1]).copied().unwrap_or(0),
            "SyncMetrics blood pressure counts"
        );
        tracing::debug!(
            device_id = %device_id,
            batch_id = %batch_id,
            timestamp_ranges = %format_timestamp_ranges(&summary.timestamp_ranges, MAX_LOG_ITEMS),
            "SyncMetrics timestamp ranges"
        );

        self.vm_writer.add_samples(&req.samples).await;

        let mut updated: HashMap<String, i64> = HashMap::new();
        for sample in &req.samples {
            let metric = &sample.metric_name;
            let ts = sample.timestamp_ms;
            let entry = updated.entry(metric.clone()).or_insert(i64::MIN);
            if ts > *entry {
                *entry = ts;
            }
        }

        if !updated.is_empty() {
            let names: Vec<&str> = updated.keys().map(|s| s.as_str()).collect();
            tracing::info!(
                device_id = %device_id,
                batch_id = %batch_id,
                metrics = updated.len(),
                names = %format_names(&names, MAX_LOG_ITEMS),
                "SyncMetrics: updating checkpoints"
            );
            self.checkpoint_store
                .update_checkpoint(&device_id, &updated);
        } else if !req.checkpoint.is_empty() {
            tracing::info!(
                device_id = %device_id,
                batch_id = %batch_id,
                client_checkpoints = req.checkpoint.len(),
                "SyncMetrics: received client checkpoints but no sample-derived checkpoint updates"
            );
        }

        let current = self.checkpoint_store.get_checkpoint(&device_id);
        let elapsed_ms = start.elapsed().as_millis();

        tracing::info!(
            device_id = %device_id,
            batch_id = %batch_id,
            acknowledged = num_samples,
            checkpoint_metrics = current.len(),
            elapsed_ms,
            "SyncMetrics complete"
        );

        Ok(crate::SyncResponse {
            acknowledged_count: num_samples as i32,
            updated_checkpoint: current,
            success: true,
            error_message: String::new(),
        })
    }

    async fn handle_sync_stream_message(
        vm_writer: &Arc<VmWriter>,
        checkpoint_store: &SharedCheckpointStore,
        req: crate::SyncRequest,
    ) -> Result<crate::SyncResponse, Box<dyn std::error::Error + Send + Sync>> {
        let device_id = req.device_id.clone();
        let batch_id = req.batch_id.clone();
        let is_historical = req.is_historical_export;

        if is_historical {
            tracing::info!(
                device_id = %device_id,
                batch_id = %batch_id,
                "SyncStream: historical export; clearing checkpoints"
            );
            checkpoint_store.delete_device(&device_id);
        }

        if req.samples.is_empty() && req.checkpoint.is_empty() {
            let current = checkpoint_store.get_checkpoint(&device_id);
            return Ok(crate::SyncResponse {
                acknowledged_count: 0,
                updated_checkpoint: current,
                success: true,
                error_message: String::new(),
            });
        }

        vm_writer.add_samples(&req.samples).await;

        let mut updated: HashMap<String, i64> = HashMap::new();
        for sample in &req.samples {
            let metric = &sample.metric_name;
            let ts = sample.timestamp_ms;
            let entry = updated.entry(metric.clone()).or_insert(i64::MIN);
            if ts > *entry {
                *entry = ts;
            }
        }

        if !updated.is_empty() {
            checkpoint_store.update_checkpoint(&device_id, &updated);
        }

        let current = checkpoint_store.get_checkpoint(&device_id);
        Ok(crate::SyncResponse {
            acknowledged_count: req.samples.len() as i32,
            updated_checkpoint: current,
            success: true,
            error_message: String::new(),
        })
    }
}
