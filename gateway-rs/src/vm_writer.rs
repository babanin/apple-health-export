use std::collections::HashMap;
use std::fmt::Write;
use std::sync::Arc;
use std::time::Duration;

use serde_json::json;
use tokio::sync::{watch, Mutex};
use tracing::{error, info, warn};

const LABEL_SANITIZATION_MAP: &[(&str, &str)] = &[
    ("/", "_"),
    (".", "_"),
    ("-", "_"),
    (" ", "_"),
    ("(", ""),
    (")", ""),
];

fn sanitize_label(value: &str) -> String {
    let mut result = value.to_string();
    for &(pat, rep) in LABEL_SANITIZATION_MAP {
        result = result.replace(pat, rep);
    }
    result
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
            let _ = write!(acc, "{name}={count}");
            acc
        });
    if items.len() > limit {
        let _ = write!(s, ", ... +{} more", items.len() - limit);
    }
    if s.is_empty() {
        s.push_str("none");
    }
    s
}

struct BufferedSample {
    timestamp_ms: i64,
    value: f64,
    labels: HashMap<String, String>,
}

struct WriterState {
    buffer: HashMap<String, Vec<BufferedSample>>,
    flush_count: u64,
    accepted_samples: u64,
}

pub struct VmWriter {
    state: Arc<Mutex<WriterState>>,
    vm_url: String,
    flush_interval: Duration,
    flush_threshold: usize,
    max_retries: u32,
    retry_backoff_base: Duration,
    client: reqwest::Client,
    shutdown_tx: watch::Sender<bool>,
    shutdown_rx: watch::Receiver<bool>,
}

impl VmWriter {
    pub fn new(
        vm_url: String,
        flush_interval: Duration,
        flush_threshold: usize,
        max_retries: u32,
        retry_backoff_base: Duration,
    ) -> Self {
        let vm_url = vm_url.trim_end_matches('/').to_string();
        #[allow(clippy::expect_used)]
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("failed to build HTTP client");
        let (shutdown_tx, shutdown_rx) = watch::channel(false);
        Self {
            state: Arc::new(Mutex::new(WriterState {
                buffer: HashMap::new(),
                flush_count: 0,
                accepted_samples: 0,
            })),
            vm_url,
            flush_interval,
            flush_threshold,
            max_retries,
            retry_backoff_base,
            client,
            shutdown_tx,
            shutdown_rx,
        }
    }

    pub async fn start(&self) {
        let state = self.state.clone();
        let flush_interval = self.flush_interval;
        let vm_url = self.vm_url.clone();
        let max_retries = self.max_retries;
        let retry_backoff_base = self.retry_backoff_base;
        let client = self.client.clone();
        let mut shutdown = self.shutdown_rx.clone();

        tokio::spawn(async move {
            let mut interval = tokio::time::interval(flush_interval);
            loop {
                tokio::select! {
                    _ = interval.tick() => {
                        let total: usize = {
                            let guard = state.lock().await;
                            guard.buffer.values().map(|v| v.len()).sum()
                        };
                        if total > 0 {
                            Self::do_flush(&state, &vm_url, max_retries, retry_backoff_base, &client).await;
                        }
                    }
                    _ = shutdown.changed() => {
                        if *shutdown.borrow() {
                            info!("VMWriter flush loop stopping");
                            break;
                        }
                    }
                }
            }
        });

        info!(
            vm_url = %self.vm_url,
            flush_interval_ms = self.flush_interval.as_millis(),
            flush_threshold = self.flush_threshold,
            max_retries = self.max_retries,
            "VMWriter started"
        );
    }

    pub async fn stop(&self) {
        let _ = self.shutdown_tx.send(true);
        self.flush().await;
        info!("VMWriter stopped");
    }

    pub async fn add_samples(&self, samples: &[crate::HealthSample]) {
        if samples.is_empty() {
            info!("VMWriter add_samples: no samples to buffer");
            return;
        }

        let mut metric_counts: HashMap<String, usize> = HashMap::new();
        let mut source_counts: HashMap<String, usize> = HashMap::new();

        for sample in samples {
            let log_metric = if sample.metric_name.is_empty() {
                "<empty>"
            } else {
                &sample.metric_name
            };
            let log_source = if sample.source.is_empty() {
                "<empty>"
            } else {
                &sample.source
            };

            *metric_counts.entry(log_metric.to_string()).or_insert(0) += 1;
            *source_counts.entry(log_source.to_string()).or_insert(0) += 1;

            let mut labels: HashMap<String, String> = sample
                .labels
                .iter()
                .map(|(k, v)| (sanitize_label(k), sanitize_label(v)))
                .collect();
            labels.insert("source".to_string(), sanitize_label(&sample.source));

            let buffered = BufferedSample {
                timestamp_ms: sample.timestamp_ms,
                value: sample.value,
                labels,
            };

            let buffer_key = sample.metric_name.clone();
            let mut guard = self.state.lock().await;
            guard.buffer.entry(buffer_key).or_default().push(buffered);
            guard.accepted_samples += 1;
            let total: usize = guard.buffer.values().map(|v| v.len()).sum();
            if total >= self.flush_threshold {
                drop(guard);
                Self::do_flush(
                    &self.state,
                    &self.vm_url,
                    self.max_retries,
                    self.retry_backoff_base,
                    &self.client,
                )
                .await;
            }
        }

        let total_accepted = self.state.lock().await.accepted_samples;
        info!(
            buffered = samples.len(),
            total_accepted,
            metric_counts = %format_counts(&metric_counts, 80),
            source_counts = %format_counts(&source_counts, 80),
            "VMWriter buffered samples"
        );
    }

    pub async fn flush(&self) -> bool {
        Self::do_flush(
            &self.state,
            &self.vm_url,
            self.max_retries,
            self.retry_backoff_base,
            &self.client,
        )
        .await
    }

    async fn do_flush(
        state: &Arc<Mutex<WriterState>>,
        vm_url: &str,
        max_retries: u32,
        retry_backoff_base: Duration,
        client: &reqwest::Client,
    ) -> bool {
        let (payload, metric_counts, sample_count, flush_id) = {
            let mut guard = state.lock().await;
            if guard.buffer.is_empty() {
                return true;
            }
            let sample_count: usize = guard.buffer.values().map(|v| v.len()).sum();
            let metric_counts: HashMap<String, usize> = guard
                .buffer
                .iter()
                .map(|(k, v)| (k.clone(), v.len()))
                .collect();

            let mut lines = Vec::with_capacity(sample_count);
            for (metric_name, samples) in &guard.buffer {
                for sample in samples {
                    let mut metric_labels = serde_json::Map::new();
                    metric_labels.insert("__name__".to_string(), json!(metric_name));
                    for (k, v) in &sample.labels {
                        metric_labels.insert(k.clone(), json!(v));
                    }
                    let line = json!({
                        "metric": metric_labels,
                        "values": [sample.value],
                        "timestamps": [sample.timestamp_ms],
                    });
                    lines.push(line.to_string());
                }
            }
            guard.flush_count += 1;
            let flush_id = guard.flush_count;
            let payload = lines.join("\n");
            (payload, metric_counts, sample_count, flush_id)
        };

        info!(
            flush_id,
            samples = sample_count,
            metrics = metric_counts.len(),
            bytes = payload.len(),
            metric_counts = %format_counts(&metric_counts, 80),
            "VMWriter flush start"
        );

        let success =
            Self::post_to_vm(vm_url, &payload, max_retries, retry_backoff_base, client).await;

        if success {
            let mut guard = state.lock().await;
            guard.buffer.clear();
            info!(
                flush_id,
                samples = sample_count,
                metrics = metric_counts.len(),
                "VMWriter flush success"
            );
        } else {
            error!(
                flush_id,
                retained_samples = sample_count,
                metrics = metric_counts.len(),
                "VMWriter flush failed"
            );
        }
        success
    }

    async fn post_to_vm(
        vm_url: &str,
        payload: &str,
        max_retries: u32,
        retry_backoff_base: Duration,
        client: &reqwest::Client,
    ) -> bool {
        let url = format!("{vm_url}/api/v1/import");

        for attempt in 0..max_retries {
            let attempt_num = attempt + 1;
            let start = tokio::time::Instant::now();
            match client
                .post(&url)
                .header("Content-Type", "application/x-ndjson")
                .body(payload.to_string())
                .send()
                .await
            {
                Ok(resp) => {
                    let elapsed_ms = start.elapsed().as_millis();
                    let status = resp.status();
                    if status == reqwest::StatusCode::OK
                        || status == reqwest::StatusCode::NO_CONTENT
                    {
                        info!(
                            status = status.as_u16(),
                            bytes = payload.len(),
                            elapsed_ms,
                            attempt = attempt_num,
                            max_retries,
                            "VM import accepted"
                        );
                        return true;
                    }
                    let body = resp.text().await.unwrap_or_default();
                    warn!(
                        status = status.as_u16(),
                        bytes = payload.len(),
                        elapsed_ms,
                        attempt = attempt_num,
                        max_retries,
                        body = &body[..body.len().min(1000)],
                        "VM import rejected"
                    );
                }
                Err(e) => {
                    let elapsed_ms = start.elapsed().as_millis();
                    warn!(
                        bytes = payload.len(),
                        elapsed_ms,
                        attempt = attempt_num,
                        max_retries,
                        error = %e,
                        "VM import request failed"
                    );
                }
            }

            if attempt < max_retries - 1 {
                let backoff = retry_backoff_base * 2u32.pow(attempt);
                tokio::time::sleep(backoff).await;
            }
        }

        error!(max_retries, "Failed to write to VM after all attempts");
        false
    }
}
