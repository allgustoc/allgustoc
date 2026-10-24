# DESIGN.md

## Perfil
`app-product`: ferramenta pessoal operada com frequência. Densidade média, estados completos, movimento baixo.

## Stack
A existente: FastAPI + Jinja2 + CSS próprio em `radar/web/static/app.css`, JS mínimo em `radar/web/static/app.js`
(só para acompanhar a busca em andamento). Controles nativos (`select`, `input type=date`), sem biblioteca de
componentes: são acessíveis por padrão e bastam para formulários simples.

## Direção visual
O mundo do produto é o saguão de aeroporto: o painel de partidas, o cartão de embarque, a sinalização de
aeroporto (letras condensadas, amarelo sobre fundo escuro). A interface empresta essa linguagem com contenção.

### Assinatura
**O cartão de embarque.** A melhor opção de cada radar aparece como um cartão de embarque: códigos IATA
grandes em fonte condensada, ida e volta separadas por uma linha picotada, preço em mono à direita.
É o único elemento ousado. O resto é disciplinado.

### Paleta (tokens em `app.css`)
| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `--bg` | `#0F1417` | `#F4F1EA` | fundo da página |
| `--surface` | `#161D21` | `#FFFDF8` | cartões e tabelas |
| `--surface-2` | `#1E272C` | `#EFEBE2` | campos, linhas alternadas |
| `--line` | `#2B363C` | `#DDD7CA` | bordas |
| `--text` | `#ECE9E1` | `#1B2226` | texto principal |
| `--muted` | `#9AA6AC` | `#5B676D` | texto secundário |
| `--accent` | `#F2B33D` | `#F2B33D` | único acento: botão primário, assinatura, foco |
| `--on-accent` | `#1A160C` | `#1A160C` | texto sobre o acento |
| `--good` / `--good-bg` | `#6CCB97` / `#16301F` | `#1C7A47` / `#E3F2E8` | preço baixo, sucesso (semântico) |
| `--bad` / `--bad-bg` | `#FF8C7A` / `#3A1D19` | `#B3261E` / `#FBE7E4` | erro, preço alto (semântico) |

Verde e vermelho são semânticos (dado de preço e estado), não acentos decorativos.

### Tipografia
- **Display:** Barlow Condensed 600/700, a letra da sinalização de aeroporto. Só em códigos IATA, título do
  radar e preço de destaque.
- **Corpo:** IBM Plex Sans 400/500/600.
- **Dados:** IBM Plex Mono 500 com `tabular-nums` para preços, milhas, datas e horários.
- Fallback: `system-ui` / `ui-monospace` (as fontes carregam do Google Fonts; sem internet o painel segue legível).

Escala (rem): 0.8125 / 0.875 / 1 / 1.125 / 1.375 / 1.75 / 2.5 (códigos do cartão).

### Espaçamento e forma
- Unidade 4px: `--space-1` 4 … `--space-8` 48.
- **Lock de forma:** raio pequeno em tudo, `--radius` 8px (cartões, campos, botões) e `--radius-sm` 4px (etiquetas).
  Nada de pílula, nada de canto reto.

## Locks
1. **Cor:** um acento (`--accent`, amarelo de sinalização) em toda a interface.
2. **Forma:** raio 8px / 4px, conforme acima.
3. **Tema:** automático (`prefers-color-scheme`), escuro e claro com contraste AA e a mesma hierarquia.
   O escuro é o tema principal do usuário e foi desenhado primeiro.

## Movimento
Orçamento baixo: hover/foco de controles (120ms), barra de progresso da busca em andamento, nada mais.
`prefers-reduced-motion` desliga a animação da barra.

## Estados obrigatórios
Toda tela que mostra tarifas trata: vazio (nunca buscado, com convite para buscar), carregando (busca em
andamento com progresso por fonte), erro (fonte bloqueada ou falhou, com o motivo e o que fazer), parcial
(algumas fontes falharam) e sucesso.

## Banimentos
- Gradientes decorativos, glassmorphism, sombras coloridas, emoji como ícone de seção.
- Inter/Arial como display; texto em caixa alta corrida fora de etiquetas curtas.
- Três cards de KPI idênticos lado a lado como abertura de página.
- Tabelas com mais de ~15 linhas abertas por padrão (usar grade de calendário ou `details`).
- Travessão (—) em copy de interface; use "sem dados" ou um traço curto só em células vazias de tabela.
- Qualquer preço que não venha de uma fonte real.

## Checklist de entrega
- [ ] Contraste AA nos dois temas; foco visível distinto do hover.
- [ ] Funciona em 360px sem rolagem horizontal da página.
- [ ] Rótulos reais em todos os campos; erros de formulário em texto.
- [ ] Estados vazio, carregando, erro e parcial presentes na página do radar.
- [ ] Alvos de toque ≥ 44px.
