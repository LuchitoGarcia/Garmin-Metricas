"""Descarga de metricas de Garmin Connect.

Cada funcion devuelve un dict con los datos crudos ya filtrados a lo
relevante. Si una metrica no esta disponible en tu dispositivo, la
funcion devuelve None silenciosamente y el resto del informe sigue.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from garminconnect import Garmin


def _safe(fn, *args, **kwargs):
    """Llama a una funcion y captura cualquier error devolviendo None."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def fetch_user_profile(client: Garmin) -> dict[str, Any]:
    return {
        "full_name": _safe(client.get_full_name),
        "unit_system": _safe(client.get_unit_system),
        "user_summary": _safe(client.get_user_summary, date.today().isoformat()),
    }


def fetch_daily_summary(client: Garmin, day: date) -> dict[str, Any] | None:
    return _safe(client.get_stats_and_body, day.isoformat())


def fetch_sleep(client: Garmin, day: date) -> dict[str, Any] | None:
    return _safe(client.get_sleep_data, day.isoformat())


def fetch_heart_rate(client: Garmin, day: date) -> dict[str, Any] | None:
    return _safe(client.get_heart_rates, day.isoformat())


def fetch_stress(client: Garmin, day: date) -> dict[str, Any] | None:
    return _safe(client.get_stress_data, day.isoformat())


def fetch_body_battery(client: Garmin, day: date) -> Any:
    return _safe(client.get_body_battery, day.isoformat())


def fetch_hrv(client: Garmin, day: date) -> dict[str, Any] | None:
    return _safe(client.get_hrv_data, day.isoformat())


def fetch_training_status(client: Garmin, day: date) -> dict[str, Any] | None:
    return _safe(client.get_training_status, day.isoformat())


def fetch_training_readiness(client: Garmin, day: date) -> Any:
    return _safe(client.get_training_readiness, day.isoformat())


def fetch_max_metrics(client: Garmin, day: date) -> Any:
    return _safe(client.get_max_metrics, day.isoformat())


def fetch_activities(client: Garmin, days: int = 14) -> list[dict[str, Any]]:
    activities = _safe(client.get_activities, 0, 30) or []
    cutoff = datetime.now() - timedelta(days=days)
    out = []
    for a in activities:
        start = a.get("startTimeLocal")
        if not start:
            continue
        try:
            ts = datetime.fromisoformat(start.replace(" ", "T"))
        except ValueError:
            continue
        if ts >= cutoff:
            out.append(a)
    return out


def fetch_steps(client: Garmin, day: date) -> Any:
    return _safe(client.get_steps_data, day.isoformat())


def fetch_floors(client: Garmin, day: date) -> Any:
    return _safe(client.get_floors, day.isoformat())


def fetch_weight(client: Garmin, day: date) -> Any:
    return _safe(
        client.get_body_composition,
        (day - timedelta(days=14)).isoformat(),
        day.isoformat(),
    )


def collect_full_snapshot(client: Garmin, day: date | None = None) -> dict[str, Any]:
    """Descarga todo el bloque de metricas para un dia concreto + actividades."""
    day = day or date.today()
    return {
        "date": day.isoformat(),
        "profile": fetch_user_profile(client),
        "summary": fetch_daily_summary(client, day),
        "sleep": fetch_sleep(client, day),
        "heart_rate": fetch_heart_rate(client, day),
        "stress": fetch_stress(client, day),
        "body_battery": fetch_body_battery(client, day),
        "hrv": fetch_hrv(client, day),
        "training_status": fetch_training_status(client, day),
        "training_readiness": fetch_training_readiness(client, day),
        "max_metrics": fetch_max_metrics(client, day),
        "steps": fetch_steps(client, day),
        "floors": fetch_floors(client, day),
        "weight": fetch_weight(client, day),
        "activities_14d": fetch_activities(client, days=14),
    }
