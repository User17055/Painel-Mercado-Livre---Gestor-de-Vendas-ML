# -*- coding: utf-8 -*-
"""Coletor de pedidos e regras do liquido, com respostas inventadas (nao chama a API).

As regras vieram da conferencia contra o relatorio de vendas do ML (ver docs/LEIA-ME.md): cada teste aqui e um caso real
reduzido ao essencial, com numeros inventados.
"""
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from painel.nucleo import caminhos  # noqa: F401  (analise\ no sys.path)
from painel.nucleo.modelos import Cobranca, Envio, ItemPedido, Pedido, Situacao
from painel.nucleo.repositorio import RepositorioPedidos

import ml_pedidos


class ColetaFalsa:
    """Responde como a API, a partir de um dicionario path -> resposta. Nunca usa a rede."""

    def __init__(self, respostas):
        self.conta, self.uid, self.chamadas, self.erros = "TPP", 1, 0, []
        self.respostas = respostas

    def get(self, path, params=None, ref="", headers=None):
        self.chamadas += 1
        r = self.respostas.get(path)
        return r(params) if callable(r) else r


def pedido_api(pid, fechado, preco=100.0, qtd=1, tarifa=10.0, status="paid", pack=None, envio=500, pagamento=None):
    return {"id": pid, "pack_id": pack, "date_created": fechado, "date_closed": fechado, "status": status, "tags": ["paid"],
            "total_amount": preco * qtd, "coupon": {"amount": 0}, "shipping": {"id": envio},
            "buyer": {"id": 9, "nickname": "COMPRADOR_TESTE"},
            "payments": [pagamento or {"status": "approved", "status_detail": "accredited", "transaction_amount_refunded": 0,
                                        "payer_id": 9}],
            "order_items": [{"item": {"id": "MLB1", "title": "Produto teste"}, "quantity": qtd, "unit_price": preco,
                             "sale_fee": tarifa, "listing_type_id": "gold_special"}]}


def cobranca_api(pid, detalhes):
    return {"order_id": pid, "details": [
        {"charge_info": {"detail_id": did, "detail_type": tipo, "detail_sub_type": sub, "detail_amount": valor,
                         "transaction_detail": "x", "status": status},
         "marketplace_info": {"marketplace": mercado},
         "shipping_info": {"shipping_id": "500", "receiver_shipping_cost": pago},
         "sales_info": [{"order_id": pid, "payer_nickname": "COMPRADOR_TESTE"}]}
        for did, tipo, mercado, sub, valor, pago, status in detalhes]}


class TestColetor(unittest.TestCase):
    def test_dia_de_brasilia(self):
        self.assertEqual(ml_pedidos.dia_local("2026-10-31T23:30:00.000-04:00"), "2026-11-01")   # 00:30 em Brasilia
        self.assertEqual(ml_pedidos.dia_local("2026-10-31T22:30:00.000-04:00"), "2026-10-31")

    def test_busca_corta_pelo_dia_de_brasilia(self):
        resp = {"results": [pedido_api(1, "2026-10-31T22:30:00.000-04:00"), pedido_api(2, "2026-10-31T23:30:00.000-04:00")],
                "paging": {"total": 2}}
        c = ColetaFalsa({"/orders/search": resp})
        ped, _ = ml_pedidos.buscar_pedidos(c, date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual([p["pedido_id"] for p in ped], [1])
        ped, _ = ml_pedidos.buscar_pedidos(ColetaFalsa({"/orders/search": resp}), date(2026, 11, 1), date(2026, 11, 30))
        self.assertEqual([p["pedido_id"] for p in ped], [2])

    def test_pagamento_so_lista_fechada(self):
        linha, _ = ml_pedidos.filtrar_pedido("TPP", pedido_api(1, "2026-11-01T10:00:00.000-04:00", pagamento={
            "status": "refunded", "status_detail": "bpp_covered", "transaction_amount_refunded": 50.0, "payer_id": 9}))
        self.assertEqual((linha["pagamento_status"], linha["pagamento_detalhe"], linha["reembolsado"]),
                         ("refunded", "bpp_covered", 50.0))
        self.assertNotIn("COMPRADOR_TESTE", repr(linha))
        self.assertNotIn(9, [v for k, v in linha.items() if k != "pedido_id"])

    def test_cobrancas(self):
        resp = {"results": [cobranca_api(1, [
            ("11", "CHARGE", "CORE", "CVVML", 8.0, 7.99, None),          # o numero do comprador aqui e o do carrinho: ignorado
            ("12", "CHARGE", "SHIPPING", "CFFE", 16.0, 9.0, None),       # frete cheio; comprador pagou 9
            ("13", "CHARGE", "MP", "CFONPN", 5.0, None, None),           # repasse do parcelamento
            ("14", "BONUS", "CORE", "BVVML", 1.0, 0, None)])]}           # estorno
        linhas = ml_pedidos.buscar_cobrancas(ColetaFalsa({"/billing/integration/group/ML/order/details": resp}), [1])
        self.assertEqual([(x["tipo"], x["valor"]) for x in linhas],
                         [("CHARGE/CORE/CVVML", 8.0), ("CHARGE/SHIPPING/CFFE", 16.0), (ml_pedidos.RECEITA_ENVIO, -9.0),
                          ("CHARGE/MP/CFONPN", 5.0), ("BONUS/CORE/BVVML", -1.0)])
        self.assertNotIn("COMPRADOR_TESTE", repr(linhas))
        self.assertEqual({x["cobranca_id"] for x in linhas}, {"11", "12", "12:comprador", "13", "14"})

    def test_frete_estornado_nao_tem_receita_do_comprador(self):
        resp = {"results": [cobranca_api(1, [("12", "CHARGE", "SHIPPING", "CFFE", 16.0, 9.0, "BONUS_ON_BILL")])]}
        linhas = ml_pedidos.buscar_cobrancas(ColetaFalsa({"/billing/integration/group/ML/order/details": resp}), [1])
        self.assertEqual([x["tipo"] for x in linhas], ["CHARGE/SHIPPING/CFFE"])

    def test_leitura_com_erro_nao_e_gravada(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                ml_pedidos.gravar(Path(d) / "v.db", {"completa": False, "erros": [["x"]]})
            self.assertFalse((Path(d) / "v.db").exists())


def pedido(status="paid", cobrancas=(), envio=None, reembolsado=0.0, detalhe="accredited", tags=("paid",), preco=100.0):
    return Pedido("TPP", "1", datetime(2026, 11, 1), status, [ItemPedido("MLB1", "t", 1, preco, 10.0)], tags=tags,
                  envio=envio, cobrancas=list(cobrancas), reembolsado=reembolsado, pagamento_detalhe=detalhe)


class TestLiquido(unittest.TestCase):
    def test_venda_normal(self):
        p = pedido(cobrancas=[Cobranca("CHARGE/CORE/CVVML", 10.0), Cobranca("CHARGE/SHIPPING/CFFE", 16.0),
                              Cobranca(ml_pedidos.RECEITA_ENVIO, -9.0), Cobranca("CHARGE/MP/CFONPN", 5.0)])
        self.assertEqual((p.tarifa(), p.frete(), p.liquido()), (10.0, 7.0, 83.0))   # parcelamento (MP) nao e custo

    def test_sem_cobranca_ainda(self):
        p = pedido(envio=Envio("500", 7.0))
        self.assertEqual((p.tarifa(), p.frete(), p.liquido()), (10.0, 7.0, 83.0))

    def test_cancelada_e_estornada_da_zero(self):
        p = pedido("cancelled", [Cobranca("CHARGE/CORE/CVVML", 10.0), Cobranca("BONUS/CORE/BVVML", -10.0)],
                   envio=Envio("500", 7.0), reembolsado=100.0, detalhe="bpp_refunded", tags=("not_delivered",))
        self.assertEqual((p.liquido(), p.situacao()), (0.0, Situacao.CANCELADA))

    def test_reembolso_com_frete_do_comprador_desconta_so_o_produto(self):
        p = pedido("cancelled", reembolsado=109.0, detalhe="bpp_refunded")
        self.assertEqual(p.receita(), 0.0)

    def test_coberta_pelo_ml_e_venda_valida(self):
        p = pedido("cancelled", [Cobranca("CHARGE/CORE/CVVML", 10.0), Cobranca("CHARGE/SHIPPING/CFFE", 7.0)],
                   reembolsado=100.0, detalhe="bpp_covered")
        self.assertEqual((p.liquido(), p.situacao()), (83.0, Situacao.VALIDA))

    def test_devolvida(self):
        p = pedido("cancelled", [Cobranca("CHARGE/SHIPPING/CFFE", 7.0)], reembolsado=100.0, detalhe="bpp_refunded",
                   tags=("delivered",))
        self.assertEqual((p.liquido(), p.situacao()), (-7.0, Situacao.DEVOLVIDA))


class TestCarrinho(unittest.TestCase):
    def test_frete_do_carrinho_conta_uma_vez(self):
        """Dois pedidos no mesmo pacote e envio: a mesma cobranca de frete vem nos dois; um deles nao tem cobranca."""
        leitura = {"conta": "TPP", "completa": True, "erros": [], "chamadas": 1, "inicio": "x", "fim": "y", "envios": [
            {"conta": "TPP", "envio_id": 500, "pedido_id": 2, "custo_vendedor": 20.0, "custo_bruto": 30.0}]}
        p1, i1 = ml_pedidos.filtrar_pedido("TPP", pedido_api(1, "2026-11-01T10:00:00.000-04:00", pack=77))
        p2, i2 = ml_pedidos.filtrar_pedido("TPP", pedido_api(2, "2026-11-01T10:00:00.000-04:00", pack=77))
        p3, i3 = ml_pedidos.filtrar_pedido("TPP", pedido_api(3, "2026-11-01T10:00:00.000-04:00", pack=77))
        leitura["pedidos"], leitura["itens"] = [p1, p2, p3], i1 + i2 + i3
        frete = {"tipo": "CHARGE/SHIPPING/CFFE", "valor": 20.0, "descricao": "", "cobranca_id": "90"}
        leitura["cobrancas"] = [{"conta": "TPP", "pedido_id": 1, "seq": 1, **frete},
                                {"conta": "TPP", "pedido_id": 2, "seq": 1, **frete}]
        with tempfile.TemporaryDirectory() as d:
            banco = Path(d) / "v.db"
            ml_pedidos.gravar(banco, leitura)
            peds = RepositorioPedidos(banco).pedidos("TPP")
        self.assertEqual([p.frete() for p in peds], [20.0, 0.0, 0.0])        # nem repetido, nem o envio de reserva
        self.assertEqual(round(sum(p.liquido() for p in peds), 2), 3 * (100.0 - 10.0) - 20.0)


if __name__ == "__main__":
    unittest.main()
