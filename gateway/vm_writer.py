import json
import logging
import time
import threading
from typing import Dict, List, Optional
from collections import defaultdict

import requests

from health_export_pb2 import HealthSample

logger = logging.getLogger(__name__)

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

    def start(self):
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        logger.info("VMWriter started")

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

    def flush(self) -> bool:
        with self._lock:
            return self._flush_internal()

    def _flush_internal(self) -> bool:
        if not self._buffer:
            return True

        lines = []
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
        success = self._post_to_vm(payload)

        if success:
            self._buffer.clear()
            self._last_flush = time.time()
        return success

    def _post_to_vm(self, payload: str) -> bool:
        url = f"{self.vm_url}/api/v1/import"
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    url,
                    data=payload,
                    headers={"Content-Type": "application/x-ndjson"},
                    timeout=30,
                )
                if resp.status_code == 204 or resp.status_code == 200:
                    logger.debug("Successfully wrote %d bytes to VM", len(payload))
                    return True
                logger.warning(
                    "VM returned status %d: %s", resp.status_code, resp.text
                )
            except requests.RequestException as e:
                logger.warning("VM request failed (attempt %d/%d): %s", attempt + 1, self.max_retries, e)

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_backoff_base * (2 ** attempt))

        logger.error("Failed to write to VM after %d attempts", self.max_retries)
        return False