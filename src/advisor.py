"""Advisor: consejos personalizados a partir del resumen.

Combina reglas heuristicas (siempre disponibles) con un modo --ai que
manda el resumen completo a Claude para una interpretacion mas matizada.
"""
from __future__ import annotations

import json
from typing import Any

import config


def _safe(d: Any, *keys, default=None):
    cur = d
    for k in keys:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return default
    return cur if cur is not None else default


def rule_based_advice(summary: dict[str, Any]) -> list[str]:
    """Devuelve una lista de bullets de consejo, basada en reglas simples."""
    advice: list[str] = []

    sleep_min = _safe(summary, "sleep", "total_min") or 0
    sleep_score = _safe(summary, "sleep", "score")
    deep_min = _safe(summary, "sleep", "deep_min") or 0
    rem_min = _safe(summary, "sleep", "rem_min") or 0
    awake_min = _safe(summary, "sleep", "awake_min") or 0

    if sleep_min:
        if sleep_min < 6 * 60:
            advice.append(
                f"Dormiste solo {sleep_min // 60}h{sleep_min % 60:02d}min. "
                "Hoy prioriza recuperacion y baja intensidad; intenta acostarte 60-90min antes."
            )
        elif sleep_min < 7 * 60:
            advice.append(
                "El sueno esta justo. Cuida la higiene de pantalla en la ultima hora."
            )
        if rem_min and rem_min < 60:
            advice.append("Poco REM. Evita alcohol y comidas tardias para mejorar la fase REM.")
        if deep_min and deep_min < 45:
            advice.append("Sueno profundo bajo. Mantener horario regular y bajar temperatura del cuarto ayuda.")
        if awake_min and awake_min > 45:
            advice.append("Demasiados despertares. Revisa cafeina despues de las 16h e ilumina menos por la noche.")
    if sleep_score is not None and sleep_score < 60:
        advice.append("Puntuacion de sueno baja. Considera siesta corta (20-25min) si tu jornada lo permite.")

    rest_hr = _safe(summary, "heart_rate", "resting") or _safe(summary, "daily", "resting_hr")
    if rest_hr:
        if rest_hr > 70:
            advice.append(f"FC reposo alta ({rest_hr} ppm) — puede indicar fatiga o estres acumulado.")
        elif rest_hr < 45:
            advice.append(f"FC reposo muy baja ({rest_hr} ppm). Si te notas mareado al levantarte, hidratacion y sales.")

    avg_stress = _safe(summary, "stress", "avg")
    high_pct = _safe(summary, "stress", "high_pct")
    if avg_stress is not None and avg_stress > 50:
        advice.append(
            f"Estres medio elevado ({avg_stress}). Inserta 2 bloques de respiracion 4-7-8 (5min) durante el dia."
        )
    if high_pct is not None and high_pct > 25:
        advice.append("Mas del 25% del dia en estres alto. Una caminata de 20min al aire libre baja el cortisol rapido.")

    bb_low = _safe(summary, "body_battery", "low")
    bb_high = _safe(summary, "body_battery", "high")
    if bb_low is not None and bb_low < 15:
        advice.append("Body Battery toco fondo. Hoy entreno suave (Z2) o descanso activo.")
    if bb_high is not None and bb_low is not None and (bb_high - bb_low) < 25:
        advice.append("Recargas de Body Battery cortas — necesitas mas pausas reales (sin pantalla) durante el dia.")

    hrv_avg = _safe(summary, "hrv", "last_night_avg")
    weekly_avg = _safe(summary, "hrv", "weekly_avg")
    hrv_status = _safe(summary, "hrv", "status")
    if hrv_avg and weekly_avg:
        if hrv_avg < weekly_avg * 0.85:
            advice.append(
                f"HRV de anoche ({hrv_avg} ms) muy por debajo de tu media semanal ({weekly_avg} ms). "
                "Hoy: nada de alta intensidad."
            )
    if hrv_status and hrv_status.upper() == "UNBALANCED":
        advice.append("HRV en estado UNBALANCED — semana de descarga recomendable si dura >5 dias.")

    readiness = _safe(summary, "training", "readiness_score")
    readiness_lvl = _safe(summary, "training", "readiness_level")
    if readiness is not None:
        if readiness < 25:
            advice.append(f"Training Readiness muy bajo ({readiness}/100). Hoy descanso o movilidad.")
        elif readiness < 50:
            advice.append(f"Readiness moderado ({readiness}/100): sesion ligera Z2.")
        else:
            advice.append(f"Readiness alto ({readiness}/100, {readiness_lvl}): buen dia para serie de calidad.")

    train_status = _safe(summary, "training", "status")
    if train_status:
        ts = str(train_status).upper()
        if "OVERREACHING" in ts or "UNPRODUCTIVE" in ts:
            advice.append(f"Estado de entrenamiento '{train_status}' — recorta volumen 20-30% una semana.")
        elif "RECOVERY" in ts:
            advice.append("Estado en RECOVERY: mantente en Z1-Z2 hasta que vuelvas a productive.")
        elif "MAINTAINING" in ts or "PRODUCTIVE" in ts:
            advice.append("Estado de entrenamiento solido — buen momento para subir intensidad si tu calendario lo permite.")

    steps = _safe(summary, "daily", "steps") or 0
    goal = _safe(summary, "daily", "steps_goal") or 10000
    if steps and steps < goal * 0.5:
        advice.append(f"Solo {steps} pasos hoy (~{steps * 100 // goal}% del objetivo). Una caminata vespertina te pone en rango.")

    mod = _safe(summary, "daily", "intensity_min_moderate") or 0
    vig = _safe(summary, "daily", "intensity_min_vigorous") or 0
    weekly_min = mod + vig * 2
    if weekly_min < 21:
        advice.append("Vas justo de minutos de intensidad esta semana (OMS recomienda 150min moderada).")

    n_acts = _safe(summary, "last_14_days", "n_activities") or 0
    if n_acts == 0:
        advice.append("Cero actividades registradas en 14 dias. Empieza con 3 sesiones suaves esta semana.")

    if not advice:
        advice.append("Metricas dentro de rango sano. Manten consistencia y descansa entre sesiones intensas.")

    return advice


def build_offline_advice(summary: dict[str, Any]) -> str:
    bullets = rule_based_advice(summary)
    out = ["# Consejos personalizados\n"]
    for b in bullets:
        out.append(f"- {b}")
    return "\n".join(out) + "\n"


def build_ai_advice(snapshot: dict[str, Any], summary: dict[str, Any]) -> str:
    """Pide a Claude consejos en profundidad. Requiere ANTHROPIC_API_KEY."""
    if not config.ANTHROPIC_API_KEY:
        raise SystemExit(
            "Para --ai necesitas ANTHROPIC_API_KEY en .env. "
            "Sin ella, usa el modo offline (sin --ai)."
        )
    try:
        import anthropic
    except ImportError as exc:
        raise SystemExit("Falta 'anthropic'. Ejecuta: pip install -r requirements.txt") from exc

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system = (
        "Eres entrenador y experto en fisiologia del ejercicio. Te paso "
        "metricas de Garmin de un usuario. Devuelve consejos accionables en "
        "markdown, agrupados en: Recuperacion, Carga de entrenamiento, "
        "Sueno, Estres, Nutricion (si hay datos relacionados), Habitos. "
        "Para cada consejo da el dato concreto que lo justifica. Espanol, "
        "tono directo, sin disclaimers."
    )
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=2500,
        system=system,
        messages=[
            {
                "role": "user",
                "content": "Resumen estructurado:\n```json\n"
                + json.dumps(summary, indent=2, ensure_ascii=False, default=str)
                + "\n```",
            }
        ],
    )
    return "".join(b.text for b in msg.content if hasattr(b, "text"))
