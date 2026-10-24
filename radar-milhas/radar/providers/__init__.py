from __future__ import annotations

import importlib.util
import logging

from ..config import Settings
from .base import Provider, ProviderBlocked, ProviderError

log = logging.getLogger(__name__)

AVAILABLE = {
    "serpapi": "Dinheiro: Google Flights via SerpApi (SERPAPI_KEY)",
    "seats_aero": "Milhas: Smiles/Azul e outros via seats.aero (SEATS_AERO_KEY)",
    "smiles": "Milhas: site da Smiles (navegador automatizado)",
    "latam": "Dinheiro + LATAM Pass: site da LATAM (navegador automatizado)",
    "azul": "Dinheiro + Azul Fidelidade: site da Azul (navegador automatizado, experimental)",
}

PROVIDER_LABELS = {
    "serpapi": "Google Flights",
    "seats_aero": "seats.aero",
    "smiles": "Smiles",
    "latam": "LATAM",
    "azul": "Azul",
    "demo": "Dados de teste",
}

BROWSER_PROVIDERS = {"smiles", "latam", "azul"}


def create_provider(name: str, settings: Settings) -> Provider:
    if name in BROWSER_PROVIDERS and importlib.util.find_spec("playwright") is None:
        raise ProviderError(
            "o navegador automatizado não está instalado. Rode: pip install playwright e "
            "python -m playwright install chromium",
            transient=False,
        )
    if name == "demo":
        # Dados sintéticos: usados só nos testes automatizados.
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


def create_providers(settings: Settings) -> tuple[list[Provider], list[tuple[str, str]]]:
    """Cria as fontes configuradas. Devolve (fontes, [(fonte, motivo da falha)])."""
    providers, failures = [], []
    for name in settings.providers:
        try:
            providers.append(create_provider(name, settings))
        except ProviderError as exc:
            log.error("Fonte '%s' desativada: %s", name, exc)
            failures.append((name, str(exc)))
    if not settings.providers:
        failures.append(("config", "nenhuma fonte configurada em RADAR_PROVIDERS"))
    return providers, failures


__all__ = ["AVAILABLE", "PROVIDER_LABELS", "Provider", "ProviderBlocked", "ProviderError", "create_provider", "create_providers"]
