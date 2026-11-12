# Plano: painel de vendas e lucro do ML (TPP + PD)
Escopo desta etapa: requisitos A (obrigatórios) e B (desejáveis) da seção 1. Camadas, classes, fórmulas e modos de uso em
`ARQUITETURA.md`; estado de cada peça e como rodar em `LEIA-ME.md` (nesta pasta).

## 1. Objetivo e requisitos
Tarefa original (06/11): "uma planilha **ou sistema** com controle fiel de vendas on-line". Nota: planilha de vendas com
preço de recebimento do ML − preço de custo + rebate; acumulado de lucro ou prejuízo; Bravecto e outros produtos.
Fazer como sistema com a planilha dentro **não aumenta o escopo da tarefa**: o cálculo é o mesmo; muda só a forma de entregar.

**A. Obrigatórios (o que a tarefa pede)**
1. Todas as vendas on-line do ML, das duas contas (TPP e PD), todos os produtos (Bravecto e os outros).
2. Por venda: valor recebido do ML (líquido, "Total (BRL)"), custo × unidades, rebate → **lucro ou prejuízo**.
3. **Acumulado**: por mês e no total, por conta e por produto.
4. **"Fiel"** = bate com o ML: total do ML = total do sistema; carrinho e kit repartidos certo; canceladas/devolvidas separadas.
5. Custo de cada produto com fonte (Omie "Preço Unitário de Venda" ou o custo informado pelo e-commerce; nunca o CMC); o que faltar aparece como faltando, sem chute.
6. Rebate como parâmetro (com × sem enquanto não vier por escrito).
7. Atualizável: as vendas vêm **pela API** (pedidos), sem usar dado de comprador (seção 5).
8. **Tela interativa** (abrir, ordenar, expandir por conta/mês/produto/venda).
9. **Download em CSV e Excel** (Excel com abas: Resumo, Por produto, Vendas, Custos, Rebate, Imposto, Premissas).
10. **Imposto parametrizável para as duas empresas** (seção 7, item 3): o lucro aparece antes do imposto (fórmula da tarefa original) e depois.

**B. Desejáveis**
11. Filtros (conta, período, produto, tipo de anúncio).
12. Gráficos (ex.: lucro por mês, acumulado, por produto).
13. **Se for barato**: atualizar os dados quando o usuário pedir (botão).

## 2. Regras
- API do ML **só leitura** (só GET, por uma função única). O painel não muda anúncio, preço nem venda.
- **Sem dado de comprador** em tela, arquivo ou download (só agregados por venda, sem nome/CPF/endereço).
- O que depende de resposta pendente (rebate, alíquota da PD, custos que faltam) aparece como parâmetro, com × sem.
- Credenciais do ML nunca no código nem no repositório (variável de ambiente / cofre do servidor).
- Custo do produto = "Preço Unitário de Venda" do Omie ou o custo informado pelo e-commerce; **nunca o CMC do Omie**.

## 3. Arquitetura
```
API do ML (só GET) --> coletor de pedidos (lista fechada de campos) --> vendas_api.db
                                                                           |
                       custos e parâmetros (fora do git) -----------> núcleo (lucro, resumo, exportação)
                                                                           |
                                                                   telas + downloads CSV/Excel
```
- Tecnologia: Streamlit (Python), pandas, Plotly (gráficos), openpyxl (Excel).
- Roda em Docker (Python 3.12 dentro da imagem) em qualquer PC, ou sem Docker num venv com Python 3.12. Pastas e modo por
  variável de ambiente (ARQUITETURA, decisões D7 a D9).
- Alternativas descartadas: Power BI / Looker Studio (não leem a API do ML direto; atualizar exige outro conector pago ou
  manual); HTML estático (barato, mas sem atualização na hora).

## 4. Páginas
| # | Página | Mostra | Fonte |
|---|---|---|---|
| 1 | Visão geral | por conta: vendas e lucro do mês, margem, última atualização | vendas + custos + parâmetros |
| 2 | Vendas e lucro | por mês e acumulado; por produto; por anúncio; linha a linha (sem comprador); com × sem rebate, com × sem imposto | vendas + custos + parâmetros |
| 3 | Downloads | cada tabela em CSV e um Excel com abas (Resumo, Por produto, Vendas, Custos, Rebate, Imposto, Premissas) | as mesmas |

Filtros (requisito 11): conta (TPP, PD, as duas), período, produto, tipo de anúncio (Clássico/Premium).

## 5. Vendas pela API
Fonte: documentação do ML (páginas gerenciamento-de-vendas, gerenciamento-de-envios, provisoes). Nada testado ainda.

| O quê | Endpoint (só GET) | Campos que entram (lista fechada) |
|---|---|---|
| Pedidos | `/orders/search?seller=` + filtro de data (`order.date_closed.from/to`), 50 por página | id, data, status, tags, pack_id, por item: id do anúncio, variação, SKU, quantidade, `unit_price` (já com desconto), `sale_fee`, tipo de anúncio, cupom, cancelamento |
| Frete do vendedor | `/shipments/{id}/costs` (cabeçalho `x-format-new: true`) | `senders[].cost` (o que o vendedor pagou) e descontos do ML no frete |
| Cobrança por venda | `/billing/integration/group/ML/order/details?order_ids=` (até 60 por chamada) | tarifa bruta/líquida, descontos, frete cobrado, data de liberação do dinheiro |

- **Líquido por venda** = preço × unidades − tarifa − frete do vendedor (fórmula da própria doc), conferido contra a cobrança.
- **Comprador:** o pedido traz `buyer` (id e apelido) e a cobrança traz `payer_nickname`. O coletor descarta esses campos na
  hora de ler (lista fechada do que entra); nada de comprador é gravado, mostrado ou baixado. Os testes conferem isso.
- **Limites da API a tratar no teste:**
  - pedidos só dos últimos 12 meses (o período padrão, 2026, cabe);
  - a busca do vendedor esconde pedidos cancelados: canceladas/devolvidas podem precisar de outra consulta (status) ou da cobrança;
  - a doc não informa limite numérico de chamadas (só "por app e por endpoint"; em 429, esperar e repetir).
- **Carga inicial** (uma vez, devagar): PD ~4 mil pedidos no ano → ~80 páginas de busca + ~70 de cobrança + 1 de frete por
  envio (~4 mil); TPP bem menos. Depois, incremental: só os pedidos desde a última atualização (poucas dezenas de chamadas).
- **Prova de que é "fiel"** (antes de valer): para 01/09 a 30/10/2026, o líquido calculado pela API tem que bater com o
  "Total (BRL)" do relatório de vendas do ML (Excel) do mesmo período, venda por venda. Diferença vira explicação escrita ou correção.
- Guardado em SQLite (`vendas_api.db`), só com os campos da lista fechada.

## 5b. Atualização dos dados (requisito 13)
Botão "Atualizar agora": busca só as vendas novas desde a última atualização (seção 5), em poucas chamadas.

Cuidados para o botão não dar problema:
- trava (uma atualização por vez) e intervalo mínimo (ex.: 15 min), mostrando "atualizado às HH:MM";
- o token do ML renova com chave de uso único: duas atualizações ao mesmo tempo podem derrubar o acesso (a trava resolve).

Custo da API do ML: zero (só limite de chamadas, folgado para esse uso).

## 6. Onde roda e quem acessa
**Decidido (11/11): um servidor só, todos acessam pela web (navegador)**, na rede da empresa. Falta decidir qual máquina
(detalhes em `ARQUITETURA.md`, seção 6).

| Opção | Custo | Prós | Contras |
|---|---|---|---|
| A. PC da empresa ligado, acesso pela rede interna | R$ 0 | simples, dados ficam na empresa | só funciona com o PC ligado e dentro da rede |
| B. Servidor pequeno na nuvem (VM) | ~US$ 5–12/mês | sempre no ar | configurar, manter e proteger |
| C. Streamlit Community Cloud | R$ 0 | pronto em minutos | credenciais em servidor de terceiros: não recomendado para dado da empresa |

Proposta: A; B só se o PC não puder ficar ligado.

## 7. Decisões
1. **Vendas pela API ou pelo Excel?** Decidido (11/11): pela API, sem usar dado de comprador (seção 5).
2. **Rebate:** é o da MSD (por unidade ou %) e não os bônus de campanha do ML (esses já estão no líquido).
3. **Lucro e imposto (decidido 11/11):** lucro antes do imposto = líquido do ML − custo × unidades + rebate (fórmula da tarefa
   original); lucro depois do imposto = isso − imposto líquido (débito sobre o preço − crédito sobre o custo). Imposto
   **parametrizável por empresa e por produto** (bloco `imposto` de `ml_parametros.json`):
   - TPP (Lucro Real), já preenchida com o que a empresa informou em 10/11: Franpet débito 27,25% / crédito 27,25%
     (PIS/COFINS 9,25% + ICMS 18%); Bravecto (monofásico) débito 18% / crédito 18% (só ICMS). Ainda sem DIFAL, sem
     confirmação do crédito de PIS/COFINS do Franpet e sem crédito sobre a tarifa do ML.
   - PD (Simples): em branco até o contador responder; enquanto isso a tela mostra "imposto pendente" e o lucro depois do
     imposto fica igual ao antes, com aviso. Crédito não se aplica ao Simples.
   - O painel mostra de onde veio cada alíquota. Canceladas/devolvidas separadas.
4. **Período padrão:** 2026 inteiro, mês a mês e acumulado.
5. **Quem acessa:** a equipe, pelo navegador. Falta: o que cada um vê (todos tudo?).
6. **Onde roda:** servidor único, acesso web na rede da empresa (decidido 11/11). Falta: qual máquina (seção 6).

## 8. Fases (cada fase entrega algo usável)
| Fase | Entrega | Depende de |
|---|---|---|
| 0 | decisões da seção 7 que faltam | equipe |
| 1a | coletor de pedidos pela API (seção 5) + conferência contra o relatório do ML de 01/09–30/10 | decisão 1 (feita) |
| 1b (= tarefa original) | requisitos A (1 a 10): páginas 1, 2 e 3, tela interativa, downloads CSV/Excel, imposto por parâmetro | 1a |
| 2 | requisitos B (11 a 13): filtros, gráficos, botão "Atualizar agora" com trava e intervalo | 1b |

## 9. Conferências (toda vez que os dados mudam)
- líquido de cada venda pela API = "Total (BRL)" do relatório do ML; total do ML = total no painel;
- unidades por contagem independente;
- download em Excel: fonte Arial, autor "TI SF" (`exportar.AUTOR`), zero erro de fórmula;
- testes sem falha.
