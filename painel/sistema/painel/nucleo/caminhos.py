# -*- coding: utf-8 -*-
"""Configuracao do painel num lugar so: caminhos e opcoes vem de VARIAVEIS DE AMBIENTE, com padrao relativo ao projeto.
Nenhum caminho de um computador especifico: roda igual em qualquer PC (Windows, Mac, Linux) e no Docker.

| Variavel                  | Para que                                              | Padrao (sem a variavel)                      |
|---------------------------|-------------------------------------------------------|----------------------------------------------|
| ML_ANALISE_DIR            | codigo das analises (ml_margem, ml_param, ml_pedidos) | <projeto>/analise                            |
| ML_DADOS_DIR              | coletas, monitor, vendas_api.db, travas              | <projeto>/relatorios-ml/api                  |
| ML_CONFIG_DIR             | ml_parametros.json e custos_produtos.csv              | <projeto>/analise                            |
| ML_API_DIR                | tokens do ML (so quem atualiza precisa)               | <pasta pessoal de quem roda>/.ml-api         |
| ML_CLIENT_ID / _SECRET    | app do ML (so quem atualiza precisa)                  | (nenhum: sem eles, o botao fica desligado)   |
| PAINEL_PERMITE_ATUALIZAR  | 1 = mostra o botao "Atualizar agora"; 0 = so leitura  | 0                                            |
As mesmas variaveis valem para os modulos de analise\\ que o painel usa (ml_param, ml_margem, ml_pedidos).
<projeto> = a pasta que contem analise\\ e painel\\ (descoberta a partir deste arquivo).
Unico modulo do painel que mexe no sys.path: todo outro modulo do nucleo importa daqui antes de importar ml_*.
"""
import os
import sys
from pathlib import Path


def _dir(variavel: str, padrao: Path) -> Path:
    v = os.environ.get(variavel, "").strip()
    return Path(v).expanduser().resolve() if v else padrao


SISTEMA = Path(__file__).resolve().parents[2]        # painel/sistema
PROJETO = SISTEMA.parents[1]                         # raiz do projeto (no Docker nao existe: tudo vem das variaveis)

ANALISE = _dir("ML_ANALISE_DIR", PROJETO / "analise")
DADOS = _dir("ML_DADOS_DIR", PROJETO / "relatorios-ml" / "api")
CONFIG = _dir("ML_CONFIG_DIR", PROJETO / "analise")

BANCO_VENDAS = DADOS / "vendas_api.db"               # criado por ml_pedidos.py
TRAVA_ATUALIZACAO = DADOS / "painel_atualizando.trava"
REGISTRO_ATUALIZACAO = DADOS / "painel_ultima_atualizacao.json"

PERMITE_ATUALIZAR = os.environ.get("PAINEL_PERMITE_ATUALIZAR", "0").strip() == "1"

if str(ANALISE) not in sys.path:
    sys.path.insert(0, str(ANALISE))
