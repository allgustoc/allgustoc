"""Configuração lida de variáveis de ambiente (e de um arquivo .env opcional)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Custo de referência do milheiro (R$ por 1.000 milhas/pontos). Usado para comparar
# uma emissão em milhas com a tarifa em dinheiro. Ajuste ao preço que você paga/vende.
DEFAULT_MILHEIRO = {
    "smiles": 16.0,
    "latampass": 25.0,
    "azul": 15.0,
}

DEFAULT_FX = {"BRL": 1.0, "USD": 5.40, "EUR": 6.30}


def load_dotenv(path: str | Path = ".env") -> None:
    """Carrega KEY=VALUE de um arquivo .env sem sobrescrever o ambiente."""
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    return float(value.replace(",", ".")) if value else default


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name).lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "sim", "on"}


def _parse_map(raw: str) -> dict[str, float]:
    """'smiles=16,azul=15' -> {'smiles': 16.0, 'azul': 15.0}"""
    out: dict[str, float] = {}
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[key.strip().lower()] = float(value.strip().replace(",", "."))
    return out


@dataclass
class Settings:
    db_path: str = "data/radar.db"
    providers: list[str] = field(default_factory=lambda: ["demo"])
    run_at: str = "07:00"
    timezone: str = "America/Sao_Paulo"

    # Orçamento e ritmo das buscas
    max_searches_per_provider: int = 120
    request_delay: float = 4.0
    refresh_hours: float = 20.0
    stale_days: int = 4
    explore_step_days: int = 3

    # Análise
    suggestion_min_saving: float = 0.12
    deal_threshold: float = 0.10
    tax_estimate_brl: float = 450.0
    milheiro: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_MILHEIRO))
    fx: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_FX))

    # Fontes por API
    serpapi_key: str = ""
    seats_aero_key: str = ""
    seats_aero_sources: str = ""

    # Navegador (Smiles / LATAM / Azul)
    browser_headless: bool = True
    browser_profile_dir: str = "data/browser"
    browser_executable: str = ""
    browser_timeout: float = 45.0
    smiles_club: bool = False
    debug_dump_dir: str = ""

    # Notificações
    notify_mode: str = "digest"  # digest | deals
    telegram_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""

    @classmethod
    def from_env(cls, dotenv: str | Path | None = ".env") -> "Settings":
        if dotenv:
            load_dotenv(dotenv)
        milheiro = dict(DEFAULT_MILHEIRO)
        milheiro.update(_parse_map(_env("RADAR_MILHEIRO")))
        fx = dict(DEFAULT_FX)
        fx.update({k.upper(): v for k, v in _parse_map(_env("RADAR_FX")).items()})
        providers = [p.strip().lower() for p in _env("RADAR_PROVIDERS", "demo").split(",") if p.strip()]
        return cls(
            db_path=_env("RADAR_DB_PATH", cls.db_path),
            providers=providers,
            run_at=_env("RADAR_RUN_AT", cls.run_at),
            timezone=_env("RADAR_TIMEZONE", cls.timezone),
            max_searches_per_provider=_env_int("RADAR_MAX_SEARCHES_PER_PROVIDER", cls.max_searches_per_provider),
            request_delay=_env_float("RADAR_REQUEST_DELAY", cls.request_delay),
            refresh_hours=_env_float("RADAR_REFRESH_HOURS", cls.refresh_hours),
            stale_days=_env_int("RADAR_STALE_DAYS", cls.stale_days),
            explore_step_days=max(1, _env_int("RADAR_EXPLORE_STEP_DAYS", cls.explore_step_days)),
            suggestion_min_saving=_env_float("RADAR_SUGGESTION_MIN_SAVING", cls.suggestion_min_saving),
            deal_threshold=_env_float("RADAR_DEAL_THRESHOLD", cls.deal_threshold),
            tax_estimate_brl=_env_float("RADAR_TAX_ESTIMATE_BRL", cls.tax_estimate_brl),
            milheiro=milheiro,
            fx=fx,
            serpapi_key=_env("SERPAPI_KEY"),
            seats_aero_key=_env("SEATS_AERO_KEY"),
            seats_aero_sources=_env("SEATS_AERO_SOURCES"),
            browser_headless=_env_bool("RADAR_BROWSER_HEADLESS", True),
            browser_profile_dir=_env("RADAR_BROWSER_PROFILE_DIR", cls.browser_profile_dir),
            browser_executable=_env("RADAR_BROWSER_EXECUTABLE"),
            browser_timeout=_env_float("RADAR_BROWSER_TIMEOUT", cls.browser_timeout),
            smiles_club=_env_bool("RADAR_SMILES_CLUB", False),
            debug_dump_dir=_env("RADAR_DEBUG_DUMP_DIR"),
            notify_mode=_env("RADAR_NOTIFY", cls.notify_mode).lower(),
            telegram_token=_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
            smtp_host=_env("SMTP_HOST"),
            smtp_port=_env_int("SMTP_PORT", cls.smtp_port),
            smtp_user=_env("SMTP_USER"),
            smtp_password=_env("SMTP_PASSWORD"),
            email_from=_env("EMAIL_FROM"),
            email_to=_env("EMAIL_TO"),
        )

    def to_brl(self, amount: float, currency: str) -> float:
        rate = self.fx.get((currency or "BRL").upper())
        if rate is None:
            raise ValueError(f"Sem cotação para {currency}; configure RADAR_FX")
        return amount * rate
