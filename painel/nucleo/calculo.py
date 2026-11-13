# -*- coding: utf-8 -*-
"""CalculadoraLucro: Pedido -> lista de ResultadoItem (uma linha por item). Formulas: docs/ARQUITETURA.md, secao 3.

Reaproveita ml_margem (produto pelo titulo, kit, brinde, custo da mercadoria) e ml_param (imposto por conta/produto) por meio de
RepositorioParametros.
"""
from painel.nucleo.modelos import ItemPedido, Pedido, ResultadoItem, Situacao, nome_tipo
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

    def _custo(self, produto: str, item: ItemPedido, rebate_pct: float) -> float | None:
        """Custo da mercadoria do item (regra de ml_margem: kit, brinde e rebate so onde aplica_rebate=sim)."""
        c = M.custo_mercadoria(produto, item.titulo, self.par.custos_brutos(), rebate_pct)
        return None if c is None else round(c * item.quantidade, 2)

    def resultado(self, pedido: Pedido) -> list[ResultadoItem]:
        """Lucro antes e depois do imposto de cada item do pedido (docs/ARQUITETURA.md, secao 3).

        Receita, tarifa e frete do pedido sao rateados pelo bruto dos itens: a soma dos liquidos dos itens = Pedido.liquido().
        Custo pendente -> custo e lucro None + aviso (nunca inventar custo). Aliquota pendente -> imposto 0 + aviso.
        Cancelada/devolvida: o produto volta ao estoque, entao sem custo de mercadoria; o lucro dela e o proprio liquido
        (o que o ML cobrou ou devolveu). Ela fica fora dos totais (resumo.separadas)."""
        itens = pedido.itens
        if not itens:
            return []
        pesos = [i.bruto() for i in itens]
        receitas = ratear(pedido.receita(), pesos)
        tarifas = ratear(pedido.tarifa(), pesos)
        fretes = ratear(pedido.frete(), pesos)
        situacao = pedido.situacao()
        pct = self.par.rebate_pct()
        pct_cmp = self.par.rebate_comparacao()
        saida = []
        for item, rec, tar, fre in zip(itens, receitas, tarifas, fretes):
            prod = self.produto(item)
            liq = round(rec - tar - fre, 2)
            avisos: list[str] = []
            base = dict(conta=pedido.conta, data=pedido.fechado_em, pedido_id=pedido.pedido_id, anuncio_id=item.anuncio_id,
                        titulo=item.titulo, produto=prod, tipo_anuncio=nome_tipo(item.tipo_anuncio), unidades=item.quantidade,
                        bruto=item.bruto(), tarifa=tar, frete=fre, liquido=liq, situacao=situacao, avisos=avisos)
            if situacao != Situacao.VALIDA:
                avisos.append("sem custo de mercadoria (o produto volta ao estoque)")
                saida.append(ResultadoItem(**base, custo=0.0, rebate=0.0, lucro_antes_imposto=liq,
                                           lucro_com_rebate=liq if pct_cmp is not None else None, imposto=0.0,
                                           lucro_depois_imposto=liq))
                continue
            custo = self._custo(prod, item, 0.0)
            if custo is None:
                avisos.append("custo pendente" if prod else "produto não identificado pelo título")
                saida.append(ResultadoItem(**base, custo=None, rebate=0.0, lucro_antes_imposto=None, lucro_com_rebate=None,
                                           imposto=0.0, lucro_depois_imposto=None))
                continue
            custo_ef = self._custo(prod, item, pct)
            rebate = round(custo - custo_ef, 2)
            antes = round(liq - custo + rebate, 2)
            com_rebate = None
            if pct_cmp is not None:
                com_rebate = round(liq - custo + (custo - self._custo(prod, item, pct_cmp)), 2)
            regra = self.par.regra_imposto(pedido.conta, prod)
            if regra.pendente():
                avisos.append("imposto pendente")
                imposto = 0.0
            else:
                # debito sobre o preco; credito sobre o custo da mercadoria comprada (com rebate, se aplicado). Simples: credito 0
                imposto = round(item.bruto() * regra.debito_pct / 100 - custo_ef * regra.credito_pct / 100, 2)
            saida.append(ResultadoItem(**base, custo=custo, rebate=rebate, lucro_antes_imposto=antes,
                                       lucro_com_rebate=com_rebate, imposto=imposto,
                                       lucro_depois_imposto=round(antes - imposto, 2)))
        return saida

    def resultados(self, pedidos: list[Pedido]) -> list[ResultadoItem]:
        return [r for p in pedidos for r in self.resultado(p)]
