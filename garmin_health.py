#!/usr/bin/env python3
"""CLI principal de Metricas Garmin.

Uso:
  python garmin_health.py resumen              # resumen de hoy
  python garmin_health.py resumen --date 2026-05-06
  python garmin_health.py plan --goal 10k --weeks 4 --days 4
  python garmin_health.py plan --ai            # plan via Claude
  python garmin_health.py consejos
  python garmin_health.py consejos --ai
  python garmin_health.py snapshot             # vuelca el JSON crudo
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

import config
from src import health_summary, training_plan, advisor
from src.garmin_client import get_client
from src.metrics import collect_full_snapshot

console = Console()


def _parse_date(s: str | None) -> date:
    if not s:
        return date.today()
    return datetime.strptime(s, "%Y-%m-%d").date()


def _save(filename: str, content: str) -> Path:
    path = config.REPORTS_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


def _get_snapshot(day: date, use_cache: bool) -> dict:
    cache_file = config.CACHE_DIR / f"snapshot_{day.isoformat()}.json"
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    console.print(f"[dim]Conectando a Garmin Connect…[/dim]")
    client = get_client()
    console.print(f"[dim]Descargando metricas para {day.isoformat()}…[/dim]")
    snap = collect_full_snapshot(client, day)
    cache_file.write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
    return snap


def cmd_resumen(args: argparse.Namespace) -> None:
    day = _parse_date(args.date)
    snap = _get_snapshot(day, args.cache)
    summary = health_summary.build_summary(snap)
    md = health_summary.render_markdown(summary)
    console.print(Markdown(md))
    out = _save(f"resumen_{day.isoformat()}.md", md)
    json_path = _save(f"resumen_{day.isoformat()}.json", json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    console.print(f"\n[green]Guardado:[/green] {out}\n[green]JSON:[/green] {json_path}")


def cmd_plan(args: argparse.Namespace) -> None:
    day = _parse_date(args.date)
    snap = _get_snapshot(day, args.cache)
    summary = health_summary.build_summary(snap)

    req = training_plan.PlanRequest(
        goal=args.goal,
        sport=args.sport,
        days_per_week=args.days,
        weeks=args.weeks,
        long_run_day=args.long_day,
        notes=args.notes or "",
    )

    if args.ai:
        console.print("[dim]Generando plan con Claude…[/dim]")
        md = training_plan.build_ai_plan(snap, summary, req)
    else:
        md = training_plan.build_offline_plan(snap, summary, req)

    console.print(Markdown(md))
    suffix = "ai" if args.ai else "offline"
    out = _save(f"plan_{req.goal}_{day.isoformat()}_{suffix}.md", md)
    console.print(f"\n[green]Guardado:[/green] {out}")


def cmd_consejos(args: argparse.Namespace) -> None:
    day = _parse_date(args.date)
    snap = _get_snapshot(day, args.cache)
    summary = health_summary.build_summary(snap)

    if args.ai:
        console.print("[dim]Generando consejos con Claude…[/dim]")
        md = advisor.build_ai_advice(snap, summary)
    else:
        md = advisor.build_offline_advice(summary)

    console.print(Markdown(md))
    suffix = "ai" if args.ai else "offline"
    out = _save(f"consejos_{day.isoformat()}_{suffix}.md", md)
    console.print(f"\n[green]Guardado:[/green] {out}")


def cmd_snapshot(args: argparse.Namespace) -> None:
    day = _parse_date(args.date)
    snap = _get_snapshot(day, args.cache)
    out = _save(f"snapshot_{day.isoformat()}.json", json.dumps(snap, indent=2, ensure_ascii=False, default=str))
    console.print(f"[green]Snapshot guardado:[/green] {out}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Resumen de salud y planes de entrenamiento desde Garmin Connect.")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--date", help="Fecha YYYY-MM-DD (por defecto hoy)")
    common.add_argument("--no-cache", dest="cache", action="store_false",
                        help="Forzar descarga ignorando cache local")
    common.set_defaults(cache=True)

    sub.add_parser("resumen", parents=[common], help="Resumen de salud del dia")

    pp = sub.add_parser("plan", parents=[common], help="Plan de entrenamiento")
    pp.add_argument("--goal", default="mantenimiento",
                    help="Objetivo: 5k, 10k, media, maraton, fuerza, mantenimiento, perder grasa…")
    pp.add_argument("--sport", default="running")
    pp.add_argument("--days", type=int, default=4, help="Dias por semana (default 4)")
    pp.add_argument("--weeks", type=int, default=4, help="Numero de semanas (default 4)")
    pp.add_argument("--long-day", default="domingo", help="Dia de la sesion larga")
    pp.add_argument("--notes", default="", help="Notas extra (lesiones, restricciones)")
    pp.add_argument("--ai", action="store_true", help="Generar via Claude (necesita ANTHROPIC_API_KEY)")

    cp = sub.add_parser("consejos", parents=[common], help="Consejos personalizados")
    cp.add_argument("--ai", action="store_true", help="Generar via Claude (necesita ANTHROPIC_API_KEY)")

    sub.add_parser("snapshot", parents=[common], help="Volcar JSON crudo del dia")

    args = p.parse_args(argv)
    handlers = {
        "resumen": cmd_resumen,
        "plan": cmd_plan,
        "consejos": cmd_consejos,
        "snapshot": cmd_snapshot,
    }
    handlers[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
