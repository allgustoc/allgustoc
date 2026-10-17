# ✈️ Radar de Milhas

Bot que procura **todo dia** passagens do Brasil para **Portugal e Espanha**, em **dinheiro e em milhas**
(Smiles/GOL, LATAM Pass e Azul Fidelidade). Ele compara as duas formas de pagamento, mostra a melhor
combinação e sugere **datas fora da sua janela** que estejam bem mais baratas.

## O que ele faz

- **Você cadastra o radar:** origem(ns), destino(s), data de início e data de fim, ida e volta ou só ida,
  quantas noites, passageiros, cabine e metas de preço opcionais. Pode usar atalhos de destino: `PT`
  (LIS, OPO, FAO), `ES` (MAD, BCN, AGP, VLC, SVQ), `PTES` (os dois), `PT+` e `ES+` (incluem ilhas e
  outras cidades).
- **Busca diária** no horário configurado, consultando cada data de ida e de volta da janela.
- **Dinheiro e milhas lado a lado.** Para comparar, as milhas viram reais pelo **seu custo do milheiro**
  (`RADAR_MILHEIRO`). Uma emissão de 60.000 milhas Smiles + R$ 400 de taxas, com milheiro a R$ 16, custa
  na prática R$ 1.360.
- **Melhor combinação:** como os programas cobram cada trecho separadamente, o bot monta a ida e a
  volta de forma independente. A ida pode sair pela Smiles e a volta pela LATAM em dinheiro, por exemplo.
  Também aceita chegar numa cidade e voltar de outra (Lisboa na ida, Madri na volta).
- **"Vale usar milhas?":** na mesma rota e data, calcula quanto cada milheiro rende:
  `(tarifa em dinheiro − taxas) ÷ milheiros`. Se rende mais do que custa, emitir com milhas compensa.
- **Sugestões de outras datas:** além da janela, amostra até `explorar` dias antes e depois (30 por
  padrão) e avisa quando uma combinação fica pelo menos 12% mais barata que a melhor opção da janela.
- **Termômetro de preço:** compara o melhor preço de hoje com a mediana das últimas buscas do próprio
  radar e destaca o menor preço já visto, quedas de 10% ou mais e metas atingidas.
- **Avisos** por Telegram e/ou e-mail: um resumo diário, ou só quando houver oportunidade
  (`RADAR_NOTIFY=deals`).
- **Painel web** para cadastrar radares e ver ranking, sugestões, calendário de preços e histórico.

## Começo rápido (modo demonstração)

```bash
cd radar-milhas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # começa com RADAR_PROVIDERS=demo

radar add --nome "Férias Europa" --origem GRU,VCP --destino PTES \
          --inicio 2026-12-10 --fim 2027-01-20 --noites 10-18 --meta-dinheiro 5000
radar run                        # busca agora e imprime o resumo
radar web                        # painel em http://127.0.0.1:8000
```

A fonte `demo` gera preços sintéticos e plausíveis para você ver o bot inteiro funcionando antes de
configurar as fontes reais.

## Fontes de dados

As companhias **não oferecem API pública** para os programas de fidelidade. Por isso o bot combina
fontes estáveis por API com a leitura automatizada dos próprios sites:

| Fonte (`RADAR_PROVIDERS`) | Traz | Como funciona | Estabilidade |
|---|---|---|---|
| `serpapi` | 💵 Dinheiro (TAP, LATAM, Azul, Iberia, Air Europa…) | API do Google Flights via [SerpApi](https://serpapi.com/google-flights-api), `SERPAPI_KEY` | Alta (API paga, com plano gratuito) |
| `seats_aero` | 🎯 Milhas (Smiles, Azul e outros programas) | [seats.aero](https://seats.aero) Partner API, `SEATS_AERO_KEY` (plano Pro). Varre várias datas por chamada | Alta |
| `smiles` | 🎯 Milhas Smiles | Abre a busca do site num Chromium e lê o JSON que o próprio site recebe. Consulta a taxa de embarque dos voos mais baratos | Média: o site muda e tem antirrobô |
| `latam` | 💵 Dinheiro + 🎯 LATAM Pass | Igual ao anterior, nas buscas em reais e em pontos | Média |
| `azul` | 💵 Dinheiro + 🎯 Azul Fidelidade | Igual ao anterior (experimental) | Baixa/média |
| `demo` | Ambos | Dados sintéticos | Só para testes |

Configuração recomendada: `RADAR_PROVIDERS=serpapi,seats_aero,latam,smiles`.

Para as fontes de site, instale o navegador:

```bash
pip install -e ".[browser]"
playwright install chromium
```

### Valide os conectores de site antes de confiar neles

Os formatos internos dos sites mudam sem aviso, então os conectores `smiles`, `latam` e `azul` foram
escritos para **avisar quando algo muda**, sem falhar em silêncio. Teste cada um na sua máquina:

```bash
radar probe smiles GRU LIS 2027-03-10
radar probe latam  GRU LIS 2027-03-10
radar probe azul   VCP LIS 2027-03-10
```

O comando mostra as tarifas lidas e salva as respostas brutas em `data/debug/`. Se o site mudou o
formato, é ali que se ajusta o parser (`radar/providers/<fonte>.py`). Se o site pedir captcha, use
`RADAR_BROWSER_HEADLESS=false`, resolva uma vez na janela que abrir e o perfil persistente
(`data/browser/`) guarda os cookies.

## Cadastro de radares

**Pelo painel** (`radar web`): use o formulário "Novo radar".

**Pela linha de comando:**

```bash
radar add --origem GRU --destino LIS,OPO --inicio 2027-04-01 --fim 2027-04-30 \
          --noites 7-12 --adultos 2 --max-paradas 1 --meta-milhas 140000 --explorar 20
radar add --origem REC --destino ES --inicio 01/09/2027 --fim 30/09/2027 --so-ida
radar list
radar report 1        # resumo atual sem fazer novas buscas
radar pause 1 / radar resume 1 / radar remove 1
radar fontes          # fontes disponíveis e quais estão ativas
```

- `--inicio` e `--fim`: primeiro e último dia da viagem (a ida sai a partir de `inicio`; a volta chega
  até `fim`).
- `--noites`: duração da viagem (`10-18`, ou `14` para exatamente 14).
- Metas valem **por pessoa, ida e volta**.

## Buscas diárias

Escolha uma das formas:

```bash
radar web --agendar          # painel + busca diária no horário RADAR_RUN_AT
radar daemon --agora         # só o agendador (sem painel); --agora faz uma busca ao iniciar
docker compose up -d         # painel + agendador em container (dados em ./data)
```

Ou pelo cron do sistema: `0 7 * * * cd /caminho/radar-milhas && .venv/bin/radar run`.

Para os sites não bloquearem o bot, cada varredura respeita um orçamento por fonte
(`RADAR_MAX_SEARCHES_PER_PROVIDER`) e pausas entre consultas, nesta ordem de prioridade:

1. datas dentro da sua janela nunca consultadas ou consultadas há mais tempo;
2. cerca de 25% do orçamento vai para datas fora da janela, amostradas em rodízio a cada
   `RADAR_EXPLORE_STEP_DAYS` dias, para que todas sejam cobertas em poucos dias;
3. consultas feitas há menos de `RADAR_REFRESH_HOURS` são reaproveitadas, inclusive entre radares
   diferentes com a mesma rota.

Se a busca mais recente de uma data voltar vazia, as tarifas antigas daquela data saem do ranking: o
bot não recomenda o que esgotou.

## Notificações

**Telegram:** crie um bot com o [@BotFather](https://t.me/BotFather) e copie o token para
`TELEGRAM_BOT_TOKEN`. Mande uma mensagem ao seu bot e abra
`https://api.telegram.org/bot<TOKEN>/getUpdates` para descobrir o `chat.id`, que vai em
`TELEGRAM_CHAT_ID`.

**E-mail:** preencha `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` e `EMAIL_TO`. No Gmail,
use uma senha de app.

Exemplo de resumo:

```
✈️ Férias Europa
GRU,VCP → LIS,MAD · 10/12/26 a 20/01/27 · ida e volta, 10–18 noites

💵 Melhor em dinheiro 🔥 14% abaixo da média
R$ 3.718 · 17 noites
   ida: 11/12/26 19:21 GRU→LIS🇵🇹 · R$ 1.582 · Air Europa · 1 parada
   volta: 28/12/26 20:25 LIS→GRU🇧🇷 · R$ 2.136 · TAP Air Portugal · 1 parada

🎯 Melhor em milhas
R$ 2.735 (≈ 104.000 milhas + R$ 1.071) · 11 noites
   ida: 01/01/27 GRU→MAD🇪🇸 · 63.000 Smiles (GOL) + R$ 632 · direto
   volta: 12/01/27 MAD→GRU🇧🇷 · 41.000 Smiles (GOL) + R$ 438 · 1 parada

💡 Vale usar milhas?
• Smiles (GOL): rendendo R$ 33/milheiro (seu custo R$ 16) → Vale muito a pena usar milhas

📅 Datas fora do seu radar com bom preço
R$ 2.071 (≈ 73.000 milhas + R$ 903) · 17 noites · 24% mais barato que sua janela
   ida: 25/11/26 GRU→LIS🇵🇹 · 38.000 Smiles (GOL) + R$ 490 · direto
   volta: 12/12/26 MAD→VCP🇧🇷 · 35.000 Smiles (GOL) + R$ 413 · 1 parada
```

## Arquitetura

```
radar/
  cli.py          comandos `radar ...`
  planner.py      decide quais rotas/datas consultar (janela, exploração, orçamento)
  runner.py       executa as fontes em paralelo, com novas tentativas e parada em caso de bloqueio
  analyzer.py     monta idas e voltas, rankings, sugestões, "vale usar milhas?" e tendência
  valuation.py    milhas → reais pelo custo do milheiro
  db.py           SQLite: radares, buscas, tarifas e histórico
  notifier.py     resumo para Telegram, e-mail e console
  scheduler.py    agenda diária
  web/            painel (FastAPI + Jinja)
  providers/      demo, serpapi, seats_aero, smiles, latam, azul (+ browser.py)
```

Para adicionar uma fonte, implemente `Provider.search()` (ou `search_range()` para fontes que respondem
várias datas por chamada), devolvendo `FareQuote` só de ida por passageiro, e registre-a em
`providers/__init__.py`.

## Testes

```bash
pip install -e ".[dev,browser]"
pytest
```

Os testes cobrem planejamento, análise (combinações, sugestões, metas e tendência), parsers de cada
fonte, a execução completa com a fonte demo, o painel web e a captura via navegador contra um site
local.

## Cuidados

- **Confirme sempre no site antes de emitir.** Disponibilidade de assentos-prêmio muda em minutos, e
  taxas marcadas com `~` são estimativas (`RADAR_TAX_ESTIMATE_BRL`).
- A automação de sites pode contrariar os termos de uso das companhias. Use para fins pessoais e em
  volume baixo (os padrões já são conservadores), e prefira as APIs (`serpapi`, `seats_aero`) quando
  possível.
- O bot não faz login nem emite passagens: só pesquisa e avisa.
