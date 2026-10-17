"""Linha de comando: `radar --help`."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime

from .airports import airport_name, expand_airports
from .config import Settings
from .db import Database
from .models import Leg, Watch
from .notifier import _strip_html, format_digest, leg_text
from .providers import AVAILABLE, create_provider
from .runner import analyze_watch, run_all
from .valuation import effective_cost_brl


def _date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"Data inválida: {value} (use AAAA-MM-DD ou DD/MM/AAAA)")


def _nights(value: str) -> tuple[int, int]:
    lo, _, hi = value.partition("-")
    return int(lo), int(hi or lo)


def cmd_add(args, settings: Settings, db: Database) -> int:
    origins = expand_airports(args.origem)
    destinations = expand_airports(args.destino)
    min_n, max_n = _nights(args.noites)
    watch = Watch(
        name=args.nome or f"{','.join(origins)} → {','.join(destinations)}",
        origins=origins,
        destinations=destinations,
        start_date=args.inicio,
        end_date=args.fim,
        round_trip=not args.so_ida,
        min_nights=min_n,
        max_nights=max_n,
        adults=args.adultos,
        cabin=args.cabine,
        max_stops=args.max_paradas,
        target_cash_brl=args.meta_dinheiro,
        target_miles=args.meta_milhas,
        explore_days=args.explorar,
    )
    db.add_watch(watch)
    print(f"Radar #{watch.id} criado: {watch.name}")
    print(f"  Origens: {', '.join(f'{c} ({airport_name(c)})' for c in origins)}")
    print(f"  Destinos: {', '.join(f'{c} ({airport_name(c)})' for c in destinations)}")
    return 0


def cmd_list(args, settings, db) -> int:
    watches = db.list_watches()
    if not watches:
        print("Nenhum radar cadastrado. Use: radar add --origem GRU --destino PT,ES --inicio ... --fim ...")
    for w in watches:
        status = "ativo" if w.active else "pausado"
        kind = f"ida e volta {w.min_nights}-{w.max_nights} noites" if w.round_trip else "só ida"
        print(
            f"#{w.id} [{status}] {w.name}: {','.join(w.origins)} → {','.join(w.destinations)} "
            f"{w.start_date:%d/%m/%Y}–{w.end_date:%d/%m/%Y} · {kind} · {w.adults} adulto(s) · {w.cabin}"
        )
    return 0


def cmd_toggle(args, settings, db, active: bool) -> int:
    ok = db.set_watch_active(args.id, active)
    print(("Radar ativado" if active else "Radar pausado") if ok else "Radar não encontrado")
    return 0 if ok else 1


def cmd_remove(args, settings, db) -> int:
    ok = db.delete_watch(args.id)
    print("Radar removido" if ok else "Radar não encontrado")
    return 0 if ok else 1


def cmd_run(args, settings, db) -> int:
    results = asyncio.run(run_all(db, settings, watch_ids=args.id or None, notify=not args.sem_notificar))
    if args.sem_notificar:
        for r in results:
            print(_strip_html(format_digest(r.analysis, settings)) + "\n")
    for r in results:
        for s in r.stats:
            line = f"[{s.provider}] radar #{r.watch.id}: {s.searches} buscas, {s.quotes} tarifas, {s.errors} erros"
            if s.stopped:
                line += f" — interrompida: {s.stopped}"
            print(line)
    return 0 if results else 1


def cmd_report(args, settings, db) -> int:
    watch = db.get_watch(args.id)
    if not watch:
        print("Radar não encontrado")
        return 1
    analysis = analyze_watch(watch, db, settings)
    print(_strip_html(format_digest(analysis, settings)))
    return 0


def cmd_probe(args, settings: Settings, db) -> int:
    """Testa uma fonte isoladamente e salva a resposta bruta para depuração."""
    settings.debug_dump_dir = settings.debug_dump_dir or "data/debug"
    provider = create_provider(args.fonte, settings)

    async def go():
        try:
            return await provider.search(args.origem.upper(), args.destino.upper(), args.data, args.adultos, "economy")
        finally:
            await provider.close()

    quotes = asyncio.run(go())
    print(f"{len(quotes)} tarifas (respostas brutas em {settings.debug_dump_dir}/)")
    for q in sorted(quotes, key=lambda q: (q.kind, q.miles or 0, q.price_brl or 0)):
        print("  " + leg_text(Leg(q, effective_cost_brl(q, settings))))
    return 0


def cmd_web(args, settings, db) -> int:
    import uvicorn

    from .web.app import create_app

    db.close()
    app = create_app(settings, with_scheduler=args.agendar)
    uvicorn.run(app, host=args.host, port=args.porta, log_level="info")
    return 0


def cmd_daemon(args, settings, db) -> int:
    from .scheduler import scheduler_loop

    asyncio.run(scheduler_loop(settings, db, run_now=args.agora))
    return 0


def cmd_providers(args, settings, db) -> int:
    for key, desc in AVAILABLE.items():
        mark = "*" if key in settings.providers else " "
        print(f" {mark} {key:<11} {desc}")
    print("\n* = ativas em RADAR_PROVIDERS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="radar", description="Radar de passagens para Portugal e Espanha (dinheiro e milhas)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="Cadastrar um radar (origem, destino e janela de datas)")
    a.add_argument("--nome")
    a.add_argument("--origem", required=True, help="Ex.: GRU ou GRU,VCP")
    a.add_argument("--destino", required=True, help="Ex.: LIS,MAD ou PT, ES, PTES, PT+, ES+")
    a.add_argument("--inicio", required=True, type=_date, help="Primeiro dia possível de viagem")
    a.add_argument("--fim", required=True, type=_date, help="Último dia possível (volta)")
    a.add_argument("--so-ida", action="store_true", help="Somente ida")
    a.add_argument("--noites", default="7-21", help="Duração da viagem em noites, ex.: 10-15")
    a.add_argument("--adultos", type=int, default=1)
    a.add_argument("--cabine", default="economy", choices=["economy", "premium", "business", "first"])
    a.add_argument("--max-paradas", type=int)
    a.add_argument("--meta-dinheiro", type=float, help="Alerta se ida+volta por pessoa ficar abaixo (R$)")
    a.add_argument("--meta-milhas", type=int, help="Alerta se ida+volta por pessoa ficar abaixo (milhas)")
    a.add_argument("--explorar", type=int, default=30, help="Dias antes/depois da janela para sugerir datas")
    a.set_defaults(func=cmd_add)

    sub.add_parser("list", help="Listar radares").set_defaults(func=cmd_list)
    for name, active, help_ in (("pause", False, "Pausar radar"), ("resume", True, "Reativar radar")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("id", type=int)
        s.set_defaults(func=lambda a, s_, d, active=active: cmd_toggle(a, s_, d, active))
    r = sub.add_parser("remove", help="Excluir radar")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_remove)

    run = sub.add_parser("run", help="Buscar agora (todos os radares ativos ou --id)")
    run.add_argument("--id", type=int, action="append")
    run.add_argument("--sem-notificar", action="store_true")
    run.set_defaults(func=cmd_run)

    rep = sub.add_parser("report", help="Mostrar o resumo atual de um radar sem buscar")
    rep.add_argument("id", type=int)
    rep.set_defaults(func=cmd_report)

    pr = sub.add_parser("probe", help="Testar uma fonte numa rota/data e salvar a resposta bruta")
    pr.add_argument("fonte", choices=list(AVAILABLE))
    pr.add_argument("origem")
    pr.add_argument("destino")
    pr.add_argument("data", type=_date)
    pr.add_argument("--adultos", type=int, default=1)
    pr.set_defaults(func=cmd_probe)

    w = sub.add_parser("web", help="Painel web para cadastrar e acompanhar radares")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--porta", type=int, default=8000)
    w.add_argument("--agendar", action="store_true", help="Também roda a busca diária no horário RADAR_RUN_AT")
    w.set_defaults(func=cmd_web)

    d = sub.add_parser("daemon", help="Rodar a busca diária no horário RADAR_RUN_AT (sem painel)")
    d.add_argument("--agora", action="store_true", help="Faz uma varredura imediatamente ao iniciar")
    d.set_defaults(func=cmd_daemon)

    sub.add_parser("fontes", help="Listar fontes de dados disponíveis").set_defaults(func=cmd_providers)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    db = Database(settings.db_path)
    try:
        return args.func(args, settings, db)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
