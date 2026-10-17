"""Converte milhas em reais para comparar emissões em milhas com tarifas em dinheiro."""

from __future__ import annotations

from .config import Settings
from .models import FareKind, FareQuote

FALLBACK_MILHEIRO = 20.0


def milheiro(settings: Settings, program: str) -> float:
    return settings.milheiro.get(program, FALLBACK_MILHEIRO)


def effective_cost_brl(quote: FareQuote, settings: Settings) -> float:
    """Custo efetivo por passageiro: dinheiro = tarifa; milhas = milhas x milheiro + taxas."""
    if quote.kind == FareKind.CASH:
        return float(quote.price_brl or 0.0)
    return (quote.miles or 0) / 1000.0 * milheiro(settings, quote.program) + quote.taxes_brl


def value_per_thousand(miles: int, taxes_brl: float, cash_price_brl: float) -> float | None:
    """Quanto cada milheiro "rende" ao trocar a tarifa em dinheiro pela emissão em milhas."""
    if miles <= 0:
        return None
    return (cash_price_brl - taxes_brl) / (miles / 1000.0)
