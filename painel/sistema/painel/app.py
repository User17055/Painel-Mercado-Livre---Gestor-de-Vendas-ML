# -*- coding: utf-8 -*-
"""Entrada do painel (Streamlit). Rodar: Docker (painel/sistema/compose.yaml) ou, sem Docker, painel/sistema/rodar.ps1.

So monta a navegacao e a configuracao da pagina. Nenhuma conta aqui: as paginas chamam o nucleo (painel/nucleo).
Configuracao (pastas, so leitura x atualizar): variaveis de ambiente, ver painel/nucleo/caminhos.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # painel/sistema, para "import painel.nucleo"

import streamlit as st  # noqa: E402

from painel.nucleo import caminhos  # noqa: E402,F401  (le a configuracao e poe a pasta das analises no sys.path)

st.set_page_config(page_title="Vendas ML · TPP e PD", layout="wide")

PAGINAS = [
    st.Page("paginas/visao_geral.py", title="Visão geral", default=True),
    st.Page("paginas/vendas_e_lucro.py", title="Vendas e lucro"),
    st.Page("paginas/downloads.py", title="Downloads"),
]
st.navigation(PAGINAS).run()
