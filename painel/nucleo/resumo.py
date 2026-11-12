# -*- coding: utf-8 -*-
"""Agregacoes para a tela e para o Excel: por conta x mes (com acumulado) e por conta x produto.

So vendas validas entram nos totais; canceladas/devolvidas ficam numa lista a parte (separadas()).
Item sem custo: entra em unidades, bruto e liquido, fica fora do custo e do lucro e soma em sem_custo_un (aviso na tela).
"""
from collections import defaultdict

from painel.nucleo.modelos import ResultadoItem, ResumoPeriodo, Situacao


def _somar(r: ResumoPeriodo, x: ResultadoItem) -> None:
    r.unidades += x.unidades
    r.bruto = round(r.bruto + x.bruto, 2)
    r.liquido = round(r.liquido + x.liquido, 2)
    if x.custo is None:
        r.sem_custo_un += x.unidades
        return
    r.custo = round(r.custo + x.custo, 2)
    r.rebate = round(r.rebate + x.rebate, 2)
    r.imposto = round(r.imposto + x.imposto, 2)
    r.lucro_antes_imposto = round(r.lucro_antes_imposto + (x.lucro_antes_imposto or 0), 2)
    r.lucro_depois_imposto = round(r.lucro_depois_imposto + (x.lucro_depois_imposto or 0), 2)


def validas(linhas: list[ResultadoItem]) -> list[ResultadoItem]:
    return [x for x in linhas if x.situacao == Situacao.VALIDA]


def separadas(linhas: list[ResultadoItem]) -> list[ResultadoItem]:
    return [x for x in linhas if x.situacao != Situacao.VALIDA]


def por_mes(linhas: list[ResultadoItem]) -> list[ResumoPeriodo]:
    """Conta x AAAA-MM em ordem, com acumulado do lucro depois do imposto dentro de cada conta."""
    g: dict[tuple[str, str], ResumoPeriodo] = {}
    for x in validas(linhas):
        k = (x.conta, x.data.strftime("%Y-%m"))
        _somar(g.setdefault(k, ResumoPeriodo(*k)), x)
    acum: dict[str, float] = defaultdict(float)
    out = []
    for k in sorted(g):
        r = g[k]
        acum[r.conta] = round(acum[r.conta] + r.lucro_depois_imposto, 2)
        r.acumulado = acum[r.conta]
        out.append(r)
    return out


def por_produto(linhas: list[ResultadoItem]) -> list[ResumoPeriodo]:
    """Conta x produto (periodo = nome do produto; '(sem produto)' quando o titulo nao classifica), do maior lucro ao menor."""
    g: dict[tuple[str, str], ResumoPeriodo] = {}
    for x in validas(linhas):
        k = (x.conta, x.produto or "(sem produto)")
        _somar(g.setdefault(k, ResumoPeriodo(*k)), x)
    return sorted(g.values(), key=lambda r: (r.conta, -r.lucro_depois_imposto))
