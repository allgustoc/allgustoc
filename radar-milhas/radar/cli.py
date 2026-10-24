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


def cmd_targets(args, settings, db) -> int:
    watch = db.get_watch(args.id)
    if not watch:
        print("Radar não encontrado")
        return 1
    cash = watch.target_cash_brl if args.dinheiro is None else (args.dinheiro or None)
    miles = watch.target_miles if args.milhas is None else (args.milhas or None)
    db.update_targets(watch.id, cash, miles)
    cash_txt = f"R$ {cash:,.0f}".replace(",", ".") if cash else "—"
    miles_txt = f"{miles:,}".replace(",", ".") if miles else "—"
    print(f"Metas do radar #{watch.id}: dinheiro {cash_txt} · milhas {miles_txt} (por pessoa, ida e volta)")
    for alert in db.list_alerts(watch.id, limit=args.historico):
        print(f"  {alert['sent_at'][:16].replace('T', ' ')}  {alert['message']}")
    return 0


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


def cmd_diagnose(args, settings: Settings, db: Database) -> int:
    """Testa cada fonte configurada numa rota real e explica o que fazer se falhar."""
    from datetime import timedelta

    from .providers import PROVIDER_LABELS, create_providers
    from .providers.browser import BrowserSession

    settings.debug_dump_dir = settings.debug_dump_dir or "data/debug"
    watches = db.list_watches(only_active=True)
    if args.origem and args.destino:
        origin, destination = args.origem.upper(), args.destino.upper()
        day = args.data or date.today() + timedelta(days=60)
    elif watches:
        w = watches[0]
        origin, destination = w.origins[0], w.destinations[0]
        day = max(w.start_date, date.today() + timedelta(days=1))
    else:
        origin, destination, day = "GRU", "LIS", date.today() + timedelta(days=60)
    print(f"Fontes configuradas (RADAR_PROVIDERS): {', '.join(settings.providers) or 'nenhuma'}")
    print(f"Rota de teste: {origin} → {destination} em {day:%d/%m/%Y}\n")

    async def go() -> int:
        failures_total = 0
        providers, failures = create_providers(settings)
        for key, msg in failures:
            failures_total += 1
            print(f"✗ {PROVIDER_LABELS.get(key, key)}: {msg}")
        if any(p.key in ("smiles", "latam", "azul") for p in providers):
            session = BrowserSession(settings, "diagnostico")
            try:
                await session._ensure()
                print("✓ Navegador automatizado: abre normalmente")
            except Exception as exc:
                print(f"✗ Navegador automatizado: {exc}\n  Rode: python -m playwright install chromium")
                return 1
            finally:
                await session.close()
        for provider in providers:
            label = PROVIDER_LABELS.get(provider.key, provider.key)
            try:
                quotes = await provider.search(origin, destination, day, 1, "economy")
            except Exception as exc:
                failures_total += 1
                print(f"✗ {label}: {exc}")
                continue
            finally:
                await provider.close()
            cash = sorted((q for q in quotes if q.kind == "cash"), key=lambda q: q.price_brl or 0)
            miles = sorted((q for q in quotes if q.kind == "miles"), key=lambda q: q.miles or 0)
            print(f"✓ {label}: {len(cash)} tarifas em dinheiro, {len(miles)} em milhas")
            for q in (cash[:2] + miles[:2]):
                print("    " + leg_text(Leg(q, effective_cost_brl(q, settings))))
            if not quotes:
                print("    Nenhum voo nesta data. Pode ser falta de disponibilidade ou mudança no site;"
                      f" envie os arquivos de {settings.debug_dump_dir}/ para análise.")
        print(f"\nRespostas brutas salvas em {settings.debug_dump_dir}/")
        return 1 if failures_total else 0

    return asyncio.run(go())


def cmd_web(args, settings, db) -> int:
    import uvicorn

    from .web.app import create_app

    db.close()
    port = args.porta
    if not _port_free(args.host, port):
        fallback = 8000 if port != 8000 else 8080
        print(f"A porta {port} está ocupada ou bloqueada neste computador; usando a porta {fallback}.")
        port = fallback
    base = "/" + args.caminho.strip("/") if args.caminho.strip("/") else ""
    shown_host = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    url = f"http://{shown_host}{'' if port == 80 else f':{port}'}{base}/"
    print(f"\nPainel do Radar de Milhas: {url}")
    print("Deixe esta janela aberta enquanto usar o painel.\n")
    if args.abrir:
        import threading
        import webbrowser

        threading.Timer(2.0, webbrowser.open, [url]).start()
    app = create_app(settings, with_scheduler=args.agendar, base_path=base)
    uvicorn.run(app, host=args.host, port=port, log_level="warning")
    return 0


def _port_free(host: str, port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


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

    m = sub.add_parser("meta", help="Definir metas de preço (alerta) de um radar e ver alertas enviados")
    m.add_argument("id", type=int)
    m.add_argument("--dinheiro", type=float, help="R$ por pessoa, ida e volta (0 remove)")
    m.add_argument("--milhas", type=int, help="Milhas por pessoa, ida e volta (0 remove)")
    m.add_argument("--historico", type=int, default=10, help="Quantos alertas enviados listar")
    m.set_defaults(func=cmd_targets)

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

    dg = sub.add_parser("diagnostico", help="Testar as fontes reais numa rota e mostrar o que falhou")
    dg.add_argument("--origem")
    dg.add_argument("--destino")
    dg.add_argument("--data", type=_date)
    dg.set_defaults(func=cmd_diagnose)

    w = sub.add_parser("web", help="Painel web para cadastrar e acompanhar radares")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--porta", type=int, default=80, help="Padrão 80 (endereço sem número de porta)")
    w.add_argument("--abrir", action="store_true", help="Abre o painel no navegador ao iniciar")
    w.add_argument("--caminho", default="/radar-milhas", help="Caminho do painel no endereço (padrão /radar-milhas)")
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
    if "demo" not in settings.providers and db.purge_provider("demo"):
        print("Dados de teste antigos removidos; o radar mostra só preços reais.", file=sys.stderr)
    try:
        return args.func(args, settings, db)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
