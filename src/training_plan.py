"""Generador de plan de entrenamiento.

Dos modos:
  - offline (por defecto): construye un plan basado en reglas a partir de
    las metricas (VO2max, FC reposo, training status, readiness, carga
    semanal). Funciona sin conexion ni API key.
  - ai: si tienes ANTHROPIC_API_KEY en .env, llama a Claude con el
    snapshot completo y los objetivos para generar un plan personalizado
    en markdown.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import config


@dataclass
class PlanRequest:
    goal: str = "mantenimiento"
    sport: str = "running"
    days_per_week: int = 4
    weeks: int = 4
    long_run_day: str = "domingo"
    notes: str = ""


def _phase_for_week(week_idx: int, total_weeks: int) -> str:
    """4 semanas: base, build, peak, deload (recuperacion)."""
    pct = (week_idx + 1) / total_weeks
    if total_weeks >= 4 and week_idx == total_weeks - 1:
        return "descarga"
    if pct <= 0.34:
        return "base"
    if pct <= 0.75:
        return "construccion"
    return "pico"


def _zones_from_resting_hr(resting_hr: int | None, max_hr: int | None) -> dict[str, str]:
    """Zonas Karvonen aproximadas. Si no hay datos devuelve placeholders."""
    if not resting_hr or not max_hr:
        return {
            "Z2": "FC suave / hablar comodo",
            "Z3": "FC moderada / hablar entrecortado",
            "Z4": "FC fuerte / frases cortas",
            "Z5": "FC maxima / inviable hablar",
        }
    reserve = max_hr - resting_hr

    def z(low_pct: float, high_pct: float) -> str:
        return f"{int(resting_hr + reserve * low_pct)}-{int(resting_hr + reserve * high_pct)} ppm"

    return {
        "Z2": z(0.60, 0.70),
        "Z3": z(0.70, 0.80),
        "Z4": z(0.80, 0.90),
        "Z5": z(0.90, 1.00),
    }


def _adjust_for_readiness(session: str, readiness_level: str | None) -> str:
    """Si la readiness es baja, reduce intensidad."""
    if not readiness_level:
        return session
    low = readiness_level.upper()
    if low in {"LOW", "POOR"}:
        return session + " — _readiness baja: reducir intensidad o sustituir por rodaje Z2 30-40min_"
    return session


def _running_template(req: PlanRequest, phase: str) -> list[str]:
    """Plantilla semanal de carrera segun fase. 4-6 dias."""
    long_day = req.long_run_day.lower()

    if phase == "base":
        sessions = [
            "Rodaje suave Z2 — 40-50min",
            "Series cortas: 10min cal + 6x(2min Z4 / 2min Z2) + 10min vuelta",
            "Rodaje suave Z2 — 35-45min",
            "Tirada larga Z2 — 60-75min",
            "Movilidad / fuerza tren inferior — 40min",
            "Cross-training opcional (bici/eliptica) — 30min Z2",
        ]
    elif phase == "construccion":
        sessions = [
            "Rodaje Z2 + 6x100m progresivos al final — 45-55min",
            "Series umbral: 15min cal + 4x6min Z4 (rec 2min Z1) + 10min vuelta",
            "Rodaje Z2 — 40-50min",
            "Tirada larga progresiva: 70min Z2 + 15min Z3 final",
            "Fuerza pesada tren inferior — 40min",
            "Trote tecnica + ejercicios — 30min",
        ]
    elif phase == "pico":
        sessions = [
            "Rodaje Z2 — 40min",
            "VO2max: 15min cal + 5x3min Z5 (rec 3min trote) + 10min vuelta",
            "Rodaje Z2 — 35-40min",
            "Tirada larga con bloques: 30min Z2 + 30min ritmo objetivo + 15min Z2",
            "Fuerza explosiva ligera + movilidad — 35min",
            "Trote regenerativo Z1-Z2 — 25min",
        ]
    else:  # descarga
        sessions = [
            "Rodaje muy suave Z2 — 30min",
            "10min cal + 4x90s Z4 (rec 2min) + 10min vuelta",
            "Descanso o caminata 30min",
            "Rodaje Z2 — 45min",
            "Movilidad y core — 25min",
            "Descanso completo",
        ]

    # Ajustar al numero de dias deseados manteniendo la sesion larga al final.
    if req.days_per_week >= 6:
        return sessions[:6]
    selected = sessions[: max(req.days_per_week - 1, 2)]
    selected.append(f"Tirada larga ({long_day})")
    if "Tirada larga" in sessions[3]:
        selected[-1] = sessions[3]
    return selected[: req.days_per_week]


def build_offline_plan(snapshot: dict[str, Any], summary: dict[str, Any], req: PlanRequest) -> str:
    """Construye un plan de entrenamiento basado en reglas en markdown."""
    lines: list[str] = []
    today = date.today()
    user = (summary.get("user") or {}).get("name") or "atleta"
    rest_hr = (summary.get("heart_rate") or {}).get("resting")
    vo2max = (summary.get("training") or {}).get("vo2max")
    readiness = (summary.get("training") or {}).get("readiness_level")
    train_status = (summary.get("training") or {}).get("status")
    n_acts = (summary.get("last_14_days") or {}).get("n_activities", 0)
    km_14d = (summary.get("last_14_days") or {}).get("total_distance_km", 0)

    max_hr = 220 - 30  # placeholder si no sabemos la edad
    activities = (summary.get("last_14_days") or {}).get("activities") or []
    for a in activities:
        if a.get("max_hr") and a["max_hr"] > max_hr:
            max_hr = a["max_hr"]

    zones = _zones_from_resting_hr(rest_hr, max_hr)
    weekly_km = round((km_14d / 2) if km_14d else 0, 1)

    lines.append(f"# Plan de entrenamiento — {user}")
    lines.append(f"_Generado: {today.isoformat()} · Objetivo: {req.goal} · Deporte: {req.sport}_\n")

    lines.append("## Punto de partida")
    lines.append(f"- VO2max actual: **{vo2max or '-'}**")
    lines.append(f"- FC reposo: **{rest_hr or '-'} ppm**, FC max estimada: **{max_hr} ppm**")
    lines.append(f"- Estado de entrenamiento: **{train_status or '-'}**")
    lines.append(f"- Training Readiness: **{readiness or '-'}**")
    lines.append(f"- Carga reciente: {n_acts} actividades en 14 dias, ~{weekly_km} km/sem")
    if req.notes:
        lines.append(f"- Notas: {req.notes}")

    lines.append("\n## Zonas de FC (Karvonen)")
    for k, v in zones.items():
        lines.append(f"- **{k}:** {v}")

    lines.append("\n## Estructura de bloque")
    lines.append(
        f"- Bloque de **{req.weeks} semanas**, **{req.days_per_week} sesiones/sem**"
    )
    lines.append("- Progresion: base → construccion → pico → descarga")
    lines.append(
        "- Regla del 10%: la primera semana suma ~10% al volumen de las dos previas"
    )

    for w in range(req.weeks):
        phase = _phase_for_week(w, req.weeks)
        start = today + timedelta(days=w * 7 - today.weekday())
        lines.append(f"\n### Semana {w + 1} · {phase.title()} — desde {start.isoformat()}")
        sessions = _running_template(req, phase)
        days = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
        for i, s in enumerate(sessions):
            adjusted = _adjust_for_readiness(s, readiness if w == 0 else None)
            lines.append(f"- **{days[i % 7]}:** {adjusted}")

    lines.append("\n## Reajustes automaticos")
    lines.append("- Si la readiness baja por debajo de 25 dos dias seguidos, sustituye la siguiente sesion intensa por rodaje Z2 30-40min.")
    lines.append("- Si el HRV cae por debajo del rango balanceado durante 3 dias, mete un dia extra de descanso.")
    lines.append("- Si el sueno medio de la semana es <6h, reduce la tirada larga un 20%.")
    return "\n".join(lines) + "\n"


def build_ai_plan(snapshot: dict[str, Any], summary: dict[str, Any], req: PlanRequest) -> str:
    """Llama a Claude para generar un plan personalizado. Requiere API key."""
    if not config.ANTHROPIC_API_KEY:
        raise SystemExit(
            "Para --ai necesitas ANTHROPIC_API_KEY en .env. "
            "Sin ella, usa el modo offline (sin --ai)."
        )
    try:
        import anthropic
    except ImportError as exc:
        raise SystemExit("Falta la dependencia 'anthropic'. Ejecuta: pip install -r requirements.txt") from exc

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    payload = {
        "summary": summary,
        "request": {
            "goal": req.goal,
            "sport": req.sport,
            "days_per_week": req.days_per_week,
            "weeks": req.weeks,
            "long_run_day": req.long_run_day,
            "notes": req.notes,
        },
    }

    system = (
        "Eres un entrenador deportivo experto. Generas planes de entrenamiento "
        "individualizados en MARKDOWN, basandote en metricas reales de Garmin. "
        "Estructura: punto de partida, zonas de FC, plan semana a semana, "
        "criterios de reajuste segun HRV/sueno/readiness. Se concreto: cada "
        "sesion debe tener tipo, duracion/distancia, intensidad por zona y "
        "estructura de series si aplica. Usa el sistema metrico. Espanol."
    )

    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=4000,
        system=system,
        messages=[
            {
                "role": "user",
                "content": (
                    "Genera el plan de entrenamiento usando estas metricas y "
                    "preferencias:\n\n```json\n"
                    + json.dumps(payload, indent=2, ensure_ascii=False, default=str)
                    + "\n```"
                ),
            }
        ],
    )

    return "".join(block.text for block in msg.content if hasattr(block, "text"))
