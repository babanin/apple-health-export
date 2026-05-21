import json
import os
import time
from pathlib import Path

import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]
DASHBOARDS_DIR = ROOT / "dashboards"
PROVISIONING_DIR = ROOT / "grafana" / "provisioning" / "dashboards"
DATASOURCE_PATH = ROOT / "grafana" / "provisioning" / "datasources" / "datasource.yml"
DATASOURCE_UID = "victoriametrics"

EXPECTED_DASHBOARDS = {
    "apple-health-dashboard.json": "apple-health-all-metrics",
    "apple-health-overview.json": "apple-health-overview",
    "apple-health-daily-ops.json": "apple-health-daily-ops",
    "apple-health-metrics-gallery.json": "apple-health-metrics-gallery",
    "apple-health-clinical-deep-dive.json": "apple-health-clinical-deep-dive",
    "apple-health-readiness.json": "apple-health-readiness",
    "apple-health-workouts.json": "apple-health-workouts",
}

GENERATED_DASHBOARDS = {
    "apple-health-overview.json",
    "apple-health-daily-ops.json",
    "apple-health-metrics-gallery.json",
    "apple-health-clinical-deep-dive.json",
    "apple-health-readiness.json",
    "apple-health-workouts.json",
}

ADDITIVE_METRICS = {
    "apple_health_steps_total",
    "apple_health_distance_walking_running_m",
    "apple_health_distance_cycling_m",
    "apple_health_distance_swimming_m",
    "apple_health_flights_climbed_total",
    "apple_health_active_energy_burned_kcal",
    "apple_health_basal_energy_burned_kcal",
    "apple_health_exercise_time_min",
    "apple_health_stand_time_min",
    "apple_health_move_time_min",
    "apple_health_insulin_delivery_iu",
    "apple_health_caffeine_consumption_mg",
    "apple_health_alcohol_consumption_grams",
    "apple_health_dietary_energy_kcal",
    "apple_health_dietary_carbohydrates_g",
    "apple_health_dietary_protein_g",
    "apple_health_dietary_fat_total_g",
    "apple_health_water_consumption_ml",
    "apple_health_time_in_daylight_seconds",
    "apple_health_number_of_times_fallen_total",
    "apple_health_workout_duration_seconds",
    "apple_health_workout_energy_kcal",
    "apple_health_workout_distance_m",
}

CATEGORY_METRICS = {
    "apple_health_sleep_stage",
    "apple_health_stand_hour",
}

BOUNDED_GAUGE_METRICS = {
    "apple_health_oxygen_saturation_percent",
    "apple_health_body_mass_index",
    "apple_health_body_fat_percent",
    "apple_health_walking_steadiness_percent",
}


def load_dashboard(filename):
    with open(DASHBOARDS_DIR / filename) as f:
        return json.load(f)


def iter_panels(dashboard):
    for panel in dashboard["panels"]:
        yield panel
        for nested in panel.get("panels", []):
            yield nested


def iter_targets(panel):
    return panel.get("targets", [])


def iter_datasources(value):
    if isinstance(value, dict):
        if value.get("type") == "prometheus" and "uid" in value:
            yield value
        for nested in value.values():
            yield from iter_datasources(nested)
    elif isinstance(value, list):
        for item in value:
            yield from iter_datasources(item)


@pytest.mark.parametrize("filename,uid", EXPECTED_DASHBOARDS.items())
def test_dashboard_json_valid(filename, uid):
    data = load_dashboard(filename)

    assert data["uid"] == uid
    assert "title" in data
    assert "panels" in data
    assert len(data["panels"]) > 0


@pytest.mark.parametrize("filename", GENERATED_DASHBOARDS)
def test_generated_dashboard_is_provisioned(filename):
    dashboard_path = DASHBOARDS_DIR / filename
    provisioned_path = PROVISIONING_DIR / filename

    assert provisioned_path.exists()
    assert json.loads(dashboard_path.read_text()) == json.loads(
        provisioned_path.read_text()
    )


def test_original_dashboard_still_has_all_metric_panels():
    data = load_dashboard("apple-health-dashboard.json")
    metric_panels = [p for p in iter_panels(data) if p.get("type") != "row"]

    assert len(metric_panels) >= 50


def test_original_dashboard_thresholds_are_preserved():
    data = load_dashboard("apple-health-dashboard.json")

    threshold_panels = {}
    for panel in iter_panels(data):
        if panel.get("type") == "row":
            continue
        fc = panel.get("fieldConfig", {}).get("defaults", {})
        steps = fc.get("thresholds", {}).get("steps", [])
        if len(steps) > 1:
            threshold_panels[panel.get("title")] = steps

    assert "Blood Oxygen" in threshold_panels
    heart_rate_thresholds = threshold_panels.get("Heart Rate Now", [])
    assert any(step.get("value") == 50 for step in heart_rate_thresholds)


def test_datasource_has_stable_uid():
    datasource_config = DATASOURCE_PATH.read_text()

    assert f"uid: {DATASOURCE_UID}" in datasource_config


@pytest.mark.parametrize("filename,uid", EXPECTED_DASHBOARDS.items())
def test_dashboards_reference_provisioned_datasource_uid(filename, uid):
    dashboard_paths = [DASHBOARDS_DIR / filename, PROVISIONING_DIR / filename]

    for dashboard_path in dashboard_paths:
        data = json.loads(dashboard_path.read_text())
        datasource_uids = {
            datasource["uid"]
            for datasource in iter_datasources(data)
            if datasource["uid"] != "-- Grafana --"
        }
        assert datasource_uids
        assert datasource_uids == {DATASOURCE_UID}
        assert "DS_VICTORIAMETRICS" not in json.dumps(data)


def test_hrv_dashboards_include_smoothed_trends():
    hrv_7d = (
        'avg_over_time(apple_health_heart_rate_variability_ms{source=~"$source"}[7d])'
    )
    hrv_30d = (
        'avg_over_time(apple_health_heart_rate_variability_ms{source=~"$source"}[30d])'
    )

    for filename in (
        "apple-health-metrics-gallery.json",
        "apple-health-clinical-deep-dive.json",
    ):
        data = load_dashboard(filename)
        expressions = " ".join(
            target.get("expr", "")
            for panel in iter_panels(data)
            for target in iter_targets(panel)
        )

        assert hrv_7d in expressions
        assert hrv_30d in expressions


@pytest.mark.parametrize(
    "filename",
    (
        "apple-health-metrics-gallery.json",
        "apple-health-clinical-deep-dive.json",
    ),
)
def test_blood_pressure_panels_use_forward_filled_queries(filename):
    data = load_dashboard(filename)
    panels = {panel.get("title"): panel for panel in iter_panels(data)}
    panel = panels["Blood Pressure"]
    expressions = [target["expr"] for target in iter_targets(panel)]

    assert expressions == [
        'last_over_time(apple_health_blood_pressure_systolic_mmhg{source=~"$source"}[$__range])',
        'last_over_time(apple_health_blood_pressure_diastolic_mmhg{source=~"$source"}[$__range])',
    ]
    assert panel["fieldConfig"]["defaults"]["custom"]["spanNulls"] is True


@pytest.mark.parametrize("filename", GENERATED_DASHBOARDS)
def test_source_variable_lists_all_apple_health_sources(filename):
    data = load_dashboard(filename)
    variables = {item["name"]: item for item in data["templating"]["list"]}

    assert variables["source"]["query"] == 'label_values({__name__=~"apple_health_.*"}, source)'


def test_respiratory_rate_dashboards_use_smoothed_trends():
    raw_resp = 'apple_health_respiratory_rate_per_min{source=~"$source"}'
    resp_1d = 'avg_over_time(apple_health_respiratory_rate_per_min{source=~"$source"}[1d])'
    resp_7d = 'avg_over_time(apple_health_respiratory_rate_per_min{source=~"$source"}[7d])'

    for filename in (
        "apple-health-overview.json",
        "apple-health-metrics-gallery.json",
    ):
        data = load_dashboard(filename)
        expressions = [
            target.get("expr", "")
            for panel in iter_panels(data)
            for target in iter_targets(panel)
        ]

        assert resp_1d in expressions
        assert resp_7d in expressions
        assert raw_resp not in expressions


def test_exercise_time_daily_and_weekly_panels_use_bucketed_intervals():
    data = load_dashboard("apple-health-metrics-gallery.json")
    panels = {panel.get("title"): panel for panel in iter_panels(data)}

    daily_panel = panels["Daily Exercise Time"]
    daily_targets = {target["refId"]: target for target in iter_targets(daily_panel)}

    assert daily_targets["A"]["expr"] == (
        'sum(sum_over_time(apple_health_exercise_time_min{source=~"$source"}[1d]))'
    )
    assert daily_targets["A"]["interval"] == "1d"
    assert daily_targets["B"]["legendFormat"] == "7d trend"
    assert daily_targets["B"]["interval"] == "1d"

    weekly_panel = panels["Weekly Exercise Time"]
    weekly_targets = {target["refId"]: target for target in iter_targets(weekly_panel)}

    assert weekly_targets["A"]["expr"] == (
        'sum(sum_over_time(apple_health_exercise_time_min{source=~"$source"}[7d]))'
    )
    assert weekly_targets["A"]["legendFormat"] == "Week total"
    assert weekly_targets["A"]["interval"] == "7d"
    assert weekly_targets["B"]["legendFormat"] == "7d daily avg"
    assert weekly_targets["B"]["interval"] == "1d"


def test_sleep_timeseries_panels_use_hours_axis():
    expected_panels_by_file = {
        "apple-health-metrics-gallery.json": {
            "Sleep Trends",
            "Sleep Trends - 7d Average",
            "Sleep Trends - 30d Average",
        },
        "apple-health-readiness.json": {
            "Sleep Duration and Stage Mix",
            "Sleep Regularity Proxy",
        },
    }

    for filename, expected_panels in expected_panels_by_file.items():
        data = load_dashboard(filename)
        panels = {
            panel.get("title"): panel
            for panel in iter_panels(data)
            if panel.get("title") in expected_panels
        }

        assert set(panels) == expected_panels

        for title, panel in panels.items():
            defaults = panel["fieldConfig"]["defaults"]
            expressions = [target["expr"] for target in iter_targets(panel)]

            assert defaults["unit"] == "h", f"{filename}: {title}"
            assert all("present_over_time" in expr for expr in expressions), (
                f"{filename}: {title}"
            )
            assert all(" / 3600" in expr for expr in expressions), (
                f"{filename}: {title}"
            )


@pytest.mark.parametrize("filename", EXPECTED_DASHBOARDS)
def test_sleep_duration_queries_deduplicate_minute_buckets(filename):
    data = load_dashboard(filename)
    sleep_expressions = [
        target.get("expr", "")
        for panel in iter_panels(data)
        for target in iter_targets(panel)
        if "apple_health_sleep_stage" in target.get("expr", "")
        and any(
            function_name in target.get("expr", "")
            for function_name in ("count_over_time", "sum_over_time")
        )
    ]

    assert all("count_over_time" not in expr for expr in sleep_expressions)
    assert all("present_over_time" in expr for expr in sleep_expressions)


def test_workout_route_map_uses_prometheus_field_names():
    data = load_dashboard("apple-health-workouts.json")
    panels = {panel.get("title"): panel for panel in iter_panels(data)}

    route_panel = panels["Outdoor Workout Route"]
    for layer in route_panel["options"]["layers"]:
        location = layer["config"]["location"]
        assert location["latitude"] == "apple_health_workout_route_latitude_degrees"
        assert location["longitude"] == "apple_health_workout_route_longitude_degrees"


def test_workout_route_points_counts_over_dashboard_range():
    data = load_dashboard("apple-health-workouts.json")
    panels = {panel.get("title"): panel for panel in iter_panels(data)}

    route_points_panel = panels["Route Points"]
    expressions = [target["expr"] for target in iter_targets(route_points_panel)]

    assert expressions == [
        (
            'sum(count_over_time(apple_health_workout_route_latitude_degrees{'
            'source=~"$source",type=~"$workout_type",workout_id=~"$workout_id"'
            "}[$__range]))"
        )
    ]


@pytest.mark.parametrize("filename", GENERATED_DASHBOARDS)
def test_generated_dashboards_use_template_variables(filename):
    data = load_dashboard(filename)
    variable_names = {item["name"] for item in data["templating"]["list"]}

    assert "source" in variable_names

    metric_panels = [p for p in iter_panels(data) if p.get("type") != "row"]
    panels_with_source_var = [
        p
        for p in metric_panels
        if any("$source" in t.get("expr", "") for t in iter_targets(p))
    ]
    assert panels_with_source_var


@pytest.mark.parametrize("filename", GENERATED_DASHBOARDS)
def test_generated_panel_queries_use_correct_metric_names(filename):
    data = load_dashboard(filename)

    for panel in iter_panels(data):
        if panel.get("type") == "row":
            continue
        for target in iter_targets(panel):
            expr = target.get("expr", "")
            if expr and "label_values" not in expr:
                assert "apple_health_" in expr, (
                    f"Panel '{panel.get('title', 'unknown')}' query does not "
                    f"use an apple_health_ metric: {expr}"
                )


@pytest.mark.parametrize("filename", GENERATED_DASHBOARDS)
def test_generated_dashboards_apply_chart_type_policy(filename):
    data = load_dashboard(filename)

    for panel in iter_panels(data):
        if panel.get("type") == "row":
            continue
        expressions = " ".join(t.get("expr", "") for t in iter_targets(panel))

        if any(metric in expressions for metric in CATEGORY_METRICS):
            assert panel["type"] in {
                "piechart",
                "state-timeline",
                "status-history",
                "timeseries",
                "stat",
            }
            if panel["type"] in {"timeseries", "stat"}:
                assert (
                    "count_over_time(" in expressions
                    or "present_over_time(" in expressions
                )

        if any(metric in expressions for metric in ADDITIVE_METRICS):
            if panel["type"] == "timeseries":
                custom = panel["fieldConfig"]["defaults"].get("custom", {})
                assert custom.get("drawStyle") == "bars"
                assert (
                    "sum_over_time(" in expressions
                    or "count_over_time(" in expressions
                )

        if panel["type"] == "gauge":
            assert any(metric in expressions for metric in BOUNDED_GAUGE_METRICS)


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_TESTS") != "1",
    reason="Grafana provisioning tests require Docker stack (RUN_DOCKER_TESTS=1)",
)
class TestGrafanaProvisioning:
    @pytest.fixture(scope="class", autouse=True)
    def grafana_session(self):
        session = requests.Session()
        session.auth = ("admin", "admin")
        for _ in range(60):
            try:
                r = session.get("http://localhost:3000/api/health", timeout=2)
                if r.status_code == 200:
                    break
            except requests.ConnectionError:
                time.sleep(2)

        yield session

    def test_datasource_provisioned(self, grafana_session):
        r = grafana_session.get("http://localhost:3000/api/datasources", timeout=5)
        assert r.status_code == 200
        datasources = r.json()
        vm_ds = [ds for ds in datasources if ds.get("type") == "prometheus"]
        assert len(vm_ds) >= 1
        assert any(ds["name"] == "Victoria Metrics" for ds in vm_ds)

    @pytest.mark.parametrize("uid", EXPECTED_DASHBOARDS.values())
    def test_dashboard_auto_imported(self, grafana_session, uid):
        r = grafana_session.get(
            f"http://localhost:3000/api/dashboards/uid/{uid}",
            timeout=5,
        )
        assert r.status_code == 200
        data = r.json()
        assert "dashboard" in data
        assert data["dashboard"]["uid"] == uid
