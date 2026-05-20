import json
import logging
import time
import threading
from typing import Dict, List, Optional
from collections import Counter, defaultdict

import requests

from health_export_pb2 import HealthSample

logger = logging.getLogger(__name__)
MAX_LOG_ITEMS = 80

PROMETHEUS_NAME_REGEX = r"[a-zA-Z_:][a-zA-Z0-9_:]*"

LABEL_SANITIZATION_MAP = {
    "/": "_",
    ".": "_",
    "-": "_",
    " ": "_",
    "(": "",
    ")": "",
}


def sanitize_label(value: str) -> str:
    for char, replacement in LABEL_SANITIZATION_MAP.items():
        value = value.replace(char, replacement)
    return value


def format_counts(counts: Counter[str], limit: int = MAX_LOG_ITEMS) -> str:
    items = sorted(counts.items())
    visible = items[:limit]
    formatted = ", ".join(f"{name}={count}" for name, count in visible)
    if len(items) > limit:
        formatted += f", ... +{len(items) - limit} more"
    return formatted or "none"


class VMWriter:
    def __init__(
        self,
        vm_url: str = "http://localhost:8428",
        flush_interval: float = 1.0,
        flush_threshold: int = 5000,
        max_retries: int = 5,
        retry_backoff_base: float = 0.5,
    ):
        self.vm_url = vm_url.rstrip("/")
        self.flush_interval = flush_interval
        self.flush_threshold = flush_threshold
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self._buffer: Dict[str, List] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._flush_thread: Optional[threading.Thread] = None
        self._running = False
        self._flush_count = 0
        self._accepted_samples = 0

    def start(self):
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        logger.info(
            "VMWriter started vm_url=%s flush_interval=%.3fs flush_threshold=%d max_retries=%d",
            self.vm_url, self.flush_interval, self.flush_threshold, self.max_retries,
        )

    def stop(self):
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
        self.flush()
        logger.info("VMWriter stopped")

    def _flush_loop(self):
        while self._running:
            time.sleep(self.flush_interval)
            if time.time() - self._last_flush >= self.flush_interval:
                self.flush()

    def add_sample(
        self,
        metric_name: str,
        timestamp_ms: int,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        sample = {
            "metric_name": metric_name,
            "timestamp_ms": timestamp_ms,
            "value": value,
            "labels": labels or {},
        }
        with self._lock:
            self._buffer[metric_name].append(sample)
            total = sum(len(v) for v in self._buffer.values())
            if total >= self.flush_threshold:
                self._flush_internal()

    def add_samples(self, samples: List[HealthSample]) -> None:
        if not samples:
            logger.info("VMWriter add_samples: no samples to buffer")
            return

        metric_counts: Counter[str] = Counter(sample.metric_name or "<empty>" for sample in samples)
        source_counts: Counter[str] = Counter(sample.source or "<empty>" for sample in samples)
        for sample in samples:
            metric_name = sample.metric_name
            labels = dict(sample.labels)
            labels["source"] = sample.source
            self.add_sample(
                metric_name=metric_name,
                timestamp_ms=sample.timestamp_ms,
                value=sample.value,
                labels=labels,
            )
        self._accepted_samples += len(samples)
        logger.info(
            "VMWriter buffered samples=%d total_accepted=%d metric_counts=%s source_counts=%s",
            len(samples),
            self._accepted_samples,
            format_counts(metric_counts),
            format_counts(source_counts),
        )

    def flush(self) -> bool:
        with self._lock:
            return self._flush_internal()

    def _flush_internal(self) -> bool:
        if not self._buffer:
            return True

        lines = []
        sample_count = sum(len(samples) for samples in self._buffer.values())
        metric_counts = Counter({metric_name: len(samples) for metric_name, samples in self._buffer.items()})
        for metric_name, samples in self._buffer.items():
            for sample in samples:
                metric_labels = {"__name__": metric_name}
                for k, v in sample["labels"].items():
                    metric_labels[sanitize_label(k)] = sanitize_label(v)
                line = json.dumps({
                    "metric": metric_labels,
                    "values": [sample["value"]],
                    "timestamps": [sample["timestamp_ms"]],
                })
                lines.append(line)

        payload = "\n".join(lines)
        self._flush_count += 1
        logger.info(
            "VMWriter flush start flush_id=%d samples=%d metrics=%d bytes=%d metric_counts=%s",
            self._flush_count,
            sample_count,
            len(metric_counts),
            len(payload),
            format_counts(metric_counts),
        )
        success = self._post_to_vm(payload)

        if success:
            self._buffer.clear()
            self._last_flush = time.time()
            logger.info(
                "VMWriter flush success flush_id=%d samples=%d metrics=%d",
                self._flush_count, sample_count, len(metric_counts),
            )
        else:
            logger.error(
                "VMWriter flush failed flush_id=%d retained_samples=%d metrics=%d",
                self._flush_count, sample_count, len(metric_counts),
            )
        return success

    def _post_to_vm(self, payload: str) -> bool:
        url = f"{self.vm_url}/api/v1/import"
        for attempt in range(self.max_retries):
            attempt_start = time.monotonic()
            try:
                resp = requests.post(
                    url,
                    data=payload,
                    headers={"Content-Type": "application/x-ndjson"},
                    timeout=30,
                )
                elapsed_ms = (time.monotonic() - attempt_start) * 1000
                if resp.status_code == 204 or resp.status_code == 200:
                    logger.info(
                        "VM import accepted status=%d bytes=%d elapsed_ms=%.1f attempt=%d/%d",
                        resp.status_code, len(payload), elapsed_ms, attempt + 1, self.max_retries,
                    )
                    return True
                logger.warning(
                    "VM import rejected status=%d bytes=%d elapsed_ms=%.1f attempt=%d/%d body=%s",
                    resp.status_code, len(payload), elapsed_ms, attempt + 1, self.max_retries, resp.text[:1000],
                )
            except requests.RequestException as e:
                elapsed_ms = (time.monotonic() - attempt_start) * 1000
                logger.warning(
                    "VM import request failed bytes=%d elapsed_ms=%.1f attempt=%d/%d error=%s",
                    len(payload), elapsed_ms, attempt + 1, self.max_retries, e,
                )

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_backoff_base * (2 ** attempt))

        logger.error("Failed to write to VM after %d attempts", self.max_retries)
        return False
