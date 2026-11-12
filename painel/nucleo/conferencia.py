# -*- coding: utf-8 -*-
"""Conferencias de que o controle de vendas bate com a fonte. Cada uma devolve (ok, texto) para mostrar na tela.

sem_comprador      colunas do vendas_api.db so da lista fechada (nenhum dado de comprador no banco)
api_x_excel        liquido por venda pela API = "Total (BRL)" do relatorio de vendas do ML (Excel) no periodo comum (fase 1a)
unidades           unidades por contagem independente (soma dos itens x contagem no banco) (fase 1a)
"""
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from painel.nucleo import caminhos

import ml_pedidos  # noqa: E402  (lista fechada de colunas: a mesma do coletor)


def sem_comprador(banco: Path = caminhos.BANCO_VENDAS) -> tuple[bool, str]:
    """Toda coluna de toda tabela do banco tem de estar no esquema do coletor (nada a mais entra escondido)."""
    banco = Path(banco)
    if not banco.exists():
        return True, "banco de pedidos ainda não existe"
    permitidas = ml_pedidos.colunas_permitidas()
    extras = []
    with closing(sqlite3.connect(f"file:{banco}?mode=ro", uri=True)) as con:
        for (tab,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
            for col in con.execute(f"PRAGMA table_info({tab})"):
                if col[1] not in permitidas.get(tab, set()):
                    extras.append(f"{tab}.{col[1]}")
    return (not extras), ("só colunas da lista fechada" if not extras else "colunas fora da lista: " + ", ".join(extras))


def api_x_excel(conta: str, de: date, ate: date, tolerancia: float = 0.01) -> tuple[bool, str]:
    raise NotImplementedError("fase 1a: comparar venda a venda com o relatorio de vendas do ML (Excel) no periodo comum")


def unidades(conta: str, de: date, ate: date) -> tuple[bool, str]:
    raise NotImplementedError("fase 1a: soma de quantidade dos itens x contagem independente no banco")
