import Foundation

struct DemoDataManager {
    static let shared = DemoDataManager()

    private init() {}

    func generateDemoSamples() -> [HealthMetricSample] {
        var samples: [HealthMetricSample] = []
        let now = Date()
        let startTime = now.addingTimeInterval(-3600 * 24)

        let metrics: [(name: String, values: [Double], unit: String)] = [
            ("apple_health_heart_rate_bpm", [72, 68, 75, 80, 65, 70, 73, 66, 78, 71], "bpm"),
            ("apple_health_steps_total", [150, 200, 180, 350, 120, 90, 250, 310, 175, 220], "count"),
            ("apple_health_active_energy_burned_kcal", [85, 120, 95, 210, 55, 40, 145, 180, 100, 130], "kcal"),
            ("apple_health_oxygen_saturation_percent", [98, 97, 99, 98, 97, 99, 98, 97, 98, 99], "percent"),
            ("apple_health_resting_heart_rate_bpm", [58, 60, 56, 62, 57, 59, 55, 61, 58, 57], "bpm"),
            ("apple_health_body_mass_kg", [75.3, 75.1, 75.4, 74.9, 75.2, 75.0, 75.3, 75.1, 75.2, 75.0], "kg"),
            ("apple_health_distance_walking_running_m", [1200, 1800, 1500, 3000, 800, 600, 2200, 2800, 1400, 1900], "m"),
            ("apple_health_flights_climbed_total", [2, 3, 1, 5, 1, 0, 4, 6, 2, 3], "count"),
            ("apple_health_blood_pressure_systolic_mmhg", [122, 118, 124, 121, 119, 123, 120, 117, 125, 121], "mmHg"),
            ("apple_health_blood_pressure_diastolic_mmhg", [78, 76, 80, 77, 75, 79, 76, 74, 81, 77], "mmHg"),
            ("apple_health_blood_glucose_mg_dl", [95, 88, 102, 110, 85, 92, 98, 105, 90, 94], "mg/dL"),
            ("apple_health_sleep_duration_seconds", [27000, 25200, 28800, 26100, 27900, 25200, 27000, 28800, 26100, 27900], "s"),
        ]

        for metric in metrics {
            for (i, value) in metric.values.enumerated() {
                let timestamp = Int64(startTime.addingTimeInterval(Double(i * 3600)).timeIntervalSince1970 * 1000)
                samples.append(HealthMetricSample(
                    metricName: metric.name,
                    timestampMs: timestamp,
                    value: value,
                    unit: metric.unit,
                    source: "Demo Device",
                    labels: ["source": "demo"]
                ))
            }
        }

        for i in 0..<60 {
            let timestamp = Int64(startTime.addingTimeInterval(Double(i * 60)).timeIntervalSince1970 * 1000)
            let stages = ["Deep", "REM", "Core", "Awake"]
            let stage = stages[i % stages.count]
            samples.append(HealthMetricSample(
                metricName: "apple_health_sleep_stage",
                timestampMs: timestamp,
                value: Double(i % 4),
                unit: "",
                source: "Demo Device",
                labels: ["stage": stage]
            ))
        }

        let workoutTimestamp = Int64(startTime.addingTimeInterval(3600 * 12).timeIntervalSince1970 * 1000)
        let workoutId = UUID().uuidString
        let workoutLabels = [
            "type": "cycling",
            "environment": "outdoor",
            "device": "Demo Watch",
            "workout_id": workoutId,
            "start_date": ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: Double(workoutTimestamp) / 1000.0)),
            "end_date": ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: Double(workoutTimestamp) / 1000.0 + 3600)),
        ]
        samples.append(HealthMetricSample(
            metricName: "apple_health_workout_duration_seconds",
            timestampMs: workoutTimestamp,
            value: 3600,
            unit: "s",
            source: "Demo Device",
            labels: workoutLabels
        ))
        samples.append(HealthMetricSample(
            metricName: "apple_health_workout_distance_m",
            timestampMs: workoutTimestamp,
            value: 22000,
            unit: "m",
            source: "Demo Device",
            labels: workoutLabels
        ))
        samples.append(HealthMetricSample(
            metricName: "apple_health_workout_avg_speed_m_per_sec",
            timestampMs: workoutTimestamp,
            value: 6.11,
            unit: "m/s",
            source: "Demo Device",
            labels: workoutLabels
        ))
        samples.append(HealthMetricSample(
            metricName: "apple_health_workout_energy_kcal",
            timestampMs: workoutTimestamp,
            value: 620,
            unit: "kcal",
            source: "Demo Device",
            labels: workoutLabels
        ))
        samples.append(HealthMetricSample(
            metricName: "apple_health_workout_heart_rate_bpm",
            timestampMs: workoutTimestamp,
            value: 142,
            unit: "count/min",
            source: "Demo Device",
            labels: workoutLabels
        ))
        let route = [
            (lat: 52.5200, lon: 13.4050, altitude: 34.0, speed: 5.8),
            (lat: 52.5212, lon: 13.4090, altitude: 36.0, speed: 6.2),
            (lat: 52.5230, lon: 13.4140, altitude: 38.0, speed: 6.4),
            (lat: 52.5250, lon: 13.4200, altitude: 37.0, speed: 5.9),
            (lat: 52.5270, lon: 13.4270, altitude: 35.0, speed: 6.1),
        ]
        for (index, point) in route.enumerated() {
            let timestamp = workoutTimestamp + Int64(index * 60_000)
            samples.append(HealthMetricSample(
                metricName: "apple_health_workout_route_latitude_degrees",
                timestampMs: timestamp,
                value: point.lat,
                unit: "deg",
                source: "Demo Device",
                labels: workoutLabels
            ))
            samples.append(HealthMetricSample(
                metricName: "apple_health_workout_route_longitude_degrees",
                timestampMs: timestamp,
                value: point.lon,
                unit: "deg",
                source: "Demo Device",
                labels: workoutLabels
            ))
            samples.append(HealthMetricSample(
                metricName: "apple_health_workout_route_altitude_m",
                timestampMs: timestamp,
                value: point.altitude,
                unit: "m",
                source: "Demo Device",
                labels: workoutLabels
            ))
            samples.append(HealthMetricSample(
                metricName: "apple_health_workout_route_speed_m_per_sec",
                timestampMs: timestamp,
                value: point.speed,
                unit: "m/s",
                source: "Demo Device",
                labels: workoutLabels
            ))
            samples.append(HealthMetricSample(
                metricName: "apple_health_workout_route_horizontal_accuracy_m",
                timestampMs: timestamp,
                value: 8,
                unit: "m",
                source: "Demo Device",
                labels: workoutLabels
            ))
        }

        return samples.shuffled()
    }
}
