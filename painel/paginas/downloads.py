# -*- coding: utf-8 -*-
"""Pagina 3, Downloads (docs/TELAS.md, secao 5): cada tabela em CSV e o Excel com todas as abas, sempre com os filtros da tela."""
import streamlit as st

from painel import tela
from painel.nucleo import exportar, formato, resumo

st.title("Downloads")
contas, de, ate = tela.filtros()
repo = tela.exigir_banco()
par = tela.parametros()
L = tela.linhas(contas, de, ate)
st.write(f"Contas: **{', '.join(contas)}** · período **{formato.data(de)} a {formato.data(ate)}** "
         f"({formato.inteiro(len(resumo.validas(L)))} itens válidos, {formato.inteiro(len(resumo.separadas(L)))} "
         "cancelados ou devolvidos).")

atualizado = {c: repo.ultima_atualizacao(c) for c in contas}
abas = resumo.abas_excel(L, par, contas, de, ate, atualizado)
nome = resumo.nome_arquivo(contas, de, ate)
st.download_button("Baixar Excel (todas as abas)", exportar.para_excel(abas), file_name=nome,
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
st.caption("Abas: " + ", ".join(abas) + ". Fonte Arial, valores sem fórmula, primeira linha congelada.")

st.subheader("CSV de cada tabela")
st.caption("Separador ponto e vírgula e decimal com vírgula: abre certo no Excel.")
base = nome.removesuffix(".xlsx")
for aba, linhas_ in abas.items():
    st.download_button(f"{aba} (CSV)", exportar.para_csv(linhas_), file_name=f"{base}_{aba.lower().replace(' ', '-')}.csv",
                       mime="text/csv", key=f"csv_{aba}", disabled=not linhas_)

tela.rodape(repo, par, contas)
