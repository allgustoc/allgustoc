"""Painel web: cadastro de radares e visualização das melhores tarifas."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..airports import GROUPS, airport_name, country_flag, expand_airports
from ..alerts import evaluate
from ..config import Settings
from ..db import Database
from ..models import CABINS, FareKind, Watch, program_label
from ..notifier import brl, fmt_date, miles_fmt
from ..providers import PROVIDER_LABELS
from ..runner import PROGRESS, analyze_watch, run_all

log = logging.getLogger(__name__)
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.filters.update(
    brl=brl, miles=miles_fmt, dmy=fmt_date, program=program_label, airport=airport_name, flag=country_flag
)
TEMPLATES.env.globals.update(FareKind=FareKind, GROUPS=GROUPS, CABINS=CABINS)

WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
CABIN_LABELS = {"economy": "Econômica", "premium": "Premium", "business": "Executiva", "first": "Primeira"}
TEMPLATES.env.filters["weekday"] = lambda d: WEEKDAYS[d.weekday()]
TEMPLATES.env.filters["cabin"] = lambda c: CABIN_LABELS.get(c, c)
TEMPLATES.env.filters["source"] = lambda k: PROVIDER_LABELS.get(k, k)
TEMPLATES.env.filters["stamp"] = lambda iso: datetime.fromisoformat(iso).strftime("%d/%m %H:%M") if iso else ""
TEMPLATES.env.globals.update(CABIN_LABELS=CABIN_LABELS, PROVIDER_LABELS=PROVIDER_LABELS)


def short_brl(value: float | None) -> str:
    """Preço compacto para a grade do calendário: 2130 -> '2,1 mil'."""
    if value is None:
        return ""
    if value >= 1000:
        return f"{value / 1000:.1f} mil".replace(".", ",")
    return f"{value:.0f}"


TEMPLATES.env.filters["short_brl"] = short_brl

HINTS = (
    ("não está instalado", "Instale o navegador: pip install playwright e depois python -m playwright install chromium."),
    ("bloqueou", "Este site não permite acesso automatizado. Para dados confiáveis, use as fontes por API: "
                 "serpapi (dinheiro, Google Flights) e seats_aero (milhas). Veja o README."),
    ("formato de resposta inesperado", "O site mudou o formato. Rode radar diagnostico e envie os arquivos de "
                                       "data/debug para ajustar o conector."),
    ("não retornou resultados", "A página não carregou a busca a tempo. Tente de novo; se repetir, aumente "
                                "RADAR_BROWSER_TIMEOUT no arquivo .env."),
    ("chave", "Confira a chave de API no arquivo .env."),
    ("limite", "O limite de buscas da fonte acabou por hoje. A próxima varredura tenta de novo."),
)


def hint_for(message: str) -> str:
    lower = (message or "").lower()
    return next((hint for key, hint in HINTS if key in lower), "Tente de novo mais tarde. Se repetir, rode radar diagnostico.")


TEMPLATES.env.filters["hint"] = hint_for


def _opt_int(value: str | None) -> int | None:
    return int(value) if value not in (None, "") else None


def _opt_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    value = value.strip()
    if "," in value:  # formato brasileiro: 4.500,00
        value = value.replace(".", "").replace(",", ".")
    return float(value)


def _price_bands(rows: list[dict]) -> None:
    """Classifica cada data do calendário em barata/média/cara (tercis do custo)."""
    costs = sorted(r["best_cost"] for r in rows)
    if not costs:
        return
    low, high = costs[len(costs) // 3], costs[(2 * len(costs)) // 3]
    for r in rows:
        r["band"] = "low" if r["best_cost"] <= low else ("high" if r["best_cost"] > high else "mid")


DEFAULT_BASE_PATH = "/radar-milhas"


def create_app(
    settings: Settings | None = None, with_scheduler: bool = False, base_path: str = DEFAULT_BASE_PATH
) -> FastAPI:
    """Painel servido em `base_path` (ex.: http://localhost/radar-milhas); "/" redireciona para lá."""
    settings = settings or Settings.from_env()
    db = Database(settings.db_path)
    running: set[int] = set()
    background: set[asyncio.Task] = set()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if with_scheduler:
            from ..scheduler import scheduler_loop

            task = asyncio.create_task(scheduler_loop(settings, db))
        yield
        if task:
            task.cancel()
        db.close()

    base = "/" + base_path.strip("/") if base_path.strip("/") else ""
    root = FastAPI(title="Radar de Milhas", lifespan=lifespan)
    app = FastAPI(title="Radar de Milhas") if base else root
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
    root.state.db = app.state.db = db
    root.state.settings = app.state.settings = settings
    if base:
        root.mount(base, app)

        @root.get("/", include_in_schema=False)
        async def go_to_panel():
            return RedirectResponse(f"{base}/", status_code=307)

    def render(request: Request, name: str, status_code: int = 200, **ctx) -> HTMLResponse:
        ctx.setdefault("settings", settings)
        ctx.setdefault("base", base)
        return TEMPLATES.TemplateResponse(request, name, ctx, status_code=status_code)

    def is_running(watch_id: int) -> bool:
        return watch_id in running or watch_id in PROGRESS

    def last_run(watch_id: int) -> dict | None:
        history = db.run_history(watch_id, limit=1)
        if not history:
            return None
        run = history[0]
        run["log"] = json.loads(run["log"]) if run.get("log") else []
        run["issues"] = [s for s in run["log"] if s.get("stopped")]
        return run

    def index_context() -> dict:
        watches = [{"watch": w, "last": last_run(w.id), "running": is_running(w.id)} for w in db.list_watches()]
        return {"watches": watches, "today": date.today()}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return render(request, "index.html", **index_context())

    @app.post("/watches")
    async def create_watch(
        request: Request,
        nome: str = Form(""),
        origem: str = Form(...),
        destino: str = Form(...),
        inicio: date = Form(...),
        fim: date = Form(...),
        tipo: str = Form("ida_volta"),
        noites_min: int = Form(7),
        noites_max: int = Form(21),
        adultos: int = Form(1),
        cabine: str = Form("economy"),
        max_paradas: str = Form(""),
        meta_dinheiro: str = Form(""),
        meta_milhas: str = Form(""),
        explorar: int = Form(30),
    ):
        try:
            origins, destinations = expand_airports(origem), expand_airports(destino)
            watch = Watch(
                name=nome.strip() or f"{','.join(origins)} → {','.join(destinations)}",
                origins=origins,
                destinations=destinations,
                start_date=inicio,
                end_date=fim,
                round_trip=tipo != "so_ida",
                min_nights=noites_min,
                max_nights=noites_max,
                adults=adultos,
                cabin=cabine,
                max_stops=_opt_int(max_paradas),
                target_cash_brl=_opt_float(meta_dinheiro),
                target_miles=_opt_int(meta_milhas.replace(".", "")),
                explore_days=explorar,
            )
            db.add_watch(watch)
        except ValueError as exc:
            return render(request, "index.html", status_code=400, error=str(exc), form=dict(await request.form()),
                          **index_context())
        return RedirectResponse(f"{base}/watches/{watch.id}", status_code=303)

    def get_or_404(watch_id: int) -> Watch:
        watch = db.get_watch(watch_id)
        if not watch:
            raise HTTPException(404, "Radar não encontrado")
        return watch

    @app.get("/watches/{watch_id}", response_class=HTMLResponse)
    async def watch_detail(request: Request, watch_id: int):
        watch = get_or_404(watch_id)
        analysis = analyze_watch(watch, db, settings)
        outbound = [r for r in analysis.calendar if r["direction"] == "out"]
        inbound = [r for r in analysis.calendar if r["direction"] == "in"]
        _price_bands(outbound)
        _price_bands(inbound)
        history = db.run_history(watch.id, limit=15)
        for h in history:
            h["log"] = json.loads(h["log"]) if h.get("log") else []
        return render(
            request, "watch.html", watch=watch, a=analysis, outbound=outbound, inbound=inbound,
            history=history, last=last_run(watch.id), running=is_running(watch.id),
            progress=PROGRESS.get(watch.id), alerts=db.list_alerts(watch.id),
            active_alerts=evaluate(analysis, settings),
        )

    @app.get("/watches/{watch_id}/status")
    async def watch_status(watch_id: int):
        get_or_404(watch_id)
        state = PROGRESS.get(watch_id) or {}
        return JSONResponse({"running": is_running(watch_id), "providers": state.get("providers", {})})

    @app.post("/watches/{watch_id}/run")
    async def run_now(watch_id: int):
        watch = get_or_404(watch_id)
        if not is_running(watch.id):
            running.add(watch.id)

            async def job():
                try:
                    await run_all(db, settings, watch_ids=[watch.id])
                except Exception:
                    log.exception("Falha ao rodar radar #%s", watch.id)
                finally:
                    running.discard(watch.id)

            task = asyncio.create_task(job())
            background.add(task)
            task.add_done_callback(background.discard)
        return RedirectResponse(f"{base}/watches/{watch.id}", status_code=303)

    @app.post("/watches/{watch_id}/metas")
    async def update_targets(watch_id: int, meta_dinheiro: str = Form(""), meta_milhas: str = Form("")):
        watch = get_or_404(watch_id)
        try:
            cash, miles = _opt_float(meta_dinheiro), _opt_int(meta_milhas.replace(".", ""))
        except ValueError as exc:
            raise HTTPException(400, "Meta inválida") from exc
        db.update_targets(watch.id, cash, miles)
        return RedirectResponse(f"{base}/watches/{watch.id}#alertas", status_code=303)

    @app.post("/watches/{watch_id}/toggle")
    async def toggle(watch_id: int):
        watch = get_or_404(watch_id)
        db.set_watch_active(watch.id, not watch.active)
        return RedirectResponse(f"{base}/watches/{watch.id}", status_code=303)

    @app.post("/watches/{watch_id}/delete")
    async def delete(watch_id: int):
        get_or_404(watch_id)
        db.delete_watch(watch_id)
        return RedirectResponse(f"{base}/", status_code=303)

    return root
