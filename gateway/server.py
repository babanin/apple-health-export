import logging
import signal
import sys
import os
from concurrent import futures

import grpc

import health_export_pb2
import health_export_pb2_grpc
from checkpoint_store import CheckpointStore
from vm_writer import VMWriter

logger = logging.getLogger(__name__)

HK_TYPE_TO_METRIC = {
    "HKQuantityTypeIdentifierHeartRate": "apple_health_heart_rate_bpm",
    "HKQuantityTypeIdentifierRestingHeartRate": "apple_health_resting_heart_rate_bpm",
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": "apple_health_walking_heart_rate_avg_bpm",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "apple_health_heart_rate_variability_ms",
    "HKQuantityTypeIdentifierOxygenSaturation": "apple_health_oxygen_saturation_percent",
    "HKQuantityTypeIdentifierBloodPressureSystolic": "apple_health_blood_pressure_systolic_mmhg",
    "HKQuantityTypeIdentifierBloodPressureDiastolic": "apple_health_blood_pressure_diastolic_mmhg",
    "HKQuantityTypeIdentifierVO2Max": "apple_health_vo2_max_ml_kg_min",
    "HKQuantityTypeIdentifierStepCount": "apple_health_steps_total",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "apple_health_distance_walking_running_m",
    "HKQuantityTypeIdentifierDistanceCycling": "apple_health_distance_cycling_m",
    "HKQuantityTypeIdentifierDistanceSwimming": "apple_health_distance_swimming_m",
    "HKQuantityTypeIdentifierDistanceDownhillSnowSkiing": "apple_health_distance_snow_skiing_m",
    "HKQuantityTypeIdentifierFlightsClimbed": "apple_health_flights_climbed_total",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "apple_health_active_energy_burned_kcal",
    "HKQuantityTypeIdentifierBasalEnergyBurned": "apple_health_basal_energy_burned_kcal",
    "HKQuantityTypeIdentifierAppleExerciseTime": "apple_health_exercise_time_min",
    "HKQuantityTypeIdentifierAppleStandTime": "apple_health_stand_time_min",
    "HKQuantityTypeIdentifierAppleMoveTime": "apple_health_move_time_min",
    "HKQuantityTypeIdentifierStepCountPerMin": "apple_health_step_count_per_min",
    "HKQuantityTypeIdentifierSleepAnalysis": "apple_health_sleep_duration_seconds",
    "HKQuantityTypeIdentifierBodyMass": "apple_health_body_mass_kg",
    "HKQuantityTypeIdentifierBodyMassIndex": "apple_health_body_mass_index",
    "HKQuantityTypeIdentifierBodyFatPercentage": "apple_health_body_fat_percent",
    "HKQuantityTypeIdentifierLeanBodyMass": "apple_health_lean_body_mass_kg",
    "HKQuantityTypeIdentifierHeight": "apple_health_height_m",
    "HKQuantityTypeIdentifierWaistCircumference": "apple_health_waist_circumference_m",
    "HKQuantityTypeIdentifierRespiratoryRate": "apple_health_respiratory_rate_per_min",
    "HKQuantityTypeIdentifierForcedExpiratoryVolume1": "apple_health_forced_expiratory_volume_l",
    "HKQuantityTypeIdentifierForcedVitalCapacity": "apple_health_forced_vital_capacity_l",
    "HKQuantityTypeIdentifierPeakExpiratoryFlowRate": "apple_health_peak_expiratory_flow_rate_l_per_sec",
    "HKQuantityTypeIdentifierEnvironmentalAudioExposure": "apple_health_environmental_audio_exposure_db",
    "HKQuantityTypeIdentifierHeadphoneAudioExposure": "apple_health_headphone_audio_exposure_db",
    "HKQuantityTypeIdentifierEnvironmentalSoundReduction": "apple_health_environmental_sound_reduction_db",
    "HKQuantityTypeIdentifierBloodGlucose": "apple_health_blood_glucose_mg_dl",
    "HKQuantityTypeIdentifierInsulinDelivery": "apple_health_insulin_delivery_iu",
    "HKQuantityTypeIdentifierAlcoholConsumption": "apple_health_alcohol_consumption_grams",
    "HKQuantityTypeIdentifierCaffeineConsumption": "apple_health_caffeine_consumption_mg",
    "HKQuantityTypeIdentifierWaterConsumption": "apple_health_water_consumption_ml",
    "HKQuantityTypeIdentifierDietaryEnergyConsumed": "apple_health_dietary_energy_kcal",
    "HKQuantityTypeIdentifierDietaryCarbohydrates": "apple_health_dietary_carbohydrates_g",
    "HKQuantityTypeIdentifierDietaryProtein": "apple_health_dietary_protein_g",
    "HKQuantityTypeIdentifierDietaryFatTotal": "apple_health_dietary_fat_total_g",
    "HKQuantityTypeIdentifierWalkingSpeed": "apple_health_walking_speed_m_per_sec",
    "HKQuantityTypeIdentifierWalkingStepLength": "apple_health_walking_step_length_m",
    "HKQuantityTypeIdentifierWalkingAsymmetryPercentage": "apple_health_walking_asymmetry_percent",
    "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage": "apple_health_walking_double_support_percent",
    "HKQuantityTypeIdentifierStepLength": "apple_health_step_length_m",
    "HKQuantityTypeIdentifierUVIndex": "apple_health_uv_index",
    "HKQuantityTypeIdentifierAppleWalkingSteadiness": "apple_health_walking_steadiness_percent",
    "HKQuantityTypeIdentifierNumberOfTimesFallen": "apple_health_number_of_times_fallen_total",
    "HKQuantityTypeIdentifierTimeInDaylight": "apple_health_time_in_daylight_seconds",
    "HKQuantityTypeIdentifierWaterTemperature": "apple_health_water_temperature_c",
    "HKQuantityTypeIdentifierWaterDepth": "apple_health_water_depth_m",
    "HKQuantityTypeIdentifierUnderwaterDepth": "apple_health_underwater_depth_m",
    "HKQuantityTypeIdentifierInhalerUsage": "apple_health_inhaler_usage_total",
    "HKQuantityTypeIdentifierBloodAlcoholContent": "apple_health_blood_alcohol_content_percent",
    "HKQuantityTypeIdentifierHandwashingDuration": "apple_health_handwashing_duration_seconds",
    "HKQuantityTypeIdentifierToothbrushingDuration": "apple_health_toothbrushing_duration_seconds",
    "HKQuantityTypeIdentifierNickelExposure": "apple_health_nickel_exposure_ug_per_m3",
    "HKQuantityTypeIdentifierChromiumExposure": "apple_health_chromium_exposure_ug_per_m3",
    "HKQuantityTypeIdentifierCobaltExposure": "apple_health_cobalt_exposure_ug_per_m3",
    "HKCategoryTypeIdentifierSleepAnalysis": "apple_health_sleep_stage",
    "HKCategoryTypeIdentifierAppleStandHour": "apple_health_stand_hour",
    "HKCategoryTypeIdentifierMenstrualFlow": "apple_health_menstrual_flow",
    "HKCategoryTypeIdentifierCervicalMucusQuality": "apple_health_cervical_mucus_quality",
    "HKCategoryTypeIdentifierOvulationTestResult": "apple_health_ovulation_test_result",
    "HKCategoryTypeIdentifierIntermenstrualBleeding": "apple_health_intermenstrual_bleeding_total",
    "HKCategoryTypeIdentifierProgesteroneTestResult": "apple_health_progesterone_result",
    "HKQuantityTypeIdentifierHeartRateVariability": "apple_health_heart_rate_variability_ms",
    "HKQuantityTypeIdentifierWristTemperature": "apple_health_wrist_temperature_c",
    "HKQuantityTypeIdentifierPeripheralPerfusionIndex": "apple_health_peripheral_perfusion_index",
    "HKQuantityTypeIdentifierElectrodermalActivity": "apple_health_electrodermal_activity_microsiemens",
}

QUANTITY_TYPE_IDENTIFIERS = [
    "HKQuantityTypeIdentifierHeartRate",
    "HKQuantityTypeIdentifierRestingHeartRate",
    "HKQuantityTypeIdentifierWalkingHeartRateAverage",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
    "HKQuantityTypeIdentifierOxygenSaturation",
    "HKQuantityTypeIdentifierBloodPressureSystolic",
    "HKQuantityTypeIdentifierBloodPressureDiastolic",
    "HKQuantityTypeIdentifierVO2Max",
    "HKQuantityTypeIdentifierStepCount",
    "HKQuantityTypeIdentifierDistanceWalkingRunning",
    "HKQuantityTypeIdentifierDistanceCycling",
    "HKQuantityTypeIdentifierDistanceSwimming",
    "HKQuantityTypeIdentifierFlightsClimbed",
    "HKQuantityTypeIdentifierActiveEnergyBurned",
    "HKQuantityTypeIdentifierBasalEnergyBurned",
    "HKQuantityTypeIdentifierAppleExerciseTime",
    "HKQuantityTypeIdentifierAppleStandTime",
    "HKQuantityTypeIdentifierAppleMoveTime",
    "HKQuantityTypeIdentifierBodyMass",
    "HKQuantityTypeIdentifierBodyMassIndex",
    "HKQuantityTypeIdentifierBodyFatPercentage",
    "HKQuantityTypeIdentifierLeanBodyMass",
    "HKQuantityTypeIdentifierHeight",
    "HKQuantityTypeIdentifierWaistCircumference",
    "HKQuantityTypeIdentifierRespiratoryRate",
    "HKQuantityTypeIdentifierBloodGlucose",
    "HKQuantityTypeIdentifierInsulinDelivery",
    "HKQuantityTypeIdentifierWalkingSpeed",
    "HKQuantityTypeIdentifierWalkingStepLength",
    "HKQuantityTypeIdentifierWalkingAsymmetryPercentage",
    "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage",
    "HKQuantityTypeIdentifierStepLength",
    "HKQuantityTypeIdentifierUVIndex",
    "HKQuantityTypeIdentifierAppleWalkingSteadiness",
    "HKQuantityTypeIdentifierTimeInDaylight",
    "HKQuantityTypeIdentifierWaterTemperature",
    "HKQuantityTypeIdentifierEnvironmentalAudioExposure",
    "HKQuantityTypeIdentifierHeadphoneAudioExposure",
    "HKQuantityTypeIdentifierCaffeineConsumption",
    "HKQuantityTypeIdentifierAlcoholConsumption",
]


SERVER_VERSION = "0.1.0"


class HealthExportServicer(health_export_pb2_grpc.HealthExportServiceServicer):
    def __init__(self, vm_writer: VMWriter, checkpoint_store: CheckpointStore):
        self.vm_writer = vm_writer
        self.checkpoint_store = checkpoint_store

    def Ping(self, request, context):
        logger.info("Ping from device=%s", request.device_id)
        return health_export_pb2.PingResponse(ok=True, server_version=SERVER_VERSION)

    def SyncMetrics(self, request, context):
        try:
            device_id = request.device_id
            batch_id = request.batch_id
            num_samples = len(request.samples)
            num_checkpoints = len(request.checkpoint)
            is_historical = request.is_historical_export
            logger.info(
                "SyncMetrics device=%s batch=%s samples=%d checkpoints=%d historical=%s",
                device_id, batch_id, num_samples, num_checkpoints, is_historical,
            )

            if not request.samples and not request.checkpoint:
                logger.info("SyncMetrics device=%s batch=%s: empty request, acknowledging", device_id, batch_id)
                return health_export_pb2.SyncResponse(
                    acknowledged_count=0,
                    success=True,
                )

            self.vm_writer.add_samples(list(request.samples))

            total = len(request.samples)
            updated = {}

            for sample in request.samples:
                metric = sample.metric_name
                ts = sample.timestamp_ms
                if metric not in updated or ts > updated[metric]:
                    updated[metric] = ts

            for metric, ts in request.checkpoint.items():
                if metric not in updated or ts > updated[metric]:
                    updated[metric] = ts

            if updated:
                self.checkpoint_store.update_checkpoint(request.device_id, updated)

            current = self.checkpoint_store.get_checkpoint(request.device_id)
            logger.info(
                "SyncMetrics device=%s batch=%s: acknowledged=%d checkpoint_metrics=%d",
                device_id, batch_id, total, len(current),
            )

            return health_export_pb2.SyncResponse(
                acknowledged_count=total,
                updated_checkpoint=current,
                success=True,
            )
        except Exception as e:
            logger.exception("Error in SyncMetrics device=%s batch=%s", request.device_id, request.batch_id)
            return health_export_pb2.SyncResponse(
                acknowledged_count=0,
                success=False,
                error_message=str(e),
            )

    def GetCheckpoint(self, request, context):
        logger.info("GetCheckpoint device=%s", request.device_id)
        checkpoint = self.checkpoint_store.get_checkpoint(request.device_id)
        logger.info("GetCheckpoint device=%s: returning %d metrics", request.device_id, len(checkpoint))
        return health_export_pb2.CheckpointResponse(checkpoint=checkpoint)

    def SyncStream(self, request_iterator, context):
        for request in request_iterator:
            response = self.SyncMetrics(request, context)
            yield response


def serve(
    port: int = 50051,
    vm_url: str = "http://localhost:8428",
    db_path: str = "/data/checkpoints.db",
):
    vm_writer = VMWriter(vm_url=vm_url)
    vm_writer.start()

    checkpoint_store = CheckpointStore(db_path=db_path)
    servicer = HealthExportServicer(vm_writer=vm_writer, checkpoint_store=checkpoint_store)

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ("grpc.max_send_message_length", 100 * 1024 * 1024),
            ("grpc.max_receive_message_length", 100 * 1024 * 1024),
        ],
    )
    health_export_pb2_grpc.add_HealthExportServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"0.0.0.0:{port}")

    def shutdown(signum, frame):
        logger.info("Shutting down server...")
        vm_writer.stop()
        server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Starting gRPC server on port %d", port)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    port = int(os.environ.get("GRPC_PORT", "50051"))
    vm_url = os.environ.get("VM_URL", "http://victoriametrics:8428")
    db_path = os.environ.get("DB_PATH", "/data/checkpoints.db")
    serve(port=port, vm_url=vm_url, db_path=db_path)