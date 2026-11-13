# Telas do painel: especificação (aprovada; base da fase 1b)
O que cada página mostra, de onde vem cada número e como aparece o que está pendente. Requisitos: `PLANO-PAINEL-ML.md`
(seções 1 e 4). Fórmulas: `ARQUITETURA.md`, seção 3. Os números dos desenhos abaixo são **inventados**.

## 1. Regras de todas as telas
- **Tudo vem do núcleo** (`painel/nucleo`): a tela só filtra, ordena e mostra. Nenhuma conta de negócio na página.
- **Sem dado de comprador** em lugar nenhum (não existe no banco).
- **Pendente nunca vira número inventado.** Custo que falta: o lucro aparece como "—" e a linha leva o aviso "custo pendente";
  alíquota que falta: "imposto pendente" e o lucro depois do imposto fica igual ao antes, com aviso. Toda tela que soma lucro
  mostra, junto do total, quantas unidades ficaram fora por falta de custo.
- **Com × sem**: o que depende de resposta pendente aparece lado a lado. Rebate: colunas "lucro sem rebate" e "lucro com
  rebate (x%)" quando `rebate.comparar` = true. Imposto: "lucro antes do imposto" e "lucro depois do imposto" sempre.
- **Formato** (padrão brasileiro): R$ 1.234,56; percentual com 1 casa (12,3%); data dd/mm/aaaa; dia da venda em Brasília
  (o mesmo do relatório do ML). Negativo com sinal "−" **e** em vermelho (a cor nunca é a única pista).
- **Situação**: só vendas válidas entram nos totais; canceladas e devolvidas ficam numa lista à parte (com o efeito delas).
- **Rodapé de toda página**: "Dados até <data e hora da última atualização> (TPP) · <...> (PD)" e as premissas em uma linha
  (rebate usado, origem do imposto de cada conta).

## 2. Filtros (barra lateral, valem para as três páginas)
| Filtro | Opções | Padrão | Fase |
|---|---|---|---|
| Conta | TPP, PD, as duas | as duas | 1b |
| Período | de / até (dia da venda) + atalhos: mês atual, mês anterior, ano | 01/01 do ano até hoje | 1b |
| Produto | lista dos produtos (classificados pelo título) | todos | 2 |
| Tipo de anúncio | Clássico, Premium | os dois | 2 |

Conta e período entram já na 1b porque sem eles a tela não separa "por conta e por mês" (requisito 3). Produto e tipo de
anúncio são o requisito 11 (fase 2). O download sai **com os mesmos filtros** que estão na tela.

## 3. Página 1: Visão geral
```
+--------------------------- Visão geral ---------------------------------------------------+
| Novembro/2026 (mês atual)                                                                  |
|                 |   TPP          |   PD           |   As duas                              |
| Vendas válidas  |   41 (52 un)   |  210 (260 un)  |  251 (312 un)                          |
| Líquido do ML   | R$ 3.100,00    | R$ 15.900,00   | R$ 19.000,00                           |
| Lucro antes imp.| R$ 450,00      | R$ 2.300,00    | R$ 2.750,00                            |
| Lucro depois    | R$ 210,00      | R$ 2.300,00 ⚠  | R$ 2.510,00                            |
| Margem          | 6,8%           | 14,5%          | 13,2%                                  |
| Acumulado no ano| R$ 1.900,00    | R$ 21.000,00   | R$ 22.900,00                           |
|---------------------------------------------------------------------------------------------|
| ⚠ PD: imposto pendente (lucro depois = antes).   ⚠ 3 unidades sem custo (fora do lucro).  |
| Com rebate (x%): lucro antes do imposto R$ 2.950,00 (+R$ 200,00)                          |
+---------------------------------------------------------------------------------------------+
| Dados até 13/11 08:31 (TPP) · 13/11 08:32 (PD)        [Atualizar agora] (fase 2)          |
```
- Mês do quadro: o mês atual; se o filtro de período terminar antes, o último mês do período.
- **Margem** = lucro depois do imposto ÷ líquido do ML (a mesma de `ResumoPeriodo.margem_pct`).
- **Acumulado no ano** = soma do lucro depois do imposto de 01/01 até o fim do mês do quadro.
- Botão "Atualizar agora": só no servidor (`PAINEL_PERMITE_ATUALIZAR=1`) e só na fase 2; antes disso, só a data.

## 4. Página 2: Vendas e lucro (abas)
Todas as tabelas: ordenar clicando no cabeçalho, total na última linha, busca por texto (anúncio, título, pedido).
"Expandir" (requisito 8) = escolher um mês, produto ou anúncio numa tabela e ver as vendas dele na aba Vendas.

| Aba | Uma linha por | Colunas |
|---|---|---|
| Por mês | conta × mês | Conta, Mês, Vendas, Unidades, Bruto, Líquido, Custo, Rebate, Lucro antes, Imposto, Lucro depois, Margem, Acumulado, Un. sem custo |
| Por produto | conta × produto | Conta, Produto, Unidades, Líquido, Custo, Rebate, Lucro antes, Imposto, Lucro depois, Margem, Un. sem custo (do maior lucro ao menor) |
| Por anúncio | conta × anúncio | Conta, Anúncio, Título, Tipo, Produto, Unidades, Líquido, Lucro depois, Margem |
| Vendas | item de pedido | Data, Conta, Pedido, Anúncio, Título, Produto, Tipo, Unid., Bruto, Tarifa, Frete, Líquido, Custo, Rebate, Lucro antes, Imposto, Lucro depois, Avisos |
| Canceladas e devolvidas | item de pedido | as mesmas da aba Vendas + Situação (o líquido delas pode ser negativo: frete e devolução que o vendedor pagou) |

- Com `rebate.comparar` = true, "Lucro antes" vira duas colunas: "sem rebate" e "com rebate (x%)".
- Carrinho: tarifa e frete do pedido rateados pelo bruto entre os itens (o total do pedido continua igual ao do ML).
- Tipo: "Clássico" / "Premium" (o banco guarda `gold_special` / `gold_pro`).

## 5. Página 3: Downloads
Botões, sempre com os filtros da tela:
- **CSV** de cada aba da página 2 (separador `;`, decimal com vírgula, abre certo no Excel).
- **Excel** com as abas: Resumo (= Por mês), Por produto, Vendas, Custos, Rebate, Imposto, Premissas.
  - Custos: produto, custo usado, fonte, aplica rebate (pendentes marcados).
  - Rebate: % usado e o valor por produto no período.
  - Imposto: regra de cada conta e exceção por produto, com a origem (de onde veio a alíquota).
  - Premissas: período e filtros, data e hora dos dados, fórmulas em uma linha cada, lista do que está pendente.
  - Fonte Arial, autor "TI SF", valores (sem fórmula), primeira linha congelada (`exportar.py`).
- Nome do arquivo: `vendas-ml_<contas>_<de>_<ate>.xlsx` (ex.: `vendas-ml_TPP-PD_2026-01-01_2026-11-13.xlsx`).

## 6. Situações especiais
| Situação | O que a tela mostra |
|---|---|
| Banco de pedidos não existe | aviso "Ainda sem vendas pela API" e como gravar; nenhuma tabela |
| Período sem vendas | tabelas vazias com "Nenhuma venda no período" |
| Sem os arquivos de parâmetros | vendas e líquido normais; custo e imposto pendentes em tudo (aviso no topo) |
| Dados com mais de 1 dia | rodapé em destaque: "dados de <data>; atualize" |

## 7. Gráficos (fase 2, requisito 12)
Um eixo por gráfico (nunca dois eixos de escalas diferentes):
- lucro depois do imposto por mês (barras, uma cor por conta);
- acumulado no ano (linha por conta);
- lucro por produto (barras horizontais, do maior ao menor).

## 8. O que muda no código para isso (fase 1b)
- `CalculadoraLucro.resultado`: escrever (fórmulas da ARQUITETURA, seção 3), com rebate com × sem.
- `ResultadoItem`: ganhar `tipo_anuncio` (filtro e coluna) e `lucro_com_rebate` (coluna de comparação).
- `resumo.por_anuncio` (aba Por anúncio) e o montador das abas Custos, Rebate, Imposto e Premissas do Excel.
- Leitura do banco com cache por data da última atualização (a tela não relê tudo a cada clique).
- Teste: total da tela = total do núcleo = total do relatório do ML no período conferido.

## 9. Decisões (aprovadas em 13/11/2026)
1. Filtros de conta e período já na 1b; produto e tipo de anúncio na fase 2.
2. Coluna "As duas" na Visão geral (soma das contas) e opção "as duas" no filtro.
3. Margem sobre o líquido do ML.
4. Número do pedido na aba Vendas (serve para achar a venda no ML).
5. Quem vê o quê: todos veem tudo (as duas contas e os custos).
