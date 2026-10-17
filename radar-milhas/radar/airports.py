"""Aeroportos e atalhos de grupos (PT, ES) usados no cadastro dos radares."""

from __future__ import annotations

import re

AIRPORTS = {
    # Portugal
    "LIS": "Lisboa",
    "OPO": "Porto",
    "FAO": "Faro",
    "FNC": "Funchal (Madeira)",
    "PDL": "Ponta Delgada (Açores)",
    # Espanha
    "MAD": "Madri",
    "BCN": "Barcelona",
    "AGP": "Málaga",
    "VLC": "Valência",
    "SVQ": "Sevilha",
    "BIO": "Bilbao",
    "PMI": "Palma de Maiorca",
    "ALC": "Alicante",
    "SCQ": "Santiago de Compostela",
    # Brasil
    "GRU": "São Paulo (Guarulhos)",
    "VCP": "Campinas (Viracopos)",
    "GIG": "Rio de Janeiro (Galeão)",
    "BSB": "Brasília",
    "CNF": "Belo Horizonte (Confins)",
    "REC": "Recife",
    "FOR": "Fortaleza",
    "SSA": "Salvador",
    "NAT": "Natal",
    "POA": "Porto Alegre",
    "CWB": "Curitiba",
    "FLN": "Florianópolis",
    "BEL": "Belém",
    "MAO": "Manaus",
}

GROUPS = {
    # Principais portas de entrada com voo direto/1 conexão a partir do Brasil
    "PT": ["LIS", "OPO", "FAO"],
    "PT+": ["LIS", "OPO", "FAO", "FNC", "PDL"],
    "ES": ["MAD", "BCN", "AGP", "VLC", "SVQ"],
    "ES+": ["MAD", "BCN", "AGP", "VLC", "SVQ", "BIO", "PMI", "ALC", "SCQ"],
}
GROUPS["PTES"] = GROUPS["PT"] + GROUPS["ES"]

PORTUGAL = set(GROUPS["PT+"])
SPAIN = set(GROUPS["ES+"])

_IATA = re.compile(r"^[A-Z]{3}$")


def expand_airports(raw: str | list[str]) -> list[str]:
    """'GRU, PT' -> ['GRU', 'LIS', 'OPO', 'FAO'] (sem duplicatas, ordem preservada)."""
    tokens = raw if isinstance(raw, list) else re.split(r"[,\s;/]+", raw)
    out: list[str] = []
    for token in tokens:
        code = token.strip().upper().replace("-", "").replace("_", "")
        if not code:
            continue
        codes = GROUPS.get(code)
        if codes is None:
            if not _IATA.match(code):
                raise ValueError(f"Aeroporto inválido: {token!r} (use código IATA ou PT, PT+, ES, ES+, PTES)")
            codes = [code]
        for c in codes:
            if c not in out:
                out.append(c)
    return out


def airport_name(code: str) -> str:
    return AIRPORTS.get(code, code)


def country_flag(code: str) -> str:
    if code in PORTUGAL:
        return "🇵🇹"
    if code in SPAIN:
        return "🇪🇸"
    return "🇧🇷" if code in AIRPORTS else ""
