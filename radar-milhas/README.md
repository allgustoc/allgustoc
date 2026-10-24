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
- **Alertas de preço baixo** (como no Voe Livre e no Google Flights): defina uma meta em R$ e/ou em
  milhas por radar e receba um aviso 🚨 quando ela for atingida, quando aparecer o menor preço já visto,
  quando o preço cair 10% abaixo da média ou quando surgir uma data fora da janela bem mais barata. O
  mesmo alerta não se repete todo dia: só volta se o preço cair mais 3% ou depois de 7 dias.
- **Avisos** por WhatsApp, Telegram e/ou e-mail: alertas sempre, mais um resumo diário (`RADAR_NOTIFY=digest`) ou
  só os alertas (`RADAR_NOTIFY=deals`).
- **Painel web** para cadastrar radares e ver ranking, sugestões, calendário de preços e histórico.

## Instalação

Precisa de **Python 3.11 ou mais novo** e **Git**. Todos os preços vêm dos sites das companhias: não há
dados inventados.

### Windows (Prompt de Comando)

1. Instale o Python: `winget install -e --id Python.Python.3.12` (ou baixe em python.org e marque
   **"Add python.exe to PATH"**). Feche e abra o terminal de novo.
2. Rode, um comando por vez:

```
git clone -b claude/airline-ticket-search-bot-ykiq0k https://github.com/allgustoc/allgustoc.git
cd allgustoc\radar-milhas
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e ".[dev]"
python -m playwright install chromium
copy .env.example .env
radar diagnostico --origem CNF --destino LIS --data 2027-05-28
radar web --agendar
```

Abra **http://localhost/radar-milhas**. (No PowerShell, ative com `.venv\Scripts\Activate.ps1`.)

O painel usa a porta 80, então o endereço não leva número. Se a porta 80 estiver ocupada por outro
programa, o bot avisa e usa a 8000: http://localhost:8000/radar-milhas. O endereço certo sempre aparece
na janela do terminal, que precisa ficar aberta enquanto você usa o painel. Opções: `radar web --porta 8080`
e `radar web --caminho /` (painel na raiz).

### Deixar o painel sempre aberto (Windows)

Na pasta `radar-milhas\windows`:

- **`iniciar-radar.bat`**: dê dois cliques. Abre o painel em http://localhost/radar-milhas, faz a busca diária no
  horário configurado e reinicia sozinho se parar. Para encerrar, feche a janela preta.
- **`ativar-inicio-automatico.bat`**: faz o radar abrir sozinho (minimizado) toda vez que você entrar no
  Windows. Para desfazer, use `desativar-inicio-automatico.bat`.

O computador precisa estar ligado no horário da busca (`RADAR_RUN_AT`, padrão 07:00).

### Mac / Linux

```bash
git clone -b claude/airline-ticket-search-bot-ykiq0k https://github.com/allgustoc/allgustoc.git
cd allgustoc/radar-milhas
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && python -m playwright install chromium
cp .env.example .env
radar diagnostico --origem GRU --destino LIS
radar web --agendar
```

## Fontes de dados

As companhias **não oferecem API pública** para os programas de fidelidade. Por padrão o bot abre os
próprios sites num navegador (Chromium) e lê as tarifas que o site recebe, como uma pessoa faria:

| Fonte (`RADAR_PROVIDERS`) | Traz | Como funciona | Custo |
|---|---|---|---|
| `latam` | Dinheiro + LATAM Pass | Site da LATAM, buscas em reais e em pontos | Grátis |
| `smiles` | Milhas Smiles (GOL e parceiras) | Site da Smiles; consulta a taxa de embarque dos voos mais baratos | Grátis |
| `azul` | Dinheiro + Azul Fidelidade | Site da Azul (experimental) | Grátis |
| `serpapi` | Dinheiro (TAP, Iberia, Air Europa, todas) | API do Google Flights via [SerpApi](https://serpapi.com/google-flights-api), `SERPAPI_KEY` | Plano gratuito limitado |
| `seats_aero` | Milhas (Smiles, Azul e outros) | [seats.aero](https://seats.aero) Partner API, `SEATS_AERO_KEY` | Plano Pro |

Padrão: `RADAR_PROVIDERS=latam,smiles,azul`.

**Atenção:** LATAM, Azul e, às vezes, Smiles têm proteção antirrobô e podem bloquear o acesso
automatizado. Quando isso acontece, o bot para aquela fonte, mostra o aviso no painel e salva uma captura
da tela em `data/debug/`; ele **não** tenta burlar a proteção. Para ter dados confiáveis todo dia, use as
fontes por API, feitas para acesso automatizado:

- **Dinheiro:** crie uma conta gratuita na [SerpApi](https://serpapi.com/users/sign_up), copie a chave para
  `SERPAPI_KEY` e acrescente `serpapi` em `RADAR_PROVIDERS`. Cobre TAP, LATAM, Azul, Iberia e Air Europa.
- **Milhas:** assine o plano Pro do [seats.aero](https://seats.aero), gere a chave da Partner API em
  `SEATS_AERO_KEY` e acrescente `seats_aero`.

Exemplo: `RADAR_PROVIDERS=serpapi,seats_aero,smiles`. Cada consulta conta no limite do plano; ajuste
`RADAR_MAX_SEARCHES_PER_PROVIDER` e a janela de datas para caber nele.

### Diagnóstico

Os sites mudam sem aviso. Para conferir se cada fonte está funcionando:

```bash
radar diagnostico --origem CNF --destino LIS --data 2027-05-28
```

Ele abre cada site, mostra as tarifas lidas (ou o motivo da falha e o que fazer) e salva as respostas
brutas em `data/debug/`. Se uma fonte vier vazia ou com erro, esses arquivos permitem ajustar o conector
(`radar/providers/<fonte>.py`). No painel, a página do radar mostra o progresso de cada fonte durante a
busca e explica qualquer falha.

## Cadastro de radares

**Pelo painel** (`radar web`): use o formulário "Novo radar".

**Pela linha de comando:**

```bash
radar add --origem GRU --destino LIS,OPO --inicio 2027-04-01 --fim 2027-04-30 \
          --noites 7-12 --adultos 2 --max-paradas 1 --meta-milhas 140000 --explorar 20
radar add --origem REC --destino ES --inicio 01/09/2027 --fim 30/09/2027 --so-ida
radar list
radar report 1        # resumo atual sem fazer novas buscas
radar meta 1 --dinheiro 4200 --milhas 110000   # metas de alerta (0 remove); lista os alertas enviados
radar pause 1 / radar resume 1 / radar remove 1
radar fontes          # fontes disponíveis e quais estão ativas
```

- `--inicio` e `--fim`: primeiro e último dia da viagem (a ida sai a partir de `inicio`; a volta chega
  até `fim`).
- `--noites`: duração da viagem (`10-18`, ou `14` para exatamente 14).
- Metas valem **por pessoa, ida e volta**, e podem ser alteradas depois em `radar meta` ou na seção
  "Alertas de preço baixo" do painel. A meta em milhas considera a viagem com menos milhas na janela.

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

**WhatsApp:** o bot usa o [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/),
gratuito, que manda mensagens para o seu próprio número. Adicione o número do CallMeBot aos contatos,
envie a ele a mensagem de ativação indicada no site e copie a apikey recebida. No `.env`:
`WHATSAPP_PHONE=+5531999999999` e `WHATSAPP_APIKEY=<sua apikey>`.

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
  alerts.py       regras de alerta (metas, recorde, queda, datas melhores) sem repetição
  analyzer.py     monta idas e voltas, rankings, sugestões, "vale usar milhas?" e tendência
  valuation.py    milhas → reais pelo custo do milheiro
  db.py           SQLite: radares, buscas, tarifas e histórico
  notifier.py     resumo para Telegram, e-mail e console
  scheduler.py    agenda diária
  web/            painel (FastAPI + Jinja + CSS próprio; decisões de design em DESIGN.md)
  providers/      latam, smiles, azul (+ browser.py), serpapi, seats_aero; demo só para testes
```

Para adicionar uma fonte, implemente `Provider.search()` (ou `search_range()` para fontes que respondem
várias datas por chamada), devolvendo `FareQuote` só de ida por passageiro, e registre-a em
`providers/__init__.py`.

## Testes

```bash
pip install -e ".[dev]"
pytest
```

Os testes cobrem planejamento, análise (combinações, sugestões, metas e tendência), parsers de cada
fonte, a execução completa (com dados sintéticos, só nos testes), o painel web e a captura via navegador contra um site
local.

## Cuidados

- **Confirme sempre no site antes de emitir.** Disponibilidade de assentos-prêmio muda em minutos, e
  taxas marcadas com `~` são estimativas (`RADAR_TAX_ESTIMATE_BRL`).
- A automação de sites pode contrariar os termos de uso das companhias. Use para fins pessoais e em
  volume baixo (os padrões já são conservadores), e prefira as APIs (`serpapi`, `seats_aero`) quando
  possível.
- O bot não faz login nem emite passagens: só pesquisa e avisa.
