# PRODUCT.md

## O que é
Radar de Milhas: bot pessoal que busca todo dia passagens do Brasil para Portugal e Espanha em dinheiro e
em milhas (Smiles, LATAM Pass, Azul Fidelidade) e avisa quando aparece um preço bom.

## Para quem
Uma pessoa que acumula milhas em mais de um programa e planeja uma viagem com alguns meses de antecedência.
Usa o painel no computador (tema escuro) e recebe os alertas no celular.

## Tarefa principal da interface
Responder, em segundos: **qual é a melhor passagem agora para este radar, e é melhor pagar em dinheiro
ou em milhas?** Tudo o mais (calendário, histórico, sugestões) é apoio para essa decisão.

## Tarefas secundárias
- Cadastrar um radar (origem, destino, janela de datas, noites, metas).
- Acompanhar a busca em andamento e entender quando uma fonte falhou.
- Ajustar metas de alerta.

## Voz
Português do Brasil, direto, em linguagem de viajante: "ida", "volta", "milheiro", "taxas", "emitir".
Números sempre formatados no padrão brasileiro (R$ 3.450, 82.000 milhas, 27/05).
Erros dizem o que houve e o que fazer. Nada de jargão técnico na tela (sem "provider", "payload").

## Anti-referências
- Dashboards SaaS genéricos com cards de KPI em gradiente.
- Sites de agência com banners piscando e urgência falsa ("só restam 2 lugares!").
- Tabelas longas sem hierarquia, onde o melhor preço some no meio de 200 linhas.
- Dados inventados: a interface nunca mostra preço que não veio de uma fonte real.
