import Foundation
import HealthKit

struct HKMetricMapping {
    let hkTypeId: String
    let metricName: String
    let unit: String
    let isCategory: Bool

    static let all: [HKMetricMapping] = [
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierHeartRate", metricName: "apple_health_heart_rate_bpm", unit: "count/min", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierRestingHeartRate", metricName: "apple_health_resting_heart_rate_bpm", unit: "count/min", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierWalkingHeartRateAverage", metricName: "apple_health_walking_heart_rate_avg_bpm", unit: "count/min", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierHeartRateVariabilitySDNN", metricName: "apple_health_heart_rate_variability_ms", unit: "ms", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierOxygenSaturation", metricName: "apple_health_oxygen_saturation_percent", unit: "percent", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierBloodPressureSystolic", metricName: "apple_health_blood_pressure_systolic_mmhg", unit: "mmHg", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierBloodPressureDiastolic", metricName: "apple_health_blood_pressure_diastolic_mmhg", unit: "mmHg", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierVO2Max", metricName: "apple_health_vo2_max_ml_kg_min", unit: "mL/kg·min", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierStepCount", metricName: "apple_health_steps_total", unit: "count", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierDistanceWalkingRunning", metricName: "apple_health_distance_walking_running_m", unit: "m", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierDistanceCycling", metricName: "apple_health_distance_cycling_m", unit: "m", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierDistanceSwimming", metricName: "apple_health_distance_swimming_m", unit: "m", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierFlightsClimbed", metricName: "apple_health_flights_climbed_total", unit: "count", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierActiveEnergyBurned", metricName: "apple_health_active_energy_burned_kcal", unit: "kcal", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierBasalEnergyBurned", metricName: "apple_health_basal_energy_burned_kcal", unit: "kcal", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierAppleExerciseTime", metricName: "apple_health_exercise_time_min", unit: "min", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierAppleStandTime", metricName: "apple_health_stand_time_min", unit: "min", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierAppleMoveTime", metricName: "apple_health_move_time_min", unit: "min", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierStepCountPerMin", metricName: "apple_health_step_count_per_min", unit: "count/min", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierBodyMass", metricName: "apple_health_body_mass_kg", unit: "kg", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierBodyMassIndex", metricName: "apple_health_body_mass_index", unit: "kg/m²", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierBodyFatPercentage", metricName: "apple_health_body_fat_percent", unit: "percent", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierLeanBodyMass", metricName: "apple_health_lean_body_mass_kg", unit: "kg", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierHeight", metricName: "apple_health_height_m", unit: "m", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierWaistCircumference", metricName: "apple_health_waist_circumference_m", unit: "m", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierRespiratoryRate", metricName: "apple_health_respiratory_rate_per_min", unit: "breaths/min", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierBloodGlucose", metricName: "apple_health_blood_glucose_mg_dl", unit: "mg/dL", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierInsulinDelivery", metricName: "apple_health_insulin_delivery_iu", unit: "IU", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierWalkingSpeed", metricName: "apple_health_walking_speed_m_per_sec", unit: "m/s", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierWalkingStepLength", metricName: "apple_health_walking_step_length_m", unit: "m", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierWalkingAsymmetryPercentage", metricName: "apple_health_walking_asymmetry_percent", unit: "percent", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage", metricName: "apple_health_walking_double_support_percent", unit: "percent", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierStepLength", metricName: "apple_health_step_length_m", unit: "m", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierUVIndex", metricName: "apple_health_uv_index", unit: "index", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierAppleWalkingSteadiness", metricName: "apple_health_walking_steadiness_percent", unit: "percent", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierNumberOfTimesFallen", metricName: "apple_health_number_of_times_fallen_total", unit: "count", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierTimeInDaylight", metricName: "apple_health_time_in_daylight_seconds", unit: "s", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierWaterTemperature", metricName: "apple_health_water_temperature_c", unit: "°C", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierEnvironmentalAudioExposure", metricName: "apple_health_environmental_audio_exposure_db", unit: "dB", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierHeadphoneAudioExposure", metricName: "apple_health_headphone_audio_exposure_db", unit: "dB", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierCaffeineConsumption", metricName: "apple_health_caffeine_consumption_mg", unit: "mg", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierAlcoholConsumption", metricName: "apple_health_alcohol_consumption_grams", unit: "g", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierForcedExpiratoryVolume1", metricName: "apple_health_forced_expiratory_volume_l", unit: "L", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierForcedVitalCapacity", metricName: "apple_health_forced_vital_capacity_l", unit: "L", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierPeakExpiratoryFlowRate", metricName: "apple_health_peak_expiratory_flow_rate_l_per_sec", unit: "L/s", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierDietaryEnergyConsumed", metricName: "apple_health_dietary_energy_kcal", unit: "kcal", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierDietaryCarbohydrates", metricName: "apple_health_dietary_carbohydrates_g", unit: "g", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierDietaryProtein", metricName: "apple_health_dietary_protein_g", unit: "g", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierDietaryFatTotal", metricName: "apple_health_dietary_fat_total_g", unit: "g", isCategory: false),
        HKMetricMapping(hkTypeId: "HKQuantityTypeIdentifierWaterConsumption", metricName: "apple_health_water_consumption_ml", unit: "mL", isCategory: false),
        HKMetricMapping(hkTypeId: "HKCategoryTypeIdentifierSleepAnalysis", metricName: "apple_health_sleep_stage", unit: "", isCategory: true),
        HKMetricMapping(hkTypeId: "HKCategoryTypeIdentifierAppleStandHour", metricName: "apple_health_stand_hour", unit: "", isCategory: true),
    ]

    static func mapping(for hkTypeId: String) -> HKMetricMapping? {
        all.first { $0.hkTypeId == hkTypeId }
    }
}