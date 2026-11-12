# -*- coding: utf-8 -*-
"""Pagina 1, Visao geral: por conta, vendas e lucro do mes, acumulado do ano, ultima atualizacao e botao "Atualizar agora".
Fase 1b (tela) e fase 2 (botao). Hoje so mostra o estado do esqueleto."""
import streamlit as st

from painel.nucleo.repositorio import RepositorioPedidos

st.title("Visão geral")
repo = RepositorioPedidos()
if not repo.existe():
    st.info("Ainda sem vendas pela API: o coletor de pedidos (fase 1a) não rodou.")
else:
    for conta in ("TPP", "PD"):
        st.write(f"{conta}: última atualização {repo.ultima_atualizacao(conta) or '—'}")
