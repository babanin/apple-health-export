import Foundation
import CoreLocation
import HealthKit

enum HealthKitError: Error {
    case notAvailable
    case authorizationDenied
    case queryFailed(String)
}

class HealthKitManager: @unchecked Sendable {
    private let healthStore = HKHealthStore()
    private let bloodPressureCorrelationId = "HKCorrelationTypeIdentifierBloodPressure"
    private let bloodPressureSystolicId = "HKQuantityTypeIdentifierBloodPressureSystolic"
    private let bloodPressureDiastolicId = "HKQuantityTypeIdentifierBloodPressureDiastolic"
    private let bloodPressureBackfillStartDate = Date(timeIntervalSince1970: 0)

    var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    func requestAuthorization() async throws -> Bool {
        guard isAvailable else { throw HealthKitError.notAvailable }

        AppLogger.shared.info("Requesting HealthKit authorization for \(HKMetricMapping.all.count) types")

        var typesToRead: Set<HKObjectType> = []
        for mapping in HKMetricMapping.all {
            if mapping.isCategory {
                if let categoryType = HKObjectType.categoryType(forIdentifier: HKCategoryTypeIdentifier(rawValue: mapping.hkTypeId)) {
                    typesToRead.insert(categoryType)
                }
            } else {
                if let quantityType = HKObjectType.quantityType(forIdentifier: HKQuantityTypeIdentifier(rawValue: mapping.hkTypeId)) {
                    typesToRead.insert(quantityType)
                }
            }
        }
        typesToRead.insert(HKWorkoutType.workoutType())
        typesToRead.insert(HKSeriesType.workoutRoute())

        return try await withCheckedThrowingContinuation { continuation in
            healthStore.requestAuthorization(toShare: nil, read: typesToRead) { success, error in
                if let error = error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: success)
                }
            }
        }
    }

    func fetchQuantitySamples(
        for hkTypeId: String,
        metricName: String,
        unit: String,
        from startDate: Date,
        to endDate: Date = Date()
    ) async throws -> [HealthMetricSample] {
        guard let quantityType = HKObjectType.quantityType(forIdentifier: HKQuantityTypeIdentifier(rawValue: hkTypeId)) else {
            return []
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: quantityType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sortDescriptor]) { _, samples, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }

                guard let quantitySamples = samples as? [HKQuantitySample] else {
                    continuation.resume(returning: [])
                    return
                }

                let hkUnit = self.unitFromString(unit)
                let result = quantitySamples.compactMap { sample -> HealthMetricSample? in
                    guard sample.quantity.is(compatibleWith: hkUnit) else {
                        AppLogger.shared.warning("Skipping \(metricName) sample: unit incompatible (\(sample.quantity))")
                        return nil
                    }
                    return HealthMetricSample(
                        metricName: metricName,
                        timestampMs: Int64(sample.startDate.timeIntervalSince1970 * 1000),
                        value: sample.quantity.doubleValue(for: hkUnit),
                        unit: unit,
                        source: sample.sourceRevision.source.name,
                        labels: self.labelsFromSample(sample)
                    )
                }
                continuation.resume(returning: result)
            }
            self.healthStore.execute(query)
        }
    }

    func fetchBloodPressureSamples(
        for hkTypeId: String,
        metricName: String,
        unit: String,
        from startDate: Date,
        to endDate: Date = Date()
    ) async throws -> [HealthMetricSample] {
        let effectiveStartDate = bloodPressureBackfillStartDate
        if startDate > effectiveStartDate {
            AppLogger.shared.info("\(metricName): forcing full blood pressure backfill from \(isoDate(effectiveStartDate)) instead of checkpoint \(isoDate(startDate))")
        }

        do {
            let samples = try await fetchBloodPressureCorrelationSamples(
                for: hkTypeId,
                metricName: metricName,
                unit: unit,
                from: effectiveStartDate,
                to: endDate
            )
            if !samples.isEmpty {
                return samples
            }
            AppLogger.shared.info("\(metricName): no samples from blood pressure correlation query; trying sample query over correlations")
        } catch {
            AppLogger.shared.debug("Blood pressure correlation query failed for \(metricName): \(error.localizedDescription)")
        }

        do {
            let samples = try await fetchBloodPressureSampleQuerySamples(
                for: hkTypeId,
                metricName: metricName,
                unit: unit,
                from: effectiveStartDate,
                to: endDate
            )
            if !samples.isEmpty {
                return samples
            }
            AppLogger.shared.info("\(metricName): no samples from blood pressure sample query; trying direct quantity query")
        } catch {
            AppLogger.shared.debug("Blood pressure sample query failed for \(metricName): \(error.localizedDescription)")
        }

        let quantitySamples = try await fetchQuantitySamples(
            for: hkTypeId,
            metricName: metricName,
            unit: unit,
            from: effectiveStartDate,
            to: endDate
        )
        AppLogger.shared.info("\(metricName): direct quantity query returned \(quantitySamples.count) samples")
        return quantitySamples
    }

    private func fetchBloodPressureCorrelationSamples(
        for hkTypeId: String,
        metricName: String,
        unit: String,
        from startDate: Date,
        to endDate: Date
    ) async throws -> [HealthMetricSample] {
        guard let correlationType = HKObjectType.correlationType(forIdentifier: HKCorrelationTypeIdentifier(rawValue: bloodPressureCorrelationId)),
              let quantityType = HKObjectType.quantityType(forIdentifier: HKQuantityTypeIdentifier(rawValue: hkTypeId)) else {
            return []
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKCorrelationQuery(type: correlationType, predicate: predicate, samplePredicates: nil) { _, correlations, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }

                let hkUnit = self.unitFromString(unit)
                let fetchedCorrelations = correlations ?? []
                AppLogger.shared.info("\(metricName): blood pressure correlation query returned \(fetchedCorrelations.count) correlations")
                let result = self.bloodPressureSamples(
                    from: fetchedCorrelations,
                    quantityType: quantityType,
                    metricName: metricName,
                    unit: unit,
                    hkUnit: hkUnit
                )
                continuation.resume(returning: result)
            }
            self.healthStore.execute(query)
        }
    }

    private func fetchBloodPressureSampleQuerySamples(
        for hkTypeId: String,
        metricName: String,
        unit: String,
        from startDate: Date,
        to endDate: Date
    ) async throws -> [HealthMetricSample] {
        guard let correlationType = HKObjectType.correlationType(forIdentifier: HKCorrelationTypeIdentifier(rawValue: bloodPressureCorrelationId)),
              let quantityType = HKObjectType.quantityType(forIdentifier: HKQuantityTypeIdentifier(rawValue: hkTypeId)) else {
            return []
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: correlationType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sortDescriptor]) { _, samples, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }

                let hkUnit = self.unitFromString(unit)
                let correlations = samples as? [HKCorrelation] ?? []
                AppLogger.shared.info("\(metricName): blood pressure sample query returned \(correlations.count) correlations")
                let result = self.bloodPressureSamples(
                    from: correlations,
                    quantityType: quantityType,
                    metricName: metricName,
                    unit: unit,
                    hkUnit: hkUnit
                )
                continuation.resume(returning: result)
            }
            self.healthStore.execute(query)
        }
    }

    private func bloodPressureSamples(
        from correlations: [HKCorrelation],
        quantityType: HKQuantityType,
        metricName: String,
        unit: String,
        hkUnit: HKUnit
    ) -> [HealthMetricSample] {
        correlations.flatMap { correlation -> [HealthMetricSample] in
            correlation.objects(for: quantityType).compactMap { object -> HealthMetricSample? in
                guard let sample = object as? HKQuantitySample else { return nil }
                guard sample.quantity.is(compatibleWith: hkUnit) else {
                    AppLogger.shared.warning("Skipping \(metricName) sample: unit incompatible (\(sample.quantity))")
                    return nil
                }
                return HealthMetricSample(
                    metricName: metricName,
                    timestampMs: Int64(sample.startDate.timeIntervalSince1970 * 1000),
                    value: sample.quantity.doubleValue(for: hkUnit),
                    unit: unit,
                    source: sample.sourceRevision.source.name,
                    labels: labelsFromSample(sample)
                )
            }
        }
    }

    func fetchCategorySamples(
        for hkTypeId: String,
        metricName: String,
        from startDate: Date,
        to endDate: Date = Date()
    ) async throws -> [HealthMetricSample] {
        guard let categoryType = HKObjectType.categoryType(forIdentifier: HKCategoryTypeIdentifier(rawValue: hkTypeId)) else {
            return []
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: categoryType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sortDescriptor]) { _, samples, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }

                guard let categorySamples = samples as? [HKCategorySample] else {
                    continuation.resume(returning: [])
                    return
                }

                let result = categorySamples.flatMap { sample -> [HealthMetricSample] in
                    let duration = sample.endDate.timeIntervalSince(sample.startDate)
                    let bucketSeconds = 60.0
                    var resultSamples: [HealthMetricSample] = []

                    let numBuckets = max(1, Int(ceil(duration / bucketSeconds)))
                    for i in 0..<numBuckets {
                        let bucketStart = sample.startDate.addingTimeInterval(Double(i) * bucketSeconds)
                        let bucketTs = Int64(bucketStart.timeIntervalSince1970 * 1000)
                        resultSamples.append(HealthMetricSample(
                            metricName: metricName,
                            timestampMs: bucketTs,
                            value: Double(sample.value),
                            unit: "",
                            source: sample.sourceRevision.source.name,
                            labels: ["stage": self.categoryValueName(for: hkTypeId, value: sample.value)]
                        ))
                    }
                    return resultSamples
                }
                continuation.resume(returning: result)
            }
            self.healthStore.execute(query)
        }
    }

    private func fetchWorkoutRoutes(for workout: HKWorkout) async throws -> [HKWorkoutRoute] {
        let routeType = HKSeriesType.workoutRoute()
        let predicate = HKQuery.predicateForObjects(from: workout)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: routeType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }

                continuation.resume(returning: samples as? [HKWorkoutRoute] ?? [])
            }
            self.healthStore.execute(query)
        }
    }

    private func fetchRouteLocations(for route: HKWorkoutRoute) async throws -> [CLLocation] {
        let accumulator = LocationAccumulator()

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKWorkoutRouteQuery(route: route) { _, locations, done, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }

                accumulator.append(locations ?? [])
                if done {
                    continuation.resume(returning: accumulator.locations)
                }
            }
            self.healthStore.execute(query)
        }
    }

    private func routeSamples(for workout: HKWorkout, labels: [String: String], source: String, from startDate: Date) async -> [HealthMetricSample] {
        do {
            let routes = try await fetchWorkoutRoutes(for: workout)
            var samples: [HealthMetricSample] = []

            for route in routes {
                let locations = try await fetchRouteLocations(for: route)
                for location in locations where location.timestamp >= startDate {
                    let timestampMs = Int64(location.timestamp.timeIntervalSince1970 * 1000)
                    samples.append(HealthMetricSample(
                        metricName: "apple_health_workout_route_latitude_degrees",
                        timestampMs: timestampMs,
                        value: location.coordinate.latitude,
                        unit: "deg",
                        source: source,
                        labels: labels
                    ))
                    samples.append(HealthMetricSample(
                        metricName: "apple_health_workout_route_longitude_degrees",
                        timestampMs: timestampMs,
                        value: location.coordinate.longitude,
                        unit: "deg",
                        source: source,
                        labels: labels
                    ))
                    if location.verticalAccuracy >= 0 {
                        samples.append(HealthMetricSample(
                            metricName: "apple_health_workout_route_altitude_m",
                            timestampMs: timestampMs,
                            value: location.altitude,
                            unit: "m",
                            source: source,
                            labels: labels
                        ))
                    }
                    if location.speed >= 0 {
                        samples.append(HealthMetricSample(
                            metricName: "apple_health_workout_route_speed_m_per_sec",
                            timestampMs: timestampMs,
                            value: location.speed,
                            unit: "m/s",
                            source: source,
                            labels: labels
                        ))
                    }
                    if location.horizontalAccuracy >= 0 {
                        samples.append(HealthMetricSample(
                            metricName: "apple_health_workout_route_horizontal_accuracy_m",
                            timestampMs: timestampMs,
                            value: location.horizontalAccuracy,
                            unit: "m",
                            source: source,
                            labels: labels
                        ))
                    }
                }
            }

            if !samples.isEmpty {
                AppLogger.shared.info("Workout route \(workout.uuid.uuidString): +\(samples.count) samples")
            }
            return samples
        } catch {
            AppLogger.shared.debug("Skipping workout route \(workout.uuid.uuidString): \(error.localizedDescription)")
            return []
        }
    }

    func fetchWorkoutSamples(
        from startDate: Date,
        routeStartDate: Date,
        to endDate: Date = Date()
    ) async throws -> [HealthMetricSample] {
        let workoutType = HKWorkoutType.workoutType()
        let earliestStartDate = min(startDate, routeStartDate)
        let predicate = HKQuery.predicateForSamples(withStart: earliestStartDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)

        let workouts: [HKWorkout] = try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: workoutType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sortDescriptor]) { _, samples, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }

                continuation.resume(returning: samples as? [HKWorkout] ?? [])
            }
            self.healthStore.execute(query)
        }

        var result: [HealthMetricSample] = []
        for workout in workouts {
            let timestampMs = Int64(workout.startDate.timeIntervalSince1970 * 1000)
            let type = workoutTypeName(workout.workoutActivityType)
            var labels = labelsFromWorkout(workout)
            labels["workout_id"] = workout.uuid.uuidString
            labels["type"] = type
            labels["start_date"] = isoDate(workout.startDate)
            labels["end_date"] = isoDate(workout.endDate)

            if workout.startDate >= startDate {
                result.append(HealthMetricSample(
                    metricName: "apple_health_workout_duration_seconds",
                    timestampMs: timestampMs,
                    value: workout.duration,
                    unit: "s",
                    source: workout.sourceRevision.source.name,
                    labels: labels
                ))

                if let distance = workout.totalDistance?.doubleValue(for: .meter()) {
                    result.append(HealthMetricSample(
                        metricName: "apple_health_workout_distance_m",
                        timestampMs: timestampMs,
                        value: distance,
                        unit: "m",
                        source: workout.sourceRevision.source.name,
                        labels: labels
                    ))

                    if workout.duration > 0 {
                        result.append(HealthMetricSample(
                            metricName: "apple_health_workout_avg_speed_m_per_sec",
                            timestampMs: timestampMs,
                            value: distance / workout.duration,
                            unit: "m/s",
                            source: workout.sourceRevision.source.name,
                            labels: labels
                        ))
                    }
                }

                let activeEnergyType = HKQuantityType(.activeEnergyBurned)
                if let energy = workout.statistics(for: activeEnergyType)?.sumQuantity()?.doubleValue(for: .kilocalorie()) {
                    result.append(HealthMetricSample(
                        metricName: "apple_health_workout_energy_kcal",
                        timestampMs: timestampMs,
                        value: energy,
                        unit: "kcal",
                        source: workout.sourceRevision.source.name,
                        labels: labels
                    ))
                }

                if let heartRate = await averageHeartRate(for: workout) {
                    result.append(HealthMetricSample(
                        metricName: "apple_health_workout_heart_rate_bpm",
                        timestampMs: timestampMs,
                        value: heartRate,
                        unit: "count/min",
                        source: workout.sourceRevision.source.name,
                        labels: labels
                    ))
                }
            }

            if workout.endDate >= routeStartDate {
                result.append(contentsOf: await routeSamples(
                    for: workout,
                    labels: labels,
                    source: workout.sourceRevision.source.name,
                    from: routeStartDate
                ))
            }
        }

        return result
    }

    func fetchSamples(for mapping: HKMetricMapping, from startDate: Date) async throws -> [HealthMetricSample] {
        if mapping.isCategory {
            return try await fetchCategorySamples(
                for: mapping.hkTypeId,
                metricName: mapping.metricName,
                from: startDate
            )
        }

        if mapping.hkTypeId == bloodPressureSystolicId || mapping.hkTypeId == bloodPressureDiastolicId {
            return try await fetchBloodPressureSamples(
                for: mapping.hkTypeId,
                metricName: mapping.metricName,
                unit: mapping.unit,
                from: startDate
            )
        }

        return try await fetchQuantitySamples(
            for: mapping.hkTypeId,
            metricName: mapping.metricName,
            unit: mapping.unit,
            from: startDate
        )
    }

    func fetchAllMetrics(progress: (@MainActor (HealthKitFetchProgress) -> Void)? = nil) async throws -> [HealthMetricSample] {
        var allSamples: [HealthMetricSample] = []
        let checkpointManager = CheckpointManager.shared
        AppLogger.shared.info("Fetching all metrics (\(HKMetricMapping.all.count) types)...")

        let totalMetrics = HKMetricMapping.all.count + 1
        for (index, mapping) in HKMetricMapping.all.enumerated() {
            let startDate = checkpointManager.getStartTime(for: mapping.metricName)
            AppLogger.shared.info("[\(index + 1)/\(totalMetrics)] Fetching \(mapping.metricName)...")

            do {
                let samples = try await fetchSamples(for: mapping, from: startDate)
                allSamples.append(contentsOf: samples)
                let remaining = totalMetrics - (index + 1)
                AppLogger.shared.info("[\(index + 1)/\(totalMetrics)] \(mapping.metricName): +\(samples.count) samples (total: \(allSamples.count), \(remaining) metrics left)")
                await progress?(HealthKitFetchProgress(
                    completedMetrics: index + 1,
                    totalMetrics: totalMetrics,
                    fetchedSamples: allSamples.count,
                    currentMetricName: mapping.metricName
                ))
            } catch {
                AppLogger.shared.error("Failed to fetch \(mapping.metricName): \(error.localizedDescription)")
                await progress?(HealthKitFetchProgress(
                    completedMetrics: index + 1,
                    totalMetrics: totalMetrics,
                    fetchedSamples: allSamples.count,
                    currentMetricName: mapping.metricName
                ))
            }
        }

        let workoutStartDate = checkpointManager.getStartTime(for: "apple_health_workout_duration_seconds")
        let workoutRouteStartDate = checkpointManager.getStartTime(for: "apple_health_workout_route_latitude_degrees")
        AppLogger.shared.info("Fetching workouts...")
        do {
            let workoutSamples = try await fetchWorkoutSamples(from: workoutStartDate, routeStartDate: workoutRouteStartDate)
            allSamples.append(contentsOf: workoutSamples)
            AppLogger.shared.info("Workouts: +\(workoutSamples.count) samples (total: \(allSamples.count))")
        } catch {
            AppLogger.shared.error("Failed to fetch workouts: \(error.localizedDescription)")
        }
        await progress?(HealthKitFetchProgress(
            completedMetrics: totalMetrics,
            totalMetrics: totalMetrics,
            fetchedSamples: allSamples.count,
            currentMetricName: "Workouts"
        ))

        return allSamples
    }

    private func unitFromString(_ unitStr: String) -> HKUnit {
        switch unitStr {
        case "count/min": return HKUnit.count().unitDivided(by: .minute())
        case "ms": return HKUnit.secondUnit(with: .milli)
        case "percent": return HKUnit.percent()
        case "mmHg": return HKUnit.millimeterOfMercury()
        case "mL/kg·min": return HKUnit.literUnit(with: .milli).unitDivided(by: HKUnit.gramUnit(with: .kilo)).unitDivided(by: .minute())
        case "count": return HKUnit.count()
        case "m": return HKUnit.meter()
        case "kcal": return .kilocalorie()
        case "min": return .minute()
        case "kg": return HKUnit.gramUnit(with: .kilo)
        case "kg/m²": return HKUnit.gramUnit(with: .kilo).unitDivided(by: HKUnit.meter().unitMultiplied(by: HKUnit.meter()))
        case "mg/dL": return HKUnit.gramUnit(with: .milli).unitDivided(by: HKUnit.literUnit(with: .deci))
        case "IU": return .internationalUnit()
        case "m/s": return HKUnit.meter().unitDivided(by: .second())
        case "s": return .second()
        case "°C": return .degreeCelsius()
        case "dB": return HKUnit.decibelAWeightedSoundPressureLevel()
        case "g": return HKUnit.gram()
        case "mg": return HKUnit.gramUnit(with: .milli)
        case "mL": return HKUnit.literUnit(with: .milli)
        case "index": return HKUnit.count()
        case "L": return .liter()
        case "L/s": return HKUnit.liter().unitDivided(by: .second())
        case "breaths/min": return HKUnit.count().unitDivided(by: .minute())
        case "µg/m³": return HKUnit.gramUnit(with: .micro).unitDivided(by: HKUnit(from: "m^3"))
        default: return HKUnit.count()
        }
    }

    private func labelsFromSample(_ sample: HKQuantitySample) -> [String: String] {
        var labels: [String: String] = [:]
        if let deviceName = sample.device?.name {
            labels["device"] = deviceName
        }
        return labels
    }

    private func labelsFromWorkout(_ workout: HKWorkout) -> [String: String] {
        var labels: [String: String] = [:]
        if let deviceName = workout.device?.name {
            labels["device"] = deviceName
        }
        if let isIndoor = workout.metadata?[HKMetadataKeyIndoorWorkout] as? Bool {
            labels["environment"] = isIndoor ? "indoor" : "outdoor"
        }
        return labels
    }

    private func averageHeartRate(for workout: HKWorkout) async -> Double? {
        guard let heartRateType = HKObjectType.quantityType(forIdentifier: .heartRate) else {
            return nil
        }

        let predicate = HKQuery.predicateForSamples(withStart: workout.startDate, end: workout.endDate, options: [.strictStartDate, .strictEndDate])
        let unit = HKUnit.count().unitDivided(by: .minute())

        return await withCheckedContinuation { continuation in
            let query = HKStatisticsQuery(quantityType: heartRateType, quantitySamplePredicate: predicate, options: .discreteAverage) { _, statistics, error in
                if let error = error {
                    AppLogger.shared.debug("Skipping workout heart rate: \(error.localizedDescription)")
                    continuation.resume(returning: nil)
                    return
                }

                continuation.resume(returning: statistics?.averageQuantity()?.doubleValue(for: unit))
            }
            self.healthStore.execute(query)
        }
    }

    private func workoutTypeName(_ type: HKWorkoutActivityType) -> String {
        switch type {
        case .cycling: return "cycling"
        case .running: return "running"
        case .walking: return "walking"
        case .swimming: return "swimming"
        case .hiking: return "hiking"
        case .yoga: return "yoga"
        case .traditionalStrengthTraining: return "strength_training"
        case .functionalStrengthTraining: return "functional_strength_training"
        case .highIntensityIntervalTraining: return "hiit"
        case .mixedCardio: return "mixed_cardio"
        case .elliptical: return "elliptical"
        case .rowing: return "rowing"
        case .stairClimbing: return "stair_climbing"
        case .soccer: return "soccer"
        case .tennis: return "tennis"
        case .other: return "other"
        default: return "activity_\(type.rawValue)"
        }
    }

    private func isoDate(_ date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
    }

    private func categoryValueName(for hkTypeId: String, value: Int) -> String {
        switch hkTypeId {
        case "HKCategoryTypeIdentifierSleepAnalysis":
            switch value {
            case 0: return "InBed"
            case 1: return "Asleep"
            case 2: return "Awake"
            case 3: return "Core"
            case 4: return "Deep"
            case 5: return "REM"
            default: return "Unknown"
            }
        case "HKCategoryTypeIdentifierAppleStandHour":
            return value == 0 ? "NotStood" : "Stood"
        case "HKCategoryTypeIdentifierMenstrualFlow":
            switch value {
            case 0: return "Unspecified"
            case 1: return "Light"
            case 2: return "Medium"
            case 3: return "Heavy"
            case 4: return "None"
            default: return "Unknown"
            }
        default: return String(value)
        }
    }
}

struct HealthMetricSample: Sendable {
    let metricName: String
    let timestampMs: Int64
    let value: Double
    let unit: String
    let source: String
    let labels: [String: String]
}

final class LocationAccumulator: @unchecked Sendable {
    private let lock = NSLock()
    private var storedLocations: [CLLocation] = []

    var locations: [CLLocation] {
        lock.lock()
        defer { lock.unlock() }
        return storedLocations
    }

    func append(_ locations: [CLLocation]) {
        lock.lock()
        storedLocations.append(contentsOf: locations)
        lock.unlock()
    }
}
