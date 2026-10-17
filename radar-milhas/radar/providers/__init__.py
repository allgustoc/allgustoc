from __future__ import annotations

import logging

from ..config import Settings
from .base import Provider, ProviderBlocked, ProviderError

log = logging.getLogger(__name__)

AVAILABLE = {
    "demo": "Dados sintéticos para testar o bot",
    "serpapi": "Dinheiro: Google Flights via SerpApi (SERPAPI_KEY)",
    "seats_aero": "Milhas: Smiles/Azul e outros via seats.aero (SEATS_AERO_KEY)",
    "smiles": "Milhas: site da Smiles (navegador automatizado)",
    "latam": "Dinheiro + LATAM Pass: site da LATAM (navegador automatizado)",
    "azul": "Dinheiro + Azul Fidelidade: site da Azul (navegador automatizado, experimental)",
}


def create_provider(name: str, settings: Settings) -> Provider:
    if name == "demo":
        from .demo import DemoProvider

        return DemoProvider(settings)
    if name == "serpapi":
        from .serpapi import SerpApiGoogleFlights

        return SerpApiGoogleFlights(settings)
    if name == "seats_aero":
        from .seats_aero import SeatsAeroProvider

        return SeatsAeroProvider(settings)
    if name == "smiles":
        from .smiles import SmilesProvider

        return SmilesProvider(settings)
    if name == "latam":
        from .latam import LatamProvider

        return LatamProvider(settings)
    if name == "azul":
        from .azul import AzulProvider

        return AzulProvider(settings)
    raise ProviderError(f"Fonte desconhecida: {name}. Opções: {', '.join(AVAILABLE)}", transient=False)


def create_providers(settings: Settings) -> list[Provider]:
    providers = []
    for name in settings.providers:
        try:
            providers.append(create_provider(name, settings))
        except ProviderError as exc:
            log.error("Fonte '%s' desativada: %s", name, exc)
    return providers


__all__ = ["AVAILABLE", "Provider", "ProviderBlocked", "ProviderError", "create_provider", "create_providers"]
