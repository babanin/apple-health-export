#!/usr/bin/env python3
"""Generate curated Apple Health Grafana dashboards."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DASHBOARDS_DIR = ROOT / "dashboards"
PROVISIONING_DIR = ROOT / "grafana" / "provisioning" / "dashboards"
DS = {"type": "prometheus", "uid": "victoriametrics"}
SLEEP_TIMESERIES_UNIT = "h"
SLEEP_DURATION_UNIT = "dtdurations"
SLEEP_BUCKET_INTERVAL = "5m"
SLEEP_BUCKET_SECONDS = 300
LOCAL_TIME_OFFSET_SECONDS = 3 * 3600
DAY_SECONDS = 24 * 3600
DAY_MILLISECONDS = DAY_SECONDS * 1000
SLEEP_NIGHT_SPLIT_SECONDS = 12 * 3600
SLEEP_NIGHT_MIN_MILLISECONDS = 18 * 3600 * 1000
SLEEP_NIGHT_MAX_MILLISECONDS = 30 * 3600 * 1000


@dataclass(frozen=True)
class Metric:
    title: str
    metric: str
    unit: str = "short"
    kind: str = "continuous"
    domain: str = "Other"
    expr: str | None = None
    with_trend: bool = False


METRICS: list[Metric] = [
    Metric("Heart Rate", "apple_health_heart_rate_bpm", "bpm", "continuous", "Cardio"),
    Metric("Resting Heart Rate", "apple_health_resting_heart_rate_bpm", "bpm", "trend_continuous", "Cardio"),
    Metric("Walking Heart Rate Average", "apple_health_walking_heart_rate_avg_bpm", "bpm", "trend_continuous", "Cardio"),
    Metric("HRV SDNN", "apple_health_heart_rate_variability_ms", "ms", "trend_continuous", "Cardio"),
    Metric("Blood Oxygen", "apple_health_oxygen_saturation_percent", "percentunit", "bounded", "Cardio"),
    Metric("Blood Pressure Systolic", "apple_health_blood_pressure_systolic_mmhg", "mmHg", "filled_continuous", "Cardio"),
    Metric("Blood Pressure Diastolic", "apple_health_blood_pressure_diastolic_mmhg", "mmHg", "filled_continuous", "Cardio"),
    Metric("Cardio Fitness VO2 Max", "apple_health_vo2_max_ml_kg_min", "mL/kg/min", "filled_continuous", "Cardio"),
    Metric("Steps", "apple_health_steps_total", "short", "daily_total", "Activity", with_trend=True),
    Metric("Walking and Running Distance", "apple_health_distance_walking_running_m", "km", "daily_total_km", "Activity", with_trend=True),
    Metric("Cycling Distance", "apple_health_distance_cycling_m", "km", "daily_total_km", "Activity"),
    Metric("Swimming Distance", "apple_health_distance_swimming_m", "m", "daily_total", "Activity"),
    Metric("Flights Climbed", "apple_health_flights_climbed_total", "short", "daily_total", "Activity"),
    Metric("Active Energy", "apple_health_active_energy_burned_kcal", "kcal", "daily_total", "Activity"),
    Metric("Basal Energy", "apple_health_basal_energy_burned_kcal", "kcal", "daily_total", "Activity"),
    Metric("Exercise Time", "apple_health_exercise_time_min", "min", "daily_total", "Activity", with_trend=True),
    Metric("Stand Time", "apple_health_stand_time_min", "min", "daily_total", "Activity"),
    Metric("Move Time", "apple_health_move_time_min", "min", "daily_total", "Activity"),
    Metric("Step Cadence", "apple_health_step_count_per_min", "short", "continuous", "Activity"),
    Metric("Sleep Stage", "apple_health_sleep_stage", "none", "state", "Sleep"),
    Metric("Stand Hour", "apple_health_stand_hour", "none", "state", "Sleep"),
    Metric("Body Weight", "apple_health_body_mass_kg", "kg", "filled_continuous", "Body"),
    Metric("BMI", "apple_health_body_mass_index", "short", "bounded", "Body"),
    Metric("Body Fat", "apple_health_body_fat_percent", "percentunit", "bounded", "Body"),
    Metric("Lean Body Mass", "apple_health_lean_body_mass_kg", "kg", "filled_continuous", "Body"),
    Metric("Height", "apple_health_height_m", "m", "latest", "Body"),
    Metric("Waist Circumference", "apple_health_waist_circumference_m", "m", "filled_continuous", "Body"),
    Metric("Respiratory Rate", "apple_health_respiratory_rate_per_min", "breaths/min", "continuous", "Respiratory"),
    Metric("Forced Expiratory Volume", "apple_health_forced_expiratory_volume_l", "L", "continuous", "Respiratory"),
    Metric("Forced Vital Capacity", "apple_health_forced_vital_capacity_l", "L", "continuous", "Respiratory"),
    Metric("Peak Expiratory Flow", "apple_health_peak_expiratory_flow_rate_l_per_sec", "L/s", "continuous", "Respiratory"),
    Metric("Blood Glucose", "apple_health_blood_glucose_mg_dl", "mg/dL", "continuous", "Metabolic"),
    Metric("Insulin Delivery", "apple_health_insulin_delivery_iu", "IU", "daily_total", "Metabolic"),
    Metric("Caffeine", "apple_health_caffeine_consumption_mg", "mg", "daily_total", "Nutrition"),
    Metric("Alcohol", "apple_health_alcohol_consumption_grams", "g", "daily_total", "Nutrition"),
    Metric("Dietary Energy", "apple_health_dietary_energy_kcal", "kcal", "daily_total", "Nutrition"),
    Metric("Dietary Carbohydrates", "apple_health_dietary_carbohydrates_g", "g", "daily_total", "Nutrition"),
    Metric("Dietary Protein", "apple_health_dietary_protein_g", "g", "daily_total", "Nutrition"),
    Metric("Dietary Fat", "apple_health_dietary_fat_total_g", "g", "daily_total", "Nutrition"),
    Metric("Water Consumption", "apple_health_water_consumption_ml", "mL", "daily_total", "Nutrition"),
    Metric("Walking Speed", "apple_health_walking_speed_m_per_sec", "m/s", "continuous", "Mobility"),
    Metric("Walking Step Length", "apple_health_walking_step_length_m", "m", "continuous", "Mobility"),
    Metric("Walking Asymmetry", "apple_health_walking_asymmetry_percent", "percentunit", "bounded", "Mobility"),
    Metric("Walking Double Support", "apple_health_walking_double_support_percent", "percentunit", "bounded", "Mobility"),
    Metric("Step Length", "apple_health_step_length_m", "m", "continuous", "Mobility"),
    Metric("Walking Steadiness", "apple_health_walking_steadiness_percent", "percentunit", "bounded", "Mobility"),
    Metric("UV Index", "apple_health_uv_index", "short", "continuous", "Environment"),
    Metric("Time in Daylight", "apple_health_time_in_daylight_seconds", "h", "daily_total_hours", "Environment", with_trend=True),
    Metric("Water Temperature", "apple_health_water_temperature_c", "celsius", "continuous", "Environment"),
    Metric("Environmental Audio Exposure", "apple_health_environmental_audio_exposure_db", "dB", "continuous", "Environment"),
    Metric("Headphone Audio Exposure", "apple_health_headphone_audio_exposure_db", "dB", "continuous", "Environment"),
    Metric("Falls", "apple_health_number_of_times_fallen_total", "short", "daily_total", "Safety"),
    Metric("Workout Duration", "apple_health_workout_duration_seconds", "h", "workout_total_hours", "Workouts", with_trend=True),
    Metric("Workout Energy", "apple_health_workout_energy_kcal", "kcal", "workout_total", "Workouts", with_trend=True),
    Metric("Workout Heart Rate", "apple_health_workout_heart_rate_bpm", "bpm", "workout_continuous", "Workouts"),
    Metric("Workout Distance", "apple_health_workout_distance_m", "km", "workout_total_km", "Workouts", with_trend=True),
    Metric("Workout Average Speed", "apple_health_workout_avg_speed_m_per_sec", "km/h", "workout_speed", "Workouts"),
]


def target(
    expr: str,
    ref_id: str = "A",
    legend: str | None = None,
    instant: bool = False,
    interval: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "datasource": DS,
        "expr": expr,
        "refId": ref_id,
    }
    if legend:
        out["legendFormat"] = legend
    if instant:
        out["instant"] = True
        out["range"] = False
    if interval:
        out["interval"] = interval
    return out


def thresholds(*steps: tuple[int | float | None, str]) -> dict[str, Any]:
    return {"mode": "absolute", "steps": [{"value": value, "color": color} for value, color in steps]}


def field(
    unit: str = "short",
    thresholds_: dict[str, Any] | None = None,
    custom: dict[str, Any] | None = None,
    decimals: int | None = None,
    min_: int | float | None = None,
    max_: int | float | None = None,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {"unit": unit}
    if decimals is not None:
        defaults["decimals"] = decimals
    if min_ is not None:
        defaults["min"] = min_
    if max_ is not None:
        defaults["max"] = max_
    if thresholds_:
        defaults["thresholds"] = thresholds_
    if custom:
        defaults["custom"] = custom
    return {"defaults": defaults, "overrides": []}


def grid(index: int, w: int, h: int, y: int, cols: int = 24) -> dict[str, int]:
    x = (index * w) % cols
    return {"h": h, "w": w, "x": x, "y": y + ((index * w) // cols) * h}


def row(panel_id: int, title: str, y: int) -> dict[str, Any]:
    return {"id": panel_id, "title": title, "type": "row", "collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}}


def stat(panel_id: int, title: str, expr: str, pos: dict[str, int], unit: str = "short", thresholds_: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": panel_id,
        "title": title,
        "type": "stat",
        "datasource": DS,
        "gridPos": pos,
        "targets": [target(expr, instant=True)],
        "fieldConfig": field(unit, thresholds_),
        "options": {
            "colorMode": "background",
            "graphMode": "area",
            "justifyMode": "center",
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "auto",
        },
    }


def timeseries(
    panel_id: int,
    title: str,
    targets: list[dict[str, Any]],
    pos: dict[str, int],
    unit: str = "short",
    bars: bool = False,
    stacked: bool = False,
    thresholds_: dict[str, Any] | None = None,
    description: str | None = None,
    span_nulls: bool = False,
    overrides: list[dict[str, Any]] | None = None,
    decimals: int | None = None,
    min_: int | float | None = None,
    max_: int | float | None = None,
) -> dict[str, Any]:
    custom = {
        "drawStyle": "bars" if bars else "line",
        "lineInterpolation": "smooth",
        "lineWidth": 1,
        "fillOpacity": 35 if bars or stacked else 8,
        "showPoints": "never" if bars else "auto",
        "spanNulls": span_nulls,
        "stacking": {"mode": "normal" if stacked else "none", "group": "A"},
    }
    field_config = field(unit, thresholds_, custom, decimals, min_, max_)
    if overrides:
        field_config["overrides"] = overrides
    panel = {
        "id": panel_id,
        "title": title,
        "type": "timeseries",
        "datasource": DS,
        "gridPos": pos,
        "targets": targets,
        "fieldConfig": field_config,
        "options": {
            "legend": {"calcs": ["lastNotNull"], "displayMode": "table", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "none"},
        },
    }
    if description:
        panel["description"] = description
    return panel


def gauge(panel_id: int, title: str, expr: str, pos: dict[str, int], unit: str, min_: float, max_: float, thresholds_: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": panel_id,
        "title": title,
        "type": "gauge",
        "datasource": DS,
        "gridPos": pos,
        "targets": [target(expr, instant=True)],
        "fieldConfig": {
            "defaults": {"unit": unit, "min": min_, "max": max_, "thresholds": thresholds_},
            "overrides": [],
        },
        "options": {"orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "showThresholdLabels": False, "showThresholdMarkers": True},
    }


def bar_gauge(panel_id: int, title: str, expr: str, pos: dict[str, int], unit: str, min_: float | None = None, max_: float | None = None, thresholds_: dict[str, Any] | None = None) -> dict[str, Any]:
    defaults: dict[str, Any] = {"unit": unit}
    if min_ is not None:
        defaults["min"] = min_
    if max_ is not None:
        defaults["max"] = max_
    if thresholds_:
        defaults["thresholds"] = thresholds_
    return {
        "id": panel_id,
        "title": title,
        "type": "bargauge",
        "datasource": DS,
        "gridPos": pos,
        "targets": [target(expr, instant=True)],
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "displayMode": "gradient",
            "maxVizHeight": 300,
            "minVizHeight": 16,
            "minVizWidth": 0,
            "namePlacement": "auto",
            "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "showUnfilled": True,
            "valueMode": "color",
        },
    }


def piechart(panel_id: int, title: str, targets: list[dict[str, Any]], pos: dict[str, int], unit: str = "short") -> dict[str, Any]:
    return {
        "id": panel_id,
        "title": title,
        "type": "piechart",
        "datasource": DS,
        "gridPos": pos,
        "targets": targets,
        "fieldConfig": field(unit),
        "options": {
            "displayLabels": ["name", "percent"],
            "legend": {"displayMode": "table", "placement": "right", "showLegend": True, "values": ["value", "percent"]},
            "pieType": "donut",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "tooltip": {"mode": "single", "sort": "none"},
        },
    }


def table_panel(panel_id: int, title: str, targets: list[dict[str, Any]], pos: dict[str, int]) -> dict[str, Any]:
    return {
        "id": panel_id,
        "title": title,
        "type": "table",
        "datasource": DS,
        "gridPos": pos,
        "targets": targets,
        "fieldConfig": field("short"),
        "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}},
    }


def workout_route_map(panel_id: int, pos: dict[str, int]) -> dict[str, Any]:
    selector = 'source=~"$source",type=~"$workout_type",workout_id=~"$workout_id"'
    return {
        "id": panel_id,
        "title": "Outdoor Workout Route",
        "type": "geomap",
        "datasource": DS,
        "gridPos": pos,
        "targets": [
            target(f'apple_health_workout_route_latitude_degrees{{{selector}}}', "A", "latitude"),
            target(f'apple_health_workout_route_longitude_degrees{{{selector}}}', "B", "longitude"),
            target(f'apple_health_workout_route_speed_m_per_sec{{{selector}}}', "C", "speed"),
        ],
        "transformations": [
            {"id": "joinByField", "options": {"byField": "Time", "mode": "outer"}},
            {"id": "sortBy", "options": {"fields": {}, "sort": [{"field": "Time"}]}},
        ],
        "fieldConfig": field("short"),
        "options": {
            "view": {"id": "fit", "lat": 0, "lon": 0, "zoom": 12},
            "basemap": {"type": "osm-standard", "name": "OpenStreetMap", "config": {"showAttribution": True}},
            "layers": [
                {
                    "type": "route",
                    "name": "Route",
                    "config": {
                        "location": {
                            "mode": "coords",
                            "latitude": "apple_health_workout_route_latitude_degrees",
                            "longitude": "apple_health_workout_route_longitude_degrees",
                        },
                        "style": {
                            "color": {"fixed": "dark-green"},
                            "opacity": 0.8,
                            "size": {"fixed": 4},
                        },
                        "arrow": "forward",
                        "showLegend": True,
                        "tooltip": True,
                    },
                },
                {
                    "type": "markers",
                    "name": "Route points",
                    "config": {
                        "location": {
                            "mode": "coords",
                            "latitude": "apple_health_workout_route_latitude_degrees",
                            "longitude": "apple_health_workout_route_longitude_degrees",
                        },
                        "style": {
                            "color": {"fixed": "blue"},
                            "opacity": 0.45,
                            "size": {"fixed": 3},
                            "symbol": {"fixed": "img/icons/marker/circle.svg"},
                        },
                        "showLegend": False,
                        "tooltip": True,
                    },
                },
            ],
            "controls": {
                "showZoom": True,
                "mouseWheelZoom": True,
                "showAttribution": True,
                "showScale": True,
                "showMeasure": True,
                "showDebug": False,
            },
            "tooltip": {"mode": "details"},
        },
    }


def state_panel(panel_id: int, title: str, expr: str, pos: dict[str, int], status: bool = False) -> dict[str, Any]:
    return {
        "id": panel_id,
        "title": title,
        "type": "status-history" if status else "state-timeline",
        "datasource": DS,
        "gridPos": pos,
        "targets": [target(expr, legend="{{stage}}{{type}}")],
        "fieldConfig": field("none"),
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "mergeValues": True,
            "showValue": "auto",
            "tooltip": {"mode": "single", "sort": "none"},
        },
    }


def latest(metric: str, selector: str = 'source=~"$source"') -> str:
    return f'last_over_time({metric}{{{selector}}}[$__range])'


def filled(metric: str, selector: str = 'source=~"$source"') -> str:
    return f'last_over_time({metric}{{{selector}}}[$__range])'


def smoothed(metric: str, window: str, selector: str = 'source=~"$source"') -> str:
    return f'avg_over_time({metric}{{{selector}}}[{window}])'


def rolling_average(metric: str, window: str, selector: str = 'source=~"$source"') -> str:
    return f'avg_over_time({metric}{{{selector}}}[{window}])'


def daily(metric: str, selector: str = 'source=~"$source"', divisor: float | None = None) -> str:
    expr = f'sum(sum_over_time({metric}{{{selector}}}[1d]))'
    if divisor:
        expr = f"({expr}) / {divisor:g}"
    return expr


def weekly(metric: str, selector: str = 'source=~"$source"', divisor: float | None = None) -> str:
    expr = f'sum(sum_over_time({metric}{{{selector}}}[7d]))'
    if divisor:
        expr = f"({expr}) / {divisor:g}"
    return expr


def daily_by_stage() -> str:
    return sleep_seconds(stage='stage=~"Asleep|Core|Deep|REM"', keep_stage=True)


def daily_trend(metric: str, window: str, selector: str = 'source=~"$source"', divisor: float | None = None) -> str:
    expr = f'sum(sum_over_time({metric}{{{selector}}}[1d]))'
    if divisor:
        expr = f"({expr}) / {divisor:g}"
    return f'avg_over_time(({expr})[{window}:1d])'


def daily_target(
    metric: str,
    ref_id: str,
    legend: str,
    selector: str = 'source=~"$source"',
    divisor: float | None = None,
) -> dict[str, Any]:
    return target(daily(metric, selector, divisor), ref_id, legend, interval="1d")


def daily_trend_target(
    metric: str,
    window: str,
    ref_id: str,
    legend: str,
    selector: str = 'source=~"$source"',
    divisor: float | None = None,
) -> dict[str, Any]:
    return target(daily_trend(metric, window, selector, divisor), ref_id, legend, interval="1d")


def weekly_target(
    metric: str,
    ref_id: str,
    legend: str,
    selector: str = 'source=~"$source"',
    divisor: float | None = None,
) -> dict[str, Any]:
    return target(weekly(metric, selector, divisor), ref_id, legend, interval="7d")


def sleep_seconds(
    selector: str = 'source=~"$source"',
    window: str = "1d",
    stage: str = 'stage=~"Asleep|Core|Deep|REM"',
    keep_stage: bool = False,
) -> str:
    grouping = "source" if keep_stage else "source, stage"
    return (
        "sum_over_time(("
        f"max without ({grouping}) "
        f"(present_over_time(apple_health_sleep_stage{{{selector},{stage}}}[{SLEEP_BUCKET_INTERVAL}]))"
        f")[{window}:{SLEEP_BUCKET_INTERVAL}]) * {SLEEP_BUCKET_SECONDS}"
    )


def sleep_hours(
    selector: str = 'source=~"$source"',
    window: str = "1d",
    stage: str = 'stage=~"Asleep|Core|Deep|REM"',
) -> str:
    return f"({sleep_seconds(selector, window, stage)}) / 3600"


def bedtime_seconds(selector: str = 'source=~"$source"', window: str = "1d") -> str:
    return (
        "min without (source, stage) ("
        f'min_over_time(timestamp(apple_health_sleep_stage{{{selector},stage="InBed"}})'
        f"[{window}:{SLEEP_BUCKET_INTERVAL}])"
        ")"
        " or "
        "min without (source, stage) ("
        f'min_over_time(timestamp(apple_health_sleep_stage{{{selector},stage=~"Awake|Asleep|Core|Deep|REM"}})'
        f"[{window}:{SLEEP_BUCKET_INTERVAL}])"
        ")"
    )


def bedtime_ms(selector: str = 'source=~"$source"', window: str = "1d") -> str:
    return f"({bedtime_seconds(selector, window)}) * 1000"


def bedtime_clock_ms(selector: str = 'source=~"$source"', window: str = "1d") -> str:
    return f"(({bedtime_seconds(selector, window)} + {LOCAL_TIME_OFFSET_SECONDS}) % {DAY_SECONDS}) * 1000"


def bedtime_sleep_night_ms(selector: str = 'source=~"$source"', window: str = "1d") -> str:
    bedtime = bedtime_clock_ms(selector, window)
    return f"({bedtime}) + {DAY_MILLISECONDS} * (({bedtime}) < bool {SLEEP_NIGHT_SPLIT_SECONDS * 1000})"


def bedtime_clock_trend_ms(trend_window: str, selector: str = 'source=~"$source"') -> str:
    return f"avg_over_time(({bedtime_sleep_night_ms(selector)})[{trend_window}:1d])"


def sleep_trend_hours(
    trend_window: str,
    selector: str = 'source=~"$source"',
    stage: str = 'stage=~"Asleep|Core|Deep|REM"',
) -> str:
    return f"avg_over_time(({sleep_hours(selector, stage=stage)})[{trend_window}:1d])"


def sleep_trend_seconds(
    trend_window: str,
    selector: str = 'source=~"$source"',
    stage: str = 'stage=~"Asleep|Core|Deep|REM"',
) -> str:
    return f"avg_over_time(({sleep_seconds(selector, stage=stage)})[{trend_window}:1d])"


def training_load_daily(selector: str = 'source=~"$source",type=~"$workout_type"') -> str:
    return daily("apple_health_workout_energy_kcal", selector)


def training_load_7d(selector: str = 'source=~"$source",type=~"$workout_type"') -> str:
    return f'sum(sum_over_time(apple_health_workout_energy_kcal{{{selector}}}[7d]))'


def training_load_ratio(selector: str = 'source=~"$source",type=~"$workout_type"') -> str:
    acute = training_load_7d(selector)
    chronic = f'sum(sum_over_time(apple_health_workout_energy_kcal{{{selector}}}[28d])) / 4'
    return f'({acute}) / clamp_min(({chronic}), 1)'


def readiness_score(selector: str = 'source=~"$source"', workout_selector: str = 'source=~"$source",type=~"$workout_type"') -> str:
    hrv_7d = smoothed("apple_health_heart_rate_variability_ms", "7d", selector)
    hrv_30d = smoothed("apple_health_heart_rate_variability_ms", "30d", selector)
    sleep_component = f'clamp_max(({sleep_hours(selector)} / 8), 1)'
    resting_hr_7d = smoothed("apple_health_resting_heart_rate_bpm", "7d", selector)
    resting_hr_30d = smoothed("apple_health_resting_heart_rate_bpm", "30d", selector)
    load_ratio = training_load_ratio(workout_selector)
    score = (
        "40"
        f" + 20 * clamp_max(({hrv_7d}) / clamp_min(({hrv_30d}), 1), 1.5)"
        f" + 20 * {sleep_component}"
        f" + 20 * clamp_max(({resting_hr_30d}) / clamp_min(({resting_hr_7d}), 1), 1.2)"
        f" - 10 * clamp_min(({load_ratio}) - 1, 0)"
    )
    return f"clamp_max(clamp_min(({score}), 0), 100)"


def trend_overrides(ref_ids: list[str]) -> list[dict[str, Any]]:
    """Generate field config overrides to draw specific series as lines."""
    return [
        {
            "matcher": {"id": "byFrameRefID", "options": ref_id},
            "properties": [
                {"id": "custom.drawStyle", "value": "line"},
                {"id": "custom.lineWidth", "value": 2},
                {"id": "custom.fillOpacity", "value": 0},
            ],
        }
        for ref_id in ref_ids
    ]


def dashboard_base(uid: str, title: str, refresh: str = "5m", extra_variables: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    variables = [
        {
            "name": "source",
            "type": "query",
            "datasource": DS,
            "definition": 'label_values({__name__=~"apple_health_.*"}, source)',
            "query": 'label_values({__name__=~"apple_health_.*"}, source)',
            "label": "Source",
            "includeAll": True,
            "multi": True,
            "current": {"text": "All", "value": "$__all"},
        },
        {
            "name": "workout_type",
            "type": "query",
            "datasource": DS,
            "definition": 'label_values(apple_health_workout_duration_seconds{source=~"$source"}, type)',
            "query": 'label_values(apple_health_workout_duration_seconds{source=~"$source"}, type)',
            "label": "Workout Type",
            "includeAll": True,
            "multi": True,
            "current": {"text": "All", "value": "$__all"},
        },
    ]
    if extra_variables:
        variables.extend(extra_variables)

    return {
        "uid": uid,
        "title": title,
        "tags": ["apple-health", "health", "ios", "curated"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": refresh,
        "time": {"from": "now-30d", "to": "now"},
        "timepicker": {"refresh_intervals": ["30s", "1m", "5m", "15m", "1h"]},
        "templating": {"list": variables},
        "annotations": {"list": [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True, "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"}]},
        "panels": [],
    }


def build_overview() -> dict[str, Any]:
    dash = dashboard_base("apple-health-overview", "Apple Health - Overview", refresh="1m")
    dash["time"] = {"from": "now-30d", "to": "now"}
    panels: list[dict[str, Any]] = []
    pid = 1
    selector = 'source=~"$source"'
    sleep_all = 'stage=~"Awake|Asleep|Core|Deep|REM|InBed"'

    left_specs = [
        ("Last Sample Age", f'time() - max(timestamp(apple_health_heart_rate_bpm{{{selector}}}))', "s", thresholds((None, "green"), (3600, "yellow"), (21600, "orange"), (86400, "red"))),
        ("Resting HR", latest("apple_health_resting_heart_rate_bpm", selector), "bpm", thresholds((None, "blue"), (40, "green"), (80, "orange"), (100, "red"))),
        ("Today's Steps", daily("apple_health_steps_total", selector), "short", thresholds((None, "red"), (5000, "yellow"), (8000, "green"))),
        ("SpO2", latest("apple_health_oxygen_saturation_percent", selector), "percentunit", thresholds((None, "red"), (0.92, "orange"), (0.95, "green"))),
        ("Last Day Total Sleep", sleep_seconds(selector), "dtdurations", thresholds((None, "red"), (21600, "yellow"), (25200, "green"))),
        ("Last Bedtime", bedtime_ms(selector), "dateTimeAsLocal", None),
        ("Active Energy", daily("apple_health_active_energy_burned_kcal", selector), "kcal", thresholds((None, "red"), (250, "yellow"), (500, "green"))),
    ]
    for i, (title, expr, unit, thr) in enumerate(left_specs):
        panel = stat(pid, title, expr, {"h": 4, "w": 3, "x": 0, "y": i * 4}, unit, thr)
        panel["options"]["graphMode"] = "none" if i in {1, 2, 3, 4, 5} else "area"
        panels.append(panel)
        pid += 1

    recent_y = 0
    recent_panels = [
        timeseries(pid, "Heart Rate", [
            target(f'apple_health_heart_rate_bpm{{{selector}}}', "A", "Heart Rate"),
        ], {"h": 6, "w": 21, "x": 3, "y": recent_y}, "bpm", thresholds_=thresholds((None, "blue"), (60, "green"), (95, "yellow"), (120, "red")), span_nulls=True),
        timeseries(pid + 1, "Intraday Steps", [
            target(f'sum(sum_over_time(apple_health_steps_total{{{selector}}}[5m]))', "A", "Intraday Steps"),
        ], {"h": 6, "w": 21, "x": 3, "y": recent_y + 6}, "short", bars=True, thresholds_=thresholds((None, "blue"), (25, "green"), (65, "yellow"), (100, "red"))),
        timeseries(pid + 2, "SpO2 Today", [
            target(f'apple_health_oxygen_saturation_percent{{{selector}}}', "A", "SpO2"),
        ], {"h": 5, "w": 21, "x": 3, "y": recent_y + 12}, "percentunit", bars=True, thresholds_=thresholds((None, "red"), (0.92, "orange"), (0.95, "green")), span_nulls=True),
    ]
    for panel in recent_panels:
        panel["timeFrom"] = "24h"
        panels.append(panel)
    pid += len(recent_panels)

    sleep_recent = state_panel(pid, "Sleep Pattern", f'apple_health_sleep_stage{{{selector}}}', {"h": 5, "w": 21, "x": 3, "y": recent_y + 17})
    sleep_recent["timeFrom"] = "24h"
    panels.append(sleep_recent)
    pid += 1

    y = len(left_specs) * 4
    panels.append(row(pid, "Sleep", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Sleep", [
        target(daily_by_stage(), "A", "{{stage}}"),
    ], {"h": 8, "w": 11, "x": 0, "y": y}, "dtdurations", bars=True, stacked=True))
    pid += 1
    efficiency_expr = (
        f'100 * ({sleep_seconds(selector)}) / '
        f'clamp_min(({sleep_seconds(selector, stage=sleep_all)}), 1)'
    )
    panels.append(timeseries(pid, "Sleep Efficiency", [
        target(efficiency_expr, "A", "Efficiency"),
    ], {"h": 8, "w": 7, "x": 11, "y": y}, "percent", bars=True, thresholds_=thresholds((None, "red"), (70, "yellow"), (85, "green"))))
    pid += 1
    panels.append(timeseries(pid, "Cardio Fitness", [
        target(filled("apple_health_vo2_max_ml_kg_min", selector), "A", "VO2 Max"),
    ], {"h": 8, "w": 6, "x": 18, "y": y}, "mL/kg/min", bars=True, span_nulls=True))
    pid += 1

    y += 8
    panels.append(piechart(pid, "Average Sleep Trends", [
        target(sleep_seconds(window="30d", stage='stage=~"Core|Light|Deep|REM|Awake|Asleep"', keep_stage=True), "A", "{{stage}}", instant=True),
    ], {"h": 9, "w": 12, "x": 0, "y": y}, "dtdurations"))
    pid += 1
    sleep_regularity = state_panel(pid, "Sleep Regularity", f'last_over_time(apple_health_sleep_stage{{{selector}}}[1h])', {"h": 9, "w": 12, "x": 12, "y": y}, status=True)
    sleep_regularity["maxDataPoints"] = 800
    sleep_regularity["targets"][0]["interval"] = "1h"
    sleep_regularity["targets"][0]["legendFormat"] = "Sleep Regularity"
    panels.append(sleep_regularity)
    pid += 1

    y += 9
    panels.append(row(pid, "Other Long Term Data", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Resting HR", [
        target(filled("apple_health_resting_heart_rate_bpm", selector), "A", "Resting HR"),
        target(smoothed("apple_health_resting_heart_rate_bpm", "7d", selector), "B", "7d"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "bpm", span_nulls=True))
    pid += 1
    panels.append(timeseries(pid, "HRV", [
        target('apple_health_heart_rate_variability_ms{source=~"$source"}', "A", "Daily Rmssd"),
        target(smoothed("apple_health_heart_rate_variability_ms", "7d", selector), "B", "7d"),
        target(smoothed("apple_health_heart_rate_variability_ms", "30d", selector), "C", "30d"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "ms", span_nulls=True))
    pid += 1

    y += 8
    panels.append(timeseries(pid, "SpO2 (Avg)", [
        target('avg_over_time(apple_health_oxygen_saturation_percent{source=~"$source"}[1d])', "A", "SpO2 Intraday"),
        target('avg_over_time(apple_health_oxygen_saturation_percent{source=~"$source"}[7d])', "B", "7d"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "percentunit", span_nulls=True))
    pid += 1
    panels.append(timeseries(pid, "Breathing Rate", [
        target(smoothed("apple_health_respiratory_rate_per_min", "1d", selector), "A", "Daily average"),
        target(smoothed("apple_health_respiratory_rate_per_min", "7d", selector), "B", "7d trend"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "breaths/min", span_nulls=True))
    pid += 1

    y += 8
    panels.append(timeseries(pid, "Body and Recovery", [
        target(filled("apple_health_body_mass_kg", selector), "A", "Body Weight"),
        target(filled("apple_health_walking_steadiness_percent", selector), "B", "Walking Steadiness"),
        target(smoothed("apple_health_walking_heart_rate_avg_bpm", "7d", selector), "C", "Walking HR 7d"),
    ], {"h": 8, "w": 24, "x": 0, "y": y}, "short", span_nulls=True))

    dash["panels"] = panels
    return dash


def build_daily_ops() -> dict[str, Any]:
    dash = dashboard_base("apple-health-daily-ops", "Apple Health - Daily Ops")
    panels: list[dict[str, Any]] = []
    pid = 1
    stat_specs = [
        ("Steps Today", daily("apple_health_steps_total"), "short", thresholds((None, "red"), (5000, "yellow"), (8000, "green"))),
        ("Active Energy", daily("apple_health_active_energy_burned_kcal"), "kcal", thresholds((None, "red"), (250, "yellow"), (500, "green"))),
        ("Exercise Minutes", daily("apple_health_exercise_time_min"), "min", thresholds((None, "red"), (15, "yellow"), (30, "green"))),
        ("Sleep Duration", sleep_seconds(), "dtdurations", thresholds((None, "red"), (21600, "yellow"), (25200, "green"))),
        ("Resting HR", latest("apple_health_resting_heart_rate_bpm"), "bpm", thresholds((None, "blue"), (40, "green"), (80, "orange"), (100, "red"))),
        ("Body Weight", latest("apple_health_body_mass_kg"), "kg", None),
    ]
    for i, (title, expr, unit, thr) in enumerate(stat_specs):
        panels.append(stat(pid, title, expr, grid(i, 4, 4, 0), unit, thr))
        pid += 1
    y = 4
    panels.append(timeseries(pid, "Daily Activity Load", [
        daily_target("apple_health_steps_total", "A", "Steps"),
        daily_target("apple_health_active_energy_burned_kcal", "B", "Active kcal"),
        daily_target("apple_health_exercise_time_min", "C", "Exercise min"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "short", bars=True))
    pid += 1
    panels.append(timeseries(pid, "Sleep Duration by Stage", [target(daily_by_stage(), "A", "{{stage}}")], {"h": 8, "w": 12, "x": 12, "y": y}, "dtdurations", bars=True, stacked=True))
    pid += 1
    y += 8
    panels.append(state_panel(pid, "Sleep Stages", 'apple_health_sleep_stage{source=~"$source"}', {"h": 8, "w": 24, "x": 0, "y": y}))
    pid += 1
    y += 8
    panels.append(timeseries(pid, "Heart Rate and Resting Trend", [
        target('apple_health_heart_rate_bpm{source=~"$source"}', "A", "Heart rate"),
        target(filled("apple_health_resting_heart_rate_bpm"), "B", "Resting"),
        target(smoothed("apple_health_resting_heart_rate_bpm", "7d"), "C", "Resting 7d"),
        target(smoothed("apple_health_resting_heart_rate_bpm", "30d"), "D", "Resting 30d"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "bpm", thresholds_=thresholds((None, "blue"), (50, "green"), (100, "orange"), (130, "red")), span_nulls=True))
    pid += 1
    panels.append(timeseries(pid, "Weight and Glucose", [
        target(filled("apple_health_body_mass_kg"), "A", "Weight"),
        target('apple_health_blood_glucose_mg_dl{source=~"$source"}', "B", "Glucose"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "short", span_nulls=True))
    dash["panels"] = panels
    return dash


def panel_for_metric(pid: int, metric: Metric, pos: dict[str, int]) -> dict[str, Any]:
    selector = 'source=~"$source"'
    mobility_trend_metrics = {
        "apple_health_walking_speed_m_per_sec",
        "apple_health_walking_step_length_m",
        "apple_health_walking_asymmetry_percent",
        "apple_health_walking_double_support_percent",
        "apple_health_step_length_m",
    }
    if metric.metric in mobility_trend_metrics:
        unit = "lengthm" if metric.metric.endswith("_m") else metric.unit
        return timeseries(pid, metric.title, [
            target(rolling_average(metric.metric, "1d", selector), "A", "Daily average", interval="1d"),
            target(rolling_average(metric.metric, "7d", selector), "B", "7d trend", interval="1d"),
        ], pos, unit, span_nulls=True, overrides=trend_overrides(["B"]), decimals=2)
    if metric.metric == "apple_health_respiratory_rate_per_min":
        return timeseries(pid, metric.title, [
            target(smoothed(metric.metric, "1d", selector), "A", "Daily average"),
            target(smoothed(metric.metric, "7d", selector), "B", "7d trend"),
        ], pos, metric.unit, span_nulls=True)
    if metric.kind == "state":
        return state_panel(pid, metric.title, f'{metric.metric}{{{selector}}}', pos)
    if metric.kind == "latest":
        return stat(pid, metric.title, latest(metric.metric), pos, metric.unit)
    if metric.kind == "bounded":
        if metric.metric == "apple_health_oxygen_saturation_percent":
            return gauge(pid, metric.title, latest(metric.metric), pos, metric.unit, 0.85, 1.0, thresholds((None, "red"), (0.92, "orange"), (0.95, "green")))
        if metric.metric == "apple_health_body_mass_index":
            return gauge(pid, metric.title, latest(metric.metric), pos, metric.unit, 10, 45, thresholds((None, "blue"), (18.5, "green"), (25, "yellow"), (30, "red")))
        if metric.metric == "apple_health_body_fat_percent":
            return gauge(pid, metric.title, latest(metric.metric), pos, metric.unit, 0, 0.5, thresholds((None, "green"), (0.25, "yellow"), (0.35, "red")))
        if metric.metric == "apple_health_walking_steadiness_percent":
            return gauge(pid, metric.title, latest(metric.metric), pos, metric.unit, 0, 100, thresholds((None, "red"), (50, "yellow"), (80, "green")))
        return timeseries(pid, metric.title, [target(f'{metric.metric}{{{selector}}}', "A", metric.title)], pos, metric.unit)
    if metric.kind in {"daily_total", "workout_total"}:
        selector = 'source=~"$source",type=~"$workout_type"' if metric.kind == "workout_total" else selector
        targets = [daily_target(metric.metric, "A", metric.title, selector)]
        overrides = None
        if metric.with_trend:
            targets.extend([
                daily_trend_target(metric.metric, "7d", "B", "7d trend", selector),
                daily_trend_target(metric.metric, "30d", "C", "30d trend", selector),
            ])
            overrides = trend_overrides(["B", "C"])
        return timeseries(pid, f"Daily {metric.title}", targets, pos, metric.unit, bars=True, overrides=overrides)
    if metric.kind in {"daily_total_km", "workout_total_km"}:
        selector = 'source=~"$source",type=~"$workout_type"' if metric.kind == "workout_total_km" else selector
        targets = [daily_target(metric.metric, "A", metric.title, selector, 1000)]
        overrides = None
        if metric.with_trend:
            targets.extend([
                daily_trend_target(metric.metric, "7d", "B", "7d trend", selector, 1000),
                daily_trend_target(metric.metric, "30d", "C", "30d trend", selector, 1000),
            ])
            overrides = trend_overrides(["B", "C"])
        return timeseries(pid, f"Daily {metric.title}", targets, pos, metric.unit, bars=True, overrides=overrides)
    if metric.kind in {"daily_total_hours", "workout_total_hours"}:
        selector = 'source=~"$source",type=~"$workout_type"' if metric.kind == "workout_total_hours" else selector
        targets = [daily_target(metric.metric, "A", metric.title, selector, 3600)]
        overrides = None
        if metric.with_trend:
            targets.extend([
                daily_trend_target(metric.metric, "7d", "B", "7d trend", selector, 3600),
                daily_trend_target(metric.metric, "30d", "C", "30d trend", selector, 3600),
            ])
            overrides = trend_overrides(["B", "C"])
        return timeseries(pid, f"Daily {metric.title}", targets, pos, metric.unit, bars=True, overrides=overrides)
    if metric.kind == "workout_speed":
        return timeseries(pid, metric.title, [target(f'{metric.metric}{{source=~"$source",type=~"$workout_type"}} * 3.6', "A", "{{type}}")], pos, metric.unit)
    if metric.kind == "workout_continuous":
        return timeseries(pid, metric.title, [target(f'{metric.metric}{{source=~"$source",type=~"$workout_type"}}', "A", "{{type}}")], pos, metric.unit)
    if metric.kind == "filled_continuous":
        return timeseries(pid, metric.title, [target(filled(metric.metric), "A", metric.title)], pos, metric.unit, span_nulls=True)
    if metric.kind == "smoothed_continuous":
        return timeseries(pid, f"{metric.title} Trend", [
            target(smoothed(metric.metric, "7d"), "A", "7d trend"),
            target(smoothed(metric.metric, "30d"), "B", "30d trend"),
        ], pos, metric.unit, span_nulls=True)
    if metric.kind == "trend_continuous":
        return timeseries(pid, f"{metric.title} Trend", [
            target(f'{metric.metric}{{{selector}}}', "A", "Raw"),
            target(smoothed(metric.metric, "7d"), "B", "7d trend"),
            target(smoothed(metric.metric, "30d"), "C", "30d trend"),
        ], pos, metric.unit, span_nulls=True)
    return timeseries(pid, metric.title, [target(f'{metric.metric}{{{selector}}}', "A", metric.title)], pos, metric.unit)


def weekly_exercise_panel(pid: int, pos: dict[str, int]) -> dict[str, Any]:
    selector = 'source=~"$source"'
    return timeseries(pid, "Weekly Exercise Time", [
        weekly_target("apple_health_exercise_time_min", "A", "Week total", selector),
        daily_trend_target("apple_health_exercise_time_min", "7d", "B", "7d daily avg", selector),
    ], pos, "min", bars=True, overrides=trend_overrides(["B"]))


def build_gallery() -> dict[str, Any]:
    dash = dashboard_base("apple-health-metrics-gallery", "Apple Health - All Metrics Gallery")
    panels: list[dict[str, Any]] = []
    pid = 1
    y = 0
    for domain in ["Cardio", "Activity", "Sleep", "Body", "Respiratory", "Metabolic", "Nutrition", "Mobility", "Environment", "Safety", "Workouts"]:
        domain_metrics = [m for m in METRICS if m.domain == domain]
        panels.append(row(pid, domain, y))
        pid += 1
        y += 1
        if domain == "Cardio":
            panels.append(timeseries(pid, "Blood Pressure", [
                target(filled("apple_health_blood_pressure_systolic_mmhg"), "A", "Systolic"),
                target(filled("apple_health_blood_pressure_diastolic_mmhg"), "B", "Diastolic"),
            ], {"h": 7, "w": 12, "x": 0, "y": y}, "mmHg", thresholds_=thresholds((None, "green"), (120, "yellow"), (140, "red")), span_nulls=True))
            pid += 1
            domain_metrics = [m for m in domain_metrics if not m.metric.startswith("apple_health_blood_pressure_")]
            reserved_slots = 2
        elif domain == "Sleep":
            panels.append(timeseries(pid, "Sleep Trends", [
                target(sleep_hours(), "A", "Total sleep"),
                target(sleep_hours(stage='stage="Deep"'), "B", "Deep sleep"),
                target(sleep_hours(stage='stage="REM"'), "C", "REM sleep"),
                target(sleep_hours(stage='stage="Awake"'), "D", "Awake"),
            ], {"h": 7, "w": 12, "x": 0, "y": y}, SLEEP_TIMESERIES_UNIT, span_nulls=True))
            pid += 1
            panels.append(timeseries(pid, "Sleep Trends - 7d Average", [
                target(sleep_trend_seconds("7d"), "A", "Total sleep 7d"),
                target(sleep_trend_seconds("7d", stage='stage="Deep"'), "B", "Deep sleep 7d"),
                target(sleep_trend_seconds("7d", stage='stage="REM"'), "C", "REM sleep 7d"),
                target(sleep_trend_seconds("7d", stage='stage="Awake"'), "D", "Awake 7d"),
            ], {"h": 7, "w": 12, "x": 12, "y": y}, SLEEP_DURATION_UNIT, span_nulls=True, decimals=1))
            pid += 1
            y += 7
            panels.append(timeseries(pid, "Sleep Trends - 30d Average", [
                target(sleep_trend_seconds("30d"), "A", "Total sleep 30d"),
                target(sleep_trend_seconds("30d", stage='stage="Deep"'), "B", "Deep sleep 30d"),
                target(sleep_trend_seconds("30d", stage='stage="REM"'), "C", "REM sleep 30d"),
                target(sleep_trend_seconds("30d", stage='stage="Awake"'), "D", "Awake 30d"),
            ], {"h": 7, "w": 12, "x": 0, "y": y}, SLEEP_DURATION_UNIT, span_nulls=True, decimals=1))
            pid += 1
            panels.append(timeseries(pid, "Daily Sleep Time", [
                target(sleep_seconds(), "A", "Sleep Time", interval="1d"),
            ], {"h": 7, "w": 6, "x": 12, "y": y}, "dtdurations", bars=True))
            pid += 1
            bedtime_panel = stat(pid, "Last Bedtime", bedtime_ms(), {"h": 7, "w": 6, "x": 18, "y": y}, "dateTimeAsLocal")
            bedtime_panel["options"]["graphMode"] = "none"
            panels.append(bedtime_panel)
            pid += 1
            panels.append(timeseries(pid, "Bedtime Trend", [
                target(bedtime_sleep_night_ms(), "A", "Bedtime", interval="1d"),
                target(bedtime_clock_trend_ms("7d"), "B", "7d trend", interval="1d"),
            ], {"h": 7, "w": 24, "x": 0, "y": y + 7}, "clockms", span_nulls=True, overrides=trend_overrides(["B"]), min_=SLEEP_NIGHT_MIN_MILLISECONDS, max_=SLEEP_NIGHT_MAX_MILLISECONDS))
            pid += 1
            domain_metrics = [m for m in domain_metrics if m.metric != "apple_health_sleep_stage"]
            reserved_slots = 8
        else:
            reserved_slots = 0
        extra_panels = 0
        for i, metric in enumerate(domain_metrics):
            x_index = i + reserved_slots
            pos = grid(x_index, 6, 7, y)
            panels.append(panel_for_metric(pid, metric, pos))
            pid += 1
        if domain == "Activity":
            x_index = len(domain_metrics) + reserved_slots
            panels.append(weekly_exercise_panel(pid, grid(x_index, 6, 7, y)))
            pid += 1
            extra_panels = 1
        rows = max(1, (len(domain_metrics) + extra_panels + reserved_slots + 3) // 4)
        y += rows * 7
    dash["panels"] = panels
    return dash


def build_clinical() -> dict[str, Any]:
    dash = dashboard_base("apple-health-clinical-deep-dive", "Apple Health - Clinical Deep Dive")
    panels: list[dict[str, Any]] = []
    pid = 1
    stats = [
        ("Resting HR", latest("apple_health_resting_heart_rate_bpm"), "bpm", thresholds((None, "blue"), (40, "green"), (80, "orange"), (100, "red"))),
        ("HRV SDNN", latest("apple_health_heart_rate_variability_ms"), "ms", None),
        ("Oxygen Saturation", latest("apple_health_oxygen_saturation_percent"), "percentunit", thresholds((None, "red"), (0.92, "orange"), (0.95, "green"))),
        ("Blood Glucose", latest("apple_health_blood_glucose_mg_dl"), "mg/dL", thresholds((None, "blue"), (70, "green"), (140, "orange"), (180, "red"))),
        ("BMI", latest("apple_health_body_mass_index"), "short", thresholds((None, "blue"), (18.5, "green"), (25, "yellow"), (30, "red"))),
        ("Walking Steadiness", latest("apple_health_walking_steadiness_percent"), "percentunit", thresholds((None, "red"), (50, "yellow"), (80, "green"))),
    ]
    for i, (title, expr, unit, thr) in enumerate(stats):
        panels.append(stat(pid, title, expr, grid(i, 4, 4, 0), unit, thr))
        pid += 1
    y = 4
    panels.append(row(pid, "Cardiovascular", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Heart Rate Envelope", [
        target('apple_health_heart_rate_bpm{source=~"$source"}', "A", "Heart rate"),
        target(filled("apple_health_resting_heart_rate_bpm"), "B", "Resting"),
        target(filled("apple_health_walking_heart_rate_avg_bpm"), "C", "Walking avg"),
        target(smoothed("apple_health_walking_heart_rate_avg_bpm", "7d"), "D", "Walking 7d"),
        target(smoothed("apple_health_walking_heart_rate_avg_bpm", "30d"), "E", "Walking 30d"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "bpm", thresholds_=thresholds((None, "blue"), (50, "green"), (100, "orange"), (130, "red")), span_nulls=True))
    pid += 1
    panels.append(timeseries(pid, "Blood Pressure", [
        target(filled("apple_health_blood_pressure_systolic_mmhg"), "A", "Systolic"),
        target(filled("apple_health_blood_pressure_diastolic_mmhg"), "B", "Diastolic"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "mmHg", thresholds_=thresholds((None, "green"), (120, "yellow"), (140, "red")), span_nulls=True))
    pid += 1
    y += 8
    panels.append(timeseries(pid, "HRV SDNN Trend", [
        target('apple_health_heart_rate_variability_ms{source=~"$source"}', "A", "Raw HRV"),
        target(smoothed("apple_health_heart_rate_variability_ms", "7d"), "B", "7d trend"),
        target(smoothed("apple_health_heart_rate_variability_ms", "30d"), "C", "30d trend"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "ms", span_nulls=True))
    pid += 1
    panels.append(timeseries(pid, "Walking Heart Rate Trend", [
        target('apple_health_walking_heart_rate_avg_bpm{source=~"$source"}', "A", "Raw"),
        target(smoothed("apple_health_walking_heart_rate_avg_bpm", "7d"), "B", "7d trend"),
        target(smoothed("apple_health_walking_heart_rate_avg_bpm", "30d"), "C", "30d trend"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "bpm", span_nulls=True))
    pid += 1
    y += 8
    panels.append(timeseries(pid, "Resting Heart Rate Trend", [
        target('apple_health_resting_heart_rate_bpm{source=~"$source"}', "A", "Raw"),
        target(smoothed("apple_health_resting_heart_rate_bpm", "7d"), "B", "7d trend"),
        target(smoothed("apple_health_resting_heart_rate_bpm", "30d"), "C", "30d trend"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "bpm", span_nulls=True))
    pid += 1
    panels.append(timeseries(pid, "VO2 Max Trend", [
        target(filled("apple_health_vo2_max_ml_kg_min"), "A", "VO2 max"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "mL/kg/min", span_nulls=True))
    pid += 1
    y += 8
    panels.append(timeseries(pid, "Oxygen Saturation", [target('apple_health_oxygen_saturation_percent{source=~"$source"}', "A", "SpO2")], {"h": 8, "w": 12, "x": 0, "y": y}, "percentunit", thresholds_=thresholds((None, "red"), (0.92, "orange"), (0.95, "green"))))
    pid += 1
    y += 8
    panels.append(row(pid, "Metabolic and Body Composition", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Blood Glucose", [target('apple_health_blood_glucose_mg_dl{source=~"$source"}', "A", "Glucose")], {"h": 8, "w": 12, "x": 0, "y": y}, "mg/dL", thresholds_=thresholds((None, "blue"), (70, "green"), (140, "orange"), (180, "red")), description="Informational thresholds only; context such as fasting state is not exported."))
    pid += 1
    panels.append(timeseries(pid, "Body Composition", [
        target(filled("apple_health_body_mass_kg"), "A", "Weight"),
        target('apple_health_body_mass_index{source=~"$source"}', "B", "BMI"),
        target('apple_health_body_fat_percent{source=~"$source"}', "C", "Body fat"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "short", span_nulls=True))
    pid += 1
    y += 8
    panels.append(row(pid, "Respiratory and Mobility", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Respiratory Markers", [
        target('apple_health_respiratory_rate_per_min{source=~"$source"}', "A", "Respiratory rate"),
        target('apple_health_forced_expiratory_volume_l{source=~"$source"}', "B", "FEV1"),
        target('apple_health_forced_vital_capacity_l{source=~"$source"}', "C", "FVC"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "short"))
    pid += 1
    panels.append(timeseries(pid, "Mobility Stability", [
        target('apple_health_walking_speed_m_per_sec{source=~"$source"}', "A", "Walking speed"),
        target('apple_health_walking_asymmetry_percent{source=~"$source"}', "B", "Asymmetry"),
        target('apple_health_walking_double_support_percent{source=~"$source"}', "C", "Double support"),
        target('apple_health_walking_steadiness_percent{source=~"$source"}', "D", "Steadiness"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "short"))
    dash["panels"] = panels
    return dash


def build_readiness() -> dict[str, Any]:
    dash = dashboard_base("apple-health-readiness", "Apple Health - Readiness")
    panels: list[dict[str, Any]] = []
    pid = 1
    selector = 'source=~"$source"'
    workout_selector = 'source=~"$source",type=~"$workout_type"'
    score = readiness_score(selector, workout_selector)
    load_7d = training_load_7d(workout_selector)
    load_ratio = training_load_ratio(workout_selector)
    sleep_1d = sleep_seconds(selector)
    sleep_1d_hours = sleep_hours(selector)
    alcohol_1d = daily("apple_health_alcohol_consumption_grams", selector)

    stats = [
        ("Readiness", score, "percent", thresholds((None, "red"), (45, "orange"), (65, "yellow"), (80, "green"))),
        ("7d Training Load", load_7d, "kcal", thresholds((None, "green"), (3000, "yellow"), (5000, "orange"), (7000, "red"))),
        ("Load Ratio", load_ratio, "short", thresholds((None, "green"), (1.2, "yellow"), (1.5, "orange"), (2, "red"))),
        ("Sleep Duration", sleep_1d, "dtdurations", thresholds((None, "red"), (21600, "yellow"), (25200, "green"))),
        ("Alcohol Today", alcohol_1d, "g", thresholds((None, "green"), (1, "yellow"), (15, "orange"), (30, "red"))),
        ("Resting HR", latest("apple_health_resting_heart_rate_bpm", selector), "bpm", thresholds((None, "blue"), (40, "green"), (80, "orange"), (100, "red"))),
    ]
    for i, (title, expr, unit, thr) in enumerate(stats):
        panels.append(stat(pid, title, expr, grid(i, 4, 4, 0), unit, thr))
        pid += 1

    y = 4
    panels.append(row(pid, "Readiness and Load", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Morning Readiness Score", [
        target(score, "A", "Readiness"),
        target(f'100 - (10 * clamp_min(({load_ratio}) - 1, 0))', "B", "Load penalty"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "percent", bars=True, thresholds_=thresholds((None, "red"), (45, "orange"), (65, "yellow"), (80, "green")), overrides=trend_overrides(["A", "B"])))
    pid += 1
    panels.append(timeseries(pid, "Weekly Training Load", [
        target(training_load_daily(workout_selector), "A", "Daily workout kcal"),
        target(load_7d, "B", "7d load"),
        target(f'sum(sum_over_time(apple_health_workout_energy_kcal{{{workout_selector}}}[28d])) / 4', "C", "28d weekly avg"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "kcal", bars=True, overrides=trend_overrides(["B", "C"])))
    pid += 1
    y += 8

    panels.append(row(pid, "Sleep Consistency", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Sleep Duration and Stage Mix", [
        target(sleep_1d_hours, "A", "Total sleep"),
        target(sleep_hours(selector, stage='stage="Deep"'), "B", "Deep sleep"),
        target(sleep_hours(selector, stage='stage="REM"'), "C", "REM sleep"),
        target(sleep_hours(selector, stage='stage="Awake"'), "D", "Awake"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, SLEEP_TIMESERIES_UNIT, bars=True, stacked=True))
    pid += 1
    panels.append(timeseries(pid, "Sleep Regularity Proxy", [
        target(sleep_1d_hours, "A", "Today"),
        target(f'avg_over_time(({sleep_1d_hours})[7d:1d])', "B", "7d avg"),
        target(f'stddev_over_time(({sleep_1d_hours})[7d:1d])', "C", "7d variability"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, SLEEP_TIMESERIES_UNIT, bars=True, overrides=trend_overrides(["B", "C"])))
    pid += 1
    y += 8
    panels.append(state_panel(pid, "Sleep Stages", 'apple_health_sleep_stage{source=~"$source"}', {"h": 8, "w": 24, "x": 0, "y": y}))
    pid += 1
    y += 8

    panels.append(row(pid, "Alcohol and Recovery Context", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Alcohol and BAC", [
        target(alcohol_1d, "A", "Alcohol grams"),
        target('last_over_time(apple_health_blood_alcohol_content_percent{source=~"$source"}[$__range])', "B", "BAC"),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "short", bars=True, overrides=trend_overrides(["B"]), span_nulls=True))
    pid += 1
    panels.append(timeseries(pid, "Recovery Markers", [
        target(smoothed("apple_health_heart_rate_variability_ms", "7d", selector), "A", "HRV 7d"),
        target(smoothed("apple_health_heart_rate_variability_ms", "30d", selector), "B", "HRV 30d"),
        target(smoothed("apple_health_resting_heart_rate_bpm", "7d", selector), "C", "Resting HR 7d"),
        target(smoothed("apple_health_resting_heart_rate_bpm", "30d", selector), "D", "Resting HR 30d"),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "short", span_nulls=True))
    pid += 1
    y += 8

    panels.append(row(pid, "Illness Proxy", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Recovery Strain Proxy", [
        target(f'(({smoothed("apple_health_resting_heart_rate_bpm", "7d", selector)}) - ({smoothed("apple_health_resting_heart_rate_bpm", "30d", selector)}))', "A", "Resting HR elevation"),
        target(f'(({smoothed("apple_health_heart_rate_variability_ms", "30d", selector)}) - ({smoothed("apple_health_heart_rate_variability_ms", "7d", selector)}))', "B", "HRV drop"),
        target(f'8 - ({sleep_1d_hours})', "C", "Sleep debt"),
    ], {"h": 8, "w": 24, "x": 0, "y": y}, "short", span_nulls=True, description="Proxy only: this dashboard does not export manual illness tags."))

    dash["panels"] = panels
    return dash


def build_workouts() -> dict[str, Any]:
    workout_id_variable = {
        "name": "workout_id",
        "type": "query",
        "datasource": DS,
        "definition": 'label_values(apple_health_workout_duration_seconds{source=~"$source",type=~"$workout_type"}, workout_id)',
        "query": 'label_values(apple_health_workout_duration_seconds{source=~"$source",type=~"$workout_type"}, workout_id)',
        "label": "Workout",
        "includeAll": True,
        "multi": True,
        "current": {"text": "All", "value": "$__all"},
    }
    dash = dashboard_base("apple-health-workouts", "Apple Health - Workouts", extra_variables=[workout_id_variable])
    panels: list[dict[str, Any]] = []
    pid = 1
    selector = 'source=~"$source",type=~"$workout_type",workout_id=~"$workout_id"'

    stats = [
        ("Workout Duration", latest("apple_health_workout_duration_seconds", selector), "dtdurations", None),
        ("Calories Burned", latest("apple_health_workout_energy_kcal", selector), "kcal", None),
        ("Average HR", latest("apple_health_workout_heart_rate_bpm", selector), "bpm", thresholds((None, "green"), (140, "yellow"), (170, "orange"), (190, "red"))),
        ("Distance", f'{latest("apple_health_workout_distance_m", selector)} / 1000', "km", None),
        ("Average Speed", f'{latest("apple_health_workout_avg_speed_m_per_sec", selector)} * 3.6', "km/h", None),
        ("Route Points", f'sum(count_over_time(apple_health_workout_route_latitude_degrees{{{selector}}}[$__range]))', "short", None),
    ]
    for i, (title, expr, unit, thr) in enumerate(stats):
        panels.append(stat(pid, title, expr, grid(i, 4, 4, 0), unit, thr))
        pid += 1

    y = 4
    panels.append(row(pid, "Selected Workout", y))
    pid += 1
    y += 1
    panels.append(workout_route_map(pid, {"h": 14, "w": 14, "x": 0, "y": y}))
    pid += 1
    panels.append(timeseries(pid, "Workout Heart Rate", [
        target(f'apple_health_workout_heart_rate_bpm{{{selector}}}', "A", "Avg HR"),
    ], {"h": 7, "w": 10, "x": 14, "y": y}, "bpm", span_nulls=True))
    pid += 1
    panels.append(timeseries(pid, "Route Speed and Elevation", [
        target(f'apple_health_workout_route_speed_m_per_sec{{{selector}}} * 3.6', "A", "Route speed"),
        target(f'apple_health_workout_route_altitude_m{{{selector}}}', "B", "Altitude"),
        target(f'apple_health_workout_route_horizontal_accuracy_m{{{selector}}}', "C", "GPS accuracy"),
    ], {"h": 7, "w": 10, "x": 14, "y": y + 7}, "short", span_nulls=True))
    pid += 1
    y += 14

    panels.append(row(pid, "Workout History", y))
    pid += 1
    y += 1
    panels.append(timeseries(pid, "Workout Load by Day", [
        daily_target("apple_health_workout_duration_seconds", "A", "Hours", selector, 3600),
        daily_target("apple_health_workout_energy_kcal", "B", "Calories", selector),
        daily_target("apple_health_workout_distance_m", "C", "Distance km", selector, 1000),
    ], {"h": 8, "w": 12, "x": 0, "y": y}, "short", bars=True))
    pid += 1
    panels.append(timeseries(pid, "Workout Trends", [
        daily_trend_target("apple_health_workout_duration_seconds", "7d", "A", "Hours 7d", selector, 3600),
        daily_trend_target("apple_health_workout_energy_kcal", "7d", "B", "Calories 7d", selector),
        daily_trend_target("apple_health_workout_distance_m", "7d", "C", "Distance 7d", selector, 1000),
        daily_trend_target("apple_health_workout_duration_seconds", "30d", "D", "Hours 30d", selector, 3600),
        daily_trend_target("apple_health_workout_energy_kcal", "30d", "E", "Calories 30d", selector),
    ], {"h": 8, "w": 12, "x": 12, "y": y}, "short", bars=True, span_nulls=True, overrides=trend_overrides(["A", "B", "C", "D", "E"])))
    pid += 1
    y += 8
    panels.append(table_panel(pid, "Workout Route Metrics", [
        target(f'count by (workout_id, type, start_date) (apple_health_workout_route_latitude_degrees{{{selector}}})', "A", "Route points", instant=True),
    ], {"h": 8, "w": 24, "x": 0, "y": y}))

    dash["panels"] = panels
    return dash


def write_dashboard(dashboard: dict[str, Any], filename: str) -> None:
    DASHBOARDS_DIR.mkdir(exist_ok=True)
    PROVISIONING_DIR.mkdir(parents=True, exist_ok=True)
    out = DASHBOARDS_DIR / filename
    out.write_text(json.dumps(dashboard, indent=2, sort_keys=False) + "\n")
    shutil.copy2(out, PROVISIONING_DIR / filename)


def main() -> None:
    generated = {
        "apple-health-overview.json": build_overview(),
        "apple-health-daily-ops.json": build_daily_ops(),
        "apple-health-metrics-gallery.json": build_gallery(),
        "apple-health-clinical-deep-dive.json": build_clinical(),
        "apple-health-readiness.json": build_readiness(),
        "apple-health-workouts.json": build_workouts(),
    }
    for filename, dashboard in generated.items():
        write_dashboard(dashboard, filename)


if __name__ == "__main__":
    main()
