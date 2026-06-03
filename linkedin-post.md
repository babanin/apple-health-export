# LinkedIn Post

---

For almost a decade, Apple Health has been collecting intimate data about my body — heart rate, sleep, blood glucose, VO₂ max, steps, workouts, and more. But the data stayed in a silo. Apple gives you an encrypted export, some charts in the Health app, and that's it. You can't query it, join it, or put it on a dashboard alongside other metrics.

That bothered me. So I built something.

**Apple Health Export** is an open-source project that streams 52 HealthKit metrics from your iPhone to a local Grafana dashboard — over your Wi-Fi, through a Rust gRPC gateway, into Victoria Metrics. All running on your Mac. No cloud, no third party, no subscription.

I chose this approach deliberately. Your health data is the most personal data you own. A SaaS solution would mean sending heart rate variability, blood glucose, and sleep patterns to someone else's server — trusting their security, their privacy policy, their legal jurisdiction. Even with encryption, you're trusting a third party with metadata, access patterns, and attack surface you don't control.

This project runs entirely on your local network. The iOS app sends data to a gateway on your Mac via plaintext HTTP/2 (you could add TLS). The gateway buffers and flushes to Victoria Metrics in the same Docker Compose stack. Nothing leaves your home network unless you choose to expose it.

The architecture is straightforward:
- **Swift/SwiftUI** iOS app reads HealthKit samples with per-metric checkpointing (only new data since last sync)
- **Rust gRPC gateway** (tonic + tokio) receives batches, writes NDJSON to Victoria Metrics
- **Victoria Metrics** stores everything locally in the Docker volume
- **Grafana** auto-provisioned with curated dashboards for every metric

Checkpoints are stored on both sides — the phone remembers what it sent, the gateway deduplicates. Sync is incremental and resumable.

The project is MIT-licensed and lives at github.com/babanin/apple-health-export. Contributions, issues, and ideas are welcome. If you've been sitting on years of HealthKit data and wishing you could do something with it, this is for you.

Your health data is yours. Keep it that way.
