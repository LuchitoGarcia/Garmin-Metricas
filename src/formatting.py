"""Helpers de formato para los informes en markdown / consola."""
from __future__ import annotations

from typing import Any


def fmt_int(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def fmt_pct(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return str(value)


def fmt_duration_min(minutes: Any) -> str:
    if minutes is None or minutes == 0:
        return "-"
    try:
        m = int(minutes)
    except (TypeError, ValueError):
        return str(minutes)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}min"
    return f"{m}min"


def section(title: str) -> str:
    return f"\n## {title}\n"


def bullet(label: str, value: Any) -> str:
    return f"- **{label}:** {value}"
