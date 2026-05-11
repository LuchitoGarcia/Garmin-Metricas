# Metricas Garmin

Pipeline en Python para conectarte a Garmin Connect, descargar tus metricas
de salud y generar:

- **Resumen de salud** del dia (sueno, FC, estres, HRV, body battery, VO2max, actividades de los ultimos 14 dias).
- **Plan de entrenamiento** personalizado (modo offline por reglas o modo `--ai` con Claude).
- **Consejos accionables** basados en tus metricas (offline o `--ai`).

## Estructura

```
Metricas Garmin/
├── garmin_health.py        # CLI principal
├── config.py               # Carga de .env, paths de cache/reports
├── requirements.txt
├── .env.example            # Plantilla de credenciales (copiar a .env)
├── .gitignore
├── src/
│   ├── garmin_client.py    # Login + reuso de tokens (garth)
│   ├── metrics.py          # Descarga de metricas crudas
│   ├── formatting.py       # Helpers de formato
│   ├── health_summary.py   # Construye resumen estructurado + markdown
│   ├── training_plan.py    # Plan de entrenamiento (offline + IA)
│   └── advisor.py          # Consejos personalizados (offline + IA)
├── cache/                  # Tokens de sesion + snapshots cacheados
└── reports/                # Salidas .md y .json
```

## Instalacion

```bash
cd "/Users/luisgarciaalvarez/Documents/Metricas Garmin"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# editar .env con tu email/password de Garmin Connect
```

> **Nota de seguridad**: rellena `.env` tu mismo. Las credenciales no salen de tu maquina; los tokens se guardan en `cache/garth/` y se reutilizan entre ejecuciones.

## Uso

```bash
# Resumen de salud de hoy (imprime + guarda en reports/)
python garmin_health.py resumen

# Resumen de un dia concreto
python garmin_health.py resumen --date 2026-05-06

# Plan de entrenamiento (modo offline, basado en reglas)
python garmin_health.py plan --goal 10k --weeks 4 --days 4 --long-day domingo

# Plan generado por Claude (necesita ANTHROPIC_API_KEY en .env)
python garmin_health.py plan --goal media --weeks 6 --ai

# Consejos personalizados
python garmin_health.py consejos
python garmin_health.py consejos --ai

# Volcar el JSON crudo del dia (debug / inspeccion)
python garmin_health.py snapshot

# Forzar descarga ignorando cache
python garmin_health.py resumen --no-cache
```

## Como pedirmelo a Claude

Cuando quieras que **yo** te haga el resumen o el plan, hay dos opciones:

1. **Modo offline** (recomendado para empezar): ejecuta `python garmin_health.py resumen`,
   luego pegame el contenido del archivo `reports/resumen_<fecha>.md` o `.json`
   y te interpreto las metricas, te doy el plan y los consejos en la propia conversacion.

2. **Modo `--ai`**: si pones tu `ANTHROPIC_API_KEY` en `.env`, los comandos
   `plan --ai` y `consejos --ai` llaman directamente a Claude y guardan el
   resultado en `reports/`. No necesitas pegarmelo despues.

## Metricas descargadas

`src/metrics.py::collect_full_snapshot` baja, para una fecha:

- Perfil de usuario y sistema de unidades.
- Resumen diario: pasos, calorias, FC reposo, minutos de intensidad, pisos.
- Sueno detallado: fases (profundo/ligero/REM/despierto), respiracion, SpO2.
- FC: reposo, max, min del dia.
- Estres: medio, max, % en cada banda.
- Body Battery: max y min.
- HRV: media nocturna, pico 5min, media semanal, baseline, status.
- Training Status, Training Readiness y VO2max.
- Pasos por intervalo, pisos subidos, peso (ultimos 14 dias).
- Actividades de los ultimos 14 dias con FC media/max, training effect, carga.

## Solucion de problemas

- **`GarminConnectAuthenticationError`** → revisa email/password en `.env`. Si tienes
  2FA en Garmin, deberas desactivarlo o usar un App-Specific Password (Garmin no
  ofrece 2FA app-passwords; mejor desactivar 2FA temporalmente).
- **`GarminConnectTooManyRequestsError`** → espera 15-30 minutos. Garmin bloquea
  por logins repetidos. La cache de tokens en `cache/garth/` evita relogins
  innecesarios.
- **Metricas vacias o nulas** → tu dispositivo Garmin puede no soportar esa
  metrica (p.ej. Body Battery / HRV solo en modelos recientes). El codigo es
  tolerante: imprime `-` y sigue.

## Reajuste manual

Si cambias de objetivo, edita el `--goal` y vuelve a ejecutar `plan`. Para
incorporar nuevas reglas heuristicas, anade tu logica en
`src/advisor.py::rule_based_advice` o `src/training_plan.py::_running_template`.
