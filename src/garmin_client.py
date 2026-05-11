"""Cliente de Garmin Connect con cache de tokens.

Reutiliza la sesion guardada en cache/garth/ para no tener que reautenticar
en cada llamada (Garmin bloquea logins repetidos).
"""
from __future__ import annotations

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

import config


def get_client() -> Garmin:
    """Devuelve un cliente de Garmin autenticado, reutilizando tokens si existen."""
    config.require_garmin_credentials()
    tokens_dir = str(config.GARTH_TOKENS_DIR)

    client = Garmin(config.GARMIN_EMAIL, config.GARMIN_PASSWORD)

    try:
        client.login(tokens_dir)
        return client
    except (FileNotFoundError, GarminConnectAuthenticationError):
        pass

    try:
        client.login()
        client.garth.dump(tokens_dir)
        return client
    except GarminConnectAuthenticationError as exc:
        raise SystemExit(
            f"Error de autenticacion con Garmin: {exc}. "
            "Revisa email/password en .env."
        ) from exc
    except GarminConnectTooManyRequestsError as exc:
        raise SystemExit(
            "Garmin ha bloqueado por demasiadas peticiones. "
            "Espera unos minutos y vuelve a intentarlo."
        ) from exc
    except GarminConnectConnectionError as exc:
        raise SystemExit(f"No hay conexion con Garmin Connect: {exc}") from exc
