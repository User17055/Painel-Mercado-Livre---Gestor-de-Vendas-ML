# -*- coding: utf-8 -*-
"""Pagina 1, Visao geral (docs/TELAS.md, secao 3): o mes do quadro por conta e "As duas", acumulado do ano, avisos e rodape.
Botao "Atualizar agora": fase 2."""
from datetime import date

import pandas as pd
import streamlit as st

from painel import tela
from painel.nucleo import formato, resumo

st.title("Visão geral")
contas, de, ate = tela.filtros()
repo = tela.exigir_banco()
par = tela.parametros()

# mes do quadro: o mes atual; se o periodo terminar antes, o ultimo mes do periodo
fim = min(ate, date.today())
ini_mes = fim.replace(day=1)
L_mes = tela.linhas(contas, max(ini_mes, de), fim)
L_ano = tela.linhas(contas, date(fim.year, 1, 1), fim)
hoje = date.today()
st.subheader(formato.mes(fim.strftime("%Y-%m")) + (" (mês atual)" if (fim.year, fim.month) == (hoje.year, hoje.month) else ""))
if de > ini_mes:
    st.caption(f"Do mês, só o que está no período escolhido: {formato.data(de)} a {formato.data(fim)}.")

colunas = [(c, [x for x in L_mes if x.conta == c], [x for x in L_ano if x.conta == c]) for c in contas]
if len(contas) > 1:
    colunas.append(("As duas", L_mes, L_ano))

quadro = {"Vendas válidas": [], "Líquido do ML": [], "Lucro antes do imposto": [], "Lucro depois do imposto": [], "Margem": [],
          "Acumulado no ano": []}
for nome, lm, la in colunas:
    t, ta = resumo.total(lm), resumo.total(la)
    pend = any(par.regra_imposto(c).pendente() for c in (contas if nome == "As duas" else [nome]))
    quadro["Vendas válidas"].append(f"{formato.inteiro(t.vendas)} ({formato.inteiro(t.unidades)} un)")
    quadro["Líquido do ML"].append(formato.brl(t.liquido))
    quadro["Lucro antes do imposto"].append(formato.brl(t.lucro_antes_imposto))
    quadro["Lucro depois do imposto"].append(formato.brl(t.lucro_depois_imposto) + (" ⚠" if pend else ""))
    quadro["Margem"].append(formato.pct(t.margem_pct()))
    quadro["Acumulado no ano"].append(formato.brl(ta.lucro_depois_imposto))

df = pd.DataFrame(quadro, index=[n for n, _, _ in colunas]).T
st.dataframe(df.style.map(lambda v: "color: #c62828" if formato.negativo(v) else ""), use_container_width=True)

if not L_mes:
    st.info("Nenhuma venda no mês do quadro.")
for a in tela.avisos_pendencia(L_mes, par, contas):
    st.warning(a)
cmp = par.rebate_comparacao()
t = resumo.total(L_mes)
if cmp is not None and t.lucro_com_rebate is not None:
    dif = round(t.lucro_com_rebate - t.lucro_antes_imposto, 2)
    st.caption(tela.md(f"Com rebate ({cmp:g}%): lucro antes do imposto {formato.brl(t.lucro_com_rebate)} "
                       f"({'+' if dif >= 0 else ''}{formato.brl(dif)})."))
st.caption("Margem = lucro depois do imposto ÷ líquido do ML (só itens com custo). Acumulado = lucro depois do imposto de "
           f"01/01 a {formato.data(fim)}. Botão \"Atualizar agora\": fase 2.")
tela.rodape(repo, par, contas)
