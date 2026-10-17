"""Painel web: cadastro de radares e visualização das melhores tarifas."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..airports import GROUPS, airport_name, country_flag, expand_airports
from ..alerts import evaluate
from ..config import Settings
from ..db import Database
from ..models import CABINS, FareKind, Watch, program_label
from ..notifier import brl, fmt_date, miles_fmt
from ..runner import analyze_watch, run_all

log = logging.getLogger(__name__)
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.filters.update(
    brl=brl, miles=miles_fmt, dmy=fmt_date, program=program_label, airport=airport_name, flag=country_flag
)
TEMPLATES.env.globals.update(FareKind=FareKind, GROUPS=GROUPS, CABINS=CABINS)

WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
TEMPLATES.env.filters["weekday"] = lambda d: WEEKDAYS[d.weekday()]


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


def create_app(settings: Settings | None = None, with_scheduler: bool = False) -> FastAPI:
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

    app = FastAPI(title="Radar de Milhas", lifespan=lifespan)
    app.state.db = db
    app.state.settings = settings

    def render(request: Request, name: str, status_code: int = 200, **ctx) -> HTMLResponse:
        ctx.setdefault("settings", settings)
        return TEMPLATES.TemplateResponse(request, name, ctx, status_code=status_code)

    def index_context() -> dict:
        watches = []
        for w in db.list_watches():
            history = db.run_history(w.id, limit=1)
            watches.append({"watch": w, "last": history[0] if history else None, "running": w.id in running})
        return {"watches": watches, "health": db.provider_health(), "today": date.today()}

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
        return RedirectResponse(f"/watches/{watch.id}", status_code=303)

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
            history=history, running=watch.id in running, alerts=db.list_alerts(watch.id),
            active_alerts=evaluate(analysis, settings),
        )

    @app.post("/watches/{watch_id}/run")
    async def run_now(watch_id: int):
        watch = get_or_404(watch_id)
        if watch.id not in running:
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
        return RedirectResponse(f"/watches/{watch.id}", status_code=303)

    @app.post("/watches/{watch_id}/metas")
    async def update_targets(watch_id: int, meta_dinheiro: str = Form(""), meta_milhas: str = Form("")):
        watch = get_or_404(watch_id)
        try:
            cash, miles = _opt_float(meta_dinheiro), _opt_int(meta_milhas.replace(".", ""))
        except ValueError as exc:
            raise HTTPException(400, "Meta inválida") from exc
        db.update_targets(watch.id, cash, miles)
        return RedirectResponse(f"/watches/{watch.id}#alertas", status_code=303)

    @app.post("/watches/{watch_id}/toggle")
    async def toggle(watch_id: int):
        watch = get_or_404(watch_id)
        db.set_watch_active(watch.id, not watch.active)
        return RedirectResponse(f"/watches/{watch.id}", status_code=303)

    @app.post("/watches/{watch_id}/delete")
    async def delete(watch_id: int):
        get_or_404(watch_id)
        db.delete_watch(watch_id)
        return RedirectResponse("/", status_code=303)

    return app
