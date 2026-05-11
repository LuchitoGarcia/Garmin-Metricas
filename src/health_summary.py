"""Generador de resumen de salud a partir del snapshot de Garmin."""
from __future__ import annotations

from datetime import date
from typing import Any

from .formatting import (
    fmt_duration_min,
    fmt_int,
    fmt_pct,
    section,
    bullet,
)


def _get(d: Any, *keys, default=None):
    """Acceso seguro a claves anidadas en dicts/listas."""
    cur = d
    for k in keys:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(k, default if k == keys[-1] else None)
        else:
            return default
    return cur if cur is not None else default


def build_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Convierte el snapshot crudo de Garmin en un dict estructurado."""
    summary = snapshot.get("summary") or {}
    sleep = snapshot.get("sleep") or {}
    sleep_dto = sleep.get("dailySleepDTO") or {}
    hr = snapshot.get("heart_rate") or {}
    stress = snapshot.get("stress") or {}
    bb = snapshot.get("body_battery")
    hrv = snapshot.get("hrv") or {}
    hrv_summary = hrv.get("hrvSummary") or {}
    train_status = snapshot.get("training_status") or {}
    readiness = snapshot.get("training_readiness")
    max_metrics = snapshot.get("max_metrics")
    activities = snapshot.get("activities_14d") or []

    bb_max = bb_min = None
    if isinstance(bb, list) and bb:
        first = bb[0] if isinstance(bb[0], dict) else None
        if first:
            bb_max = first.get("charged") or first.get("bodyBatteryHigh")
            bb_min = first.get("drained") or first.get("bodyBatteryLow")

    readiness_score = None
    readiness_level = None
    if isinstance(readiness, list) and readiness:
        readiness_score = readiness[0].get("score")
        readiness_level = readiness[0].get("level")

    vo2max = None
    if isinstance(max_metrics, list) and max_metrics:
        generic = max_metrics[0].get("generic") or {}
        vo2max = generic.get("vo2MaxValue")

    activities_summary = []
    total_distance_m = 0.0
    total_duration_s = 0.0
    for a in activities:
        activities_summary.append({
            "name": a.get("activityName"),
            "type": _get(a, "activityType", "typeKey"),
            "start": a.get("startTimeLocal"),
            "duration_s": a.get("duration"),
            "distance_m": a.get("distance"),
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
            "calories": a.get("calories"),
            "training_effect": a.get("aerobicTrainingEffect"),
            "anaerobic_te": a.get("anaerobicTrainingEffect"),
            "training_load": a.get("activityTrainingLoad"),
        })
        if a.get("distance"):
            total_distance_m += a["distance"]
        if a.get("duration"):
            total_duration_s += a["duration"]

    return {
        "date": snapshot.get("date"),
        "user": {
            "name": _get(snapshot, "profile", "full_name"),
            "unit_system": _get(snapshot, "profile", "unit_system"),
        },
        "daily": {
            "steps": summary.get("totalSteps"),
            "steps_goal": summary.get("dailyStepGoal"),
            "calories_total": summary.get("totalKilocalories"),
            "calories_active": summary.get("activeKilocalories"),
            "calories_bmr": summary.get("bmrKilocalories"),
            "floors_up": summary.get("floorsAscended"),
            "intensity_min_moderate": summary.get("moderateIntensityMinutes"),
            "intensity_min_vigorous": summary.get("vigorousIntensityMinutes"),
            "resting_hr": summary.get("restingHeartRate") or hr.get("restingHeartRate"),
        },
        "sleep": {
            "score": _get(sleep_dto, "sleepScores", "overall", "value"),
            "qualifier": _get(sleep_dto, "sleepScores", "overall", "qualifierKey"),
            "total_min": (sleep_dto.get("sleepTimeSeconds") or 0) // 60 or None,
            "deep_min": (sleep_dto.get("deepSleepSeconds") or 0) // 60 or None,
            "light_min": (sleep_dto.get("lightSleepSeconds") or 0) // 60 or None,
            "rem_min": (sleep_dto.get("remSleepSeconds") or 0) // 60 or None,
            "awake_min": (sleep_dto.get("awakeSleepSeconds") or 0) // 60 or None,
            "avg_resp": _get(sleep, "avgRespirationValue"),
            "avg_spo2": _get(sleep, "avgSleepStress"),
        },
        "heart_rate": {
            "resting": hr.get("restingHeartRate"),
            "max_today": hr.get("maxHeartRate"),
            "min_today": hr.get("minHeartRate"),
        },
        "stress": {
            "avg": stress.get("avgStressLevel"),
            "max": stress.get("maxStressLevel"),
            "rest_pct": stress.get("restStressPercentage"),
            "low_pct": stress.get("lowStressPercentage"),
            "medium_pct": stress.get("mediumStressPercentage"),
            "high_pct": stress.get("highStressPercentage"),
        },
        "body_battery": {
            "high": bb_max,
            "low": bb_min,
        },
        "hrv": {
            "last_night_avg": hrv_summary.get("lastNightAvg"),
            "last_night_5min_high": hrv_summary.get("lastNight5MinHigh"),
            "weekly_avg": hrv_summary.get("weeklyAvg"),
            "status": hrv_summary.get("status"),
            "baseline_low": _get(hrv_summary, "baseline", "lowUpper"),
            "baseline_balanced_low": _get(hrv_summary, "baseline", "balancedLow"),
            "baseline_balanced_high": _get(hrv_summary, "baseline", "balancedUpper"),
        },
        "training": {
            "status": _get(train_status, "mostRecentTrainingStatus",
                           "latestTrainingStatusData") or train_status.get("trainingStatus"),
            "load_focus": _get(train_status, "mostRecentTrainingLoadBalance",
                               "metricsTrainingLoadBalanceDTOMap"),
            "readiness_score": readiness_score,
            "readiness_level": readiness_level,
            "vo2max": vo2max,
        },
        "last_14_days": {
            "n_activities": len(activities_summary),
            "total_distance_km": round(total_distance_m / 1000, 2) if total_distance_m else 0,
            "total_duration_h": round(total_duration_s / 3600, 2) if total_duration_s else 0,
            "activities": activities_summary,
        },
    }


def render_markdown(s: dict[str, Any]) -> str:
    """Convierte el dict de resumen a un markdown legible."""
    lines: list[str] = []
    lines.append(f"# Resumen de salud — {s.get('date', date.today().isoformat())}")
    name = s["user"].get("name")
    if name:
        lines.append(f"_Usuario: {name}_\n")

    lines.append(section("Actividad del dia"))
    d = s["daily"]
    lines.append(bullet("Pasos", f"{fmt_int(d['steps'])} / objetivo {fmt_int(d['steps_goal'])}"))
    lines.append(bullet("Calorias totales", fmt_int(d["calories_total"])))
    lines.append(bullet("Calorias activas", fmt_int(d["calories_active"])))
    lines.append(bullet("Min. intensidad moderada", fmt_int(d["intensity_min_moderate"])))
    lines.append(bullet("Min. intensidad vigorosa", fmt_int(d["intensity_min_vigorous"])))
    lines.append(bullet("FC en reposo", f"{fmt_int(d['resting_hr'])} ppm"))

    lines.append(section("Sueno"))
    sl = s["sleep"]
    lines.append(bullet("Puntuacion", f"{fmt_int(sl['score'])} ({sl.get('qualifier') or '-'})"))
    lines.append(bullet("Total", fmt_duration_min(sl["total_min"])))
    lines.append(bullet("Profundo", fmt_duration_min(sl["deep_min"])))
    lines.append(bullet("Ligero", fmt_duration_min(sl["light_min"])))
    lines.append(bullet("REM", fmt_duration_min(sl["rem_min"])))
    lines.append(bullet("Despierto", fmt_duration_min(sl["awake_min"])))

    lines.append(section("Estres"))
    st = s["stress"]
    lines.append(bullet("Nivel medio", fmt_int(st["avg"])))
    lines.append(bullet("Maximo", fmt_int(st["max"])))
    lines.append(bullet("Tiempo en reposo", fmt_pct(st["rest_pct"])))
    lines.append(bullet("Tiempo bajo", fmt_pct(st["low_pct"])))
    lines.append(bullet("Tiempo medio", fmt_pct(st["medium_pct"])))
    lines.append(bullet("Tiempo alto", fmt_pct(st["high_pct"])))

    lines.append(section("Body Battery"))
    bb = s["body_battery"]
    lines.append(bullet("Maximo", fmt_int(bb["high"])))
    lines.append(bullet("Minimo", fmt_int(bb["low"])))

    lines.append(section("HRV"))
    hv = s["hrv"]
    lines.append(bullet("Media ultima noche", f"{fmt_int(hv['last_night_avg'])} ms"))
    lines.append(bullet("Pico 5 min", f"{fmt_int(hv['last_night_5min_high'])} ms"))
    lines.append(bullet("Media semanal", f"{fmt_int(hv['weekly_avg'])} ms"))
    lines.append(bullet("Estado", hv.get("status") or "-"))

    lines.append(section("Entrenamiento"))
    tr = s["training"]
    lines.append(bullet("Estado", tr.get("status") or "-"))
    lines.append(bullet("Training Readiness", f"{fmt_int(tr['readiness_score'])} ({tr.get('readiness_level') or '-'})"))
    lines.append(bullet("VO2max", fmt_int(tr["vo2max"])))

    lines.append(section("Ultimos 14 dias"))
    l = s["last_14_days"]
    lines.append(bullet("Actividades", str(l["n_activities"])))
    lines.append(bullet("Distancia total", f"{l['total_distance_km']} km"))
    lines.append(bullet("Tiempo total", f"{l['total_duration_h']} h"))
    if l["activities"]:
        lines.append("\n| Fecha | Tipo | Duracion | Distancia | FC media | TE aerobico |")
        lines.append("|---|---|---|---|---|---|")
        for a in l["activities"][:15]:
            dur = fmt_duration_min((a["duration_s"] or 0) // 60)
            dist = f"{(a['distance_m'] or 0) / 1000:.2f} km" if a["distance_m"] else "-"
            te = f"{a['training_effect']:.1f}" if a["training_effect"] else "-"
            lines.append(
                f"| {a['start'] or '-'} | {a['type'] or '-'} | {dur} | {dist} | "
                f"{fmt_int(a['avg_hr'])} | {te} |"
            )

    return "\n".join(lines) + "\n"
