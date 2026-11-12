# -*- coding: utf-8 -*-
"""CalculadoraLucro: Pedido -> lista de ResultadoItem (uma linha por item). Formulas: painel/docs/ARQUITETURA.md, secao 3.

Reaproveita ml_margem (produto pelo titulo, kit, brinde, custo da mercadoria) e ml_param (imposto por conta/produto) por meio de
RepositorioParametros: a mesma regra dos relatorios .md.
"""
from painel.nucleo.modelos import ItemPedido, Pedido, ResultadoItem
from painel.nucleo.repositorio import RepositorioParametros

import ml_margem as M  # noqa: E402


def ratear(total: float, pesos: list[float]) -> list[float]:
    """Reparte um valor (ex.: frete do pedido) proporcional aos pesos (bruto de cada item); o ultimo absorve o centavo."""
    s = sum(pesos)
    if not pesos:
        return []
    if not s:
        partes = [round(total / len(pesos), 2)] * len(pesos)
    else:
        partes = [round(total * p / s, 2) for p in pesos]
    partes[-1] = round(total - sum(partes[:-1]), 2)
    return partes


class CalculadoraLucro:
    def __init__(self, parametros: RepositorioParametros):
        self.par = parametros

    def produto(self, item: ItemPedido) -> str:
        return M.classificar(item.titulo) or ""

    def resultado(self, pedido: Pedido) -> list[ResultadoItem]:
        """Lucro antes e depois do imposto de cada item do pedido.
        Frete do vendedor rateado pelo bruto dos itens; custo pendente -> lucro None + aviso (nunca inventar custo)."""
        raise NotImplementedError("fase 1b: aplicar as formulas da ARQUITETURA.md secao 3 e conferir contra o Excel")
