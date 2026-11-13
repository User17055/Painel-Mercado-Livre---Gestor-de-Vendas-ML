# -*- coding: utf-8 -*-
"""Lucro por item (CalculadoraLucro.resultado), resumos e Excel, com parametros e custos inventados (nada da empresa)."""
import io
import unittest
from datetime import date, datetime

from painel.nucleo import caminhos, exportar, resumo  # noqa: F401  (analise\ no sys.path)
from painel.nucleo.calculo import CalculadoraLucro
from painel.nucleo.modelos import Cobranca, CustoProduto, ItemPedido, Pedido, RegraImposto, Situacao

DIA = datetime.fromisoformat("2026-11-10T10:00:00-03:00")


class ParametrosFalsos:
    """Mesma interface de RepositorioParametros, com numeros inventados."""

    def __init__(self, rebate=10.0, comparar=20.0, debito=10.0, credito=5.0):
        self.custos_tabela = {"Bravecto250": {"produto": "Bravecto250", "custo_sem_rebate": "50", "aplica_rebate": "sim"},
                              "Condro500": {"produto": "Condro500", "custo_sem_rebate": "", "aplica_rebate": "nao"}}
        self._rebate, self._comparar, self.debito, self.credito = rebate, comparar, debito, credito

    def custos_brutos(self):
        return self.custos_tabela

    def rebate_pct(self):
        return self._rebate

    def rebate_comparacao(self):
        return self._comparar

    def regra_imposto(self, conta, produto=None):
        return RegraImposto(conta, "lucro_real", self.debito, self.credito, produto or "", "teste")

    def custos(self):
        return [CustoProduto(p, float(r["custo_sem_rebate"]) if r["custo_sem_rebate"] else None, "teste",
                             r["aplica_rebate"] == "sim") for p, r in self.custos_tabela.items()]

    def regras_imposto(self):
        return [self.regra_imposto("TPP")]


def pedido(pid="1", itens=None, cobrancas=None, status="paid", **kw):
    itens = itens or [ItemPedido("MLB1", "Bravecto 4,5 a 10 kg", 1, 100.0, 12.0, "gold_pro")]
    cob = cobrancas if cobrancas is not None else [Cobranca("CHARGE/CORE/x", 12.0, cobranca_id=f"{pid}c"),
                                                   Cobranca("CHARGE/SHIPPING/x", 20.0, cobranca_id=f"{pid}f")]
    return Pedido("TPP", pid, DIA, status, itens, cobrancas=cob, **kw)


class TestLucroPorItem(unittest.TestCase):
    def test_formula_completa(self):
        r, = CalculadoraLucro(ParametrosFalsos()).resultado(pedido())
        self.assertEqual((r.liquido, r.custo, r.rebate), (68.0, 50.0, 5.0))       # 100 - 12 - 20; rebate 10% de 50
        self.assertEqual(r.lucro_antes_imposto, 23.0)                              # 68 - 50 + 5
        self.assertEqual(r.lucro_com_rebate, 28.0)                                 # comparacao com 20%: 68 - 50 + 10
        self.assertEqual(r.imposto, 7.75)                                          # 100 x 10% - 45 x 5%
        self.assertEqual(r.lucro_depois_imposto, 15.25)
        self.assertEqual((r.produto, r.tipo_anuncio, r.avisos), ("Bravecto250", "Premium", []))

    def test_sem_comparacao_e_sem_rebate(self):
        r, = CalculadoraLucro(ParametrosFalsos(rebate=0.0, comparar=None)).resultado(pedido())
        self.assertEqual((r.rebate, r.lucro_antes_imposto, r.lucro_com_rebate), (0.0, 18.0, None))

    def test_carrinho_soma_igual_ao_pedido(self):
        itens = [ItemPedido("MLB1", "Bravecto 4,5 a 10 kg", 1, 100.0, 12.0), ItemPedido("MLB2", "Kit 2 Unid Bravecto 250mg", 1, 200.0, 24.0)]
        p = pedido(itens=itens, cobrancas=[Cobranca("CHARGE/CORE/x", 36.0), Cobranca("CHARGE/SHIPPING/x", 30.01)])
        L = CalculadoraLucro(ParametrosFalsos()).resultado(p)
        self.assertEqual(round(sum(x.liquido for x in L), 2), p.liquido())
        self.assertEqual([x.frete for x in L], [10.0, 20.01])                     # rateio pelo bruto; o ultimo fecha o centavo
        self.assertEqual(L[1].custo, 100.0)                                        # kit de 2 unidades

    def test_custo_pendente_nao_inventa(self):
        it = ItemPedido("MLB3", "Condro 500 mg", 1, 80.0, 9.0)
        r, = CalculadoraLucro(ParametrosFalsos()).resultado(pedido(itens=[it], cobrancas=[]))
        self.assertIsNone(r.custo)
        self.assertIsNone(r.lucro_depois_imposto)
        self.assertIn("custo pendente", r.avisos)
        it = ItemPedido("MLB4", "Coleira", 1, 80.0, 9.0)
        r, = CalculadoraLucro(ParametrosFalsos()).resultado(pedido(itens=[it], cobrancas=[]))
        self.assertIn("produto não identificado pelo título", r.avisos)

    def test_imposto_pendente(self):
        par = ParametrosFalsos()
        par.debito = None
        r, = CalculadoraLucro(par).resultado(pedido())
        self.assertEqual(r.imposto, 0.0)
        self.assertEqual(r.lucro_depois_imposto, r.lucro_antes_imposto)
        self.assertIn("imposto pendente", r.avisos)

    def test_cancelada_sem_custo_de_mercadoria(self):
        p = pedido(status="cancelled", cobrancas=[Cobranca("CHARGE/SHIPPING/x", 15.0)], tags=("delivered",), reembolsado=100.0)
        r, = CalculadoraLucro(ParametrosFalsos()).resultado(p)
        self.assertEqual(r.situacao, Situacao.DEVOLVIDA)
        self.assertEqual((r.custo, r.liquido, r.lucro_depois_imposto), (0.0, -15.0, -15.0))

    def test_pedido_sem_itens(self):
        self.assertEqual(CalculadoraLucro(ParametrosFalsos()).resultado(Pedido("TPP", "9", DIA, "paid")), [])


class TestResumos(unittest.TestCase):
    def linhas(self):
        calc = CalculadoraLucro(ParametrosFalsos())
        itens = [ItemPedido("MLB1", "Bravecto 4,5 a 10 kg", 1, 100.0, 12.0), ItemPedido("MLB3", "Condro 500 mg", 1, 100.0, 12.0)]
        return calc.resultados([pedido("1"), pedido("2", itens=itens, cobrancas=[]), pedido("3", status="cancelled", cobrancas=[])])

    def test_vendas_contam_pedidos_e_margem_so_com_custo(self):
        L = self.linhas()
        t = resumo.total(L)
        self.assertEqual((t.vendas, t.unidades, t.sem_custo_un), (2, 3, 1))       # cancelado fora; carrinho = 1 venda
        com_custo = [x for x in resumo.validas(L) if x.custo is not None]
        esperado = round(sum(x.lucro_depois_imposto for x in com_custo) / sum(x.liquido for x in com_custo) * 100, 1)
        self.assertEqual(t.margem_pct(), esperado)

    def test_carrinho_conta_uma_venda(self):
        """No ML um carrinho vira um pedido por produto no mesmo pacote; o relatorio de vendas conta o pacote como 1 venda."""
        calc = CalculadoraLucro(ParametrosFalsos())
        L = calc.resultados([pedido("1", pack_id="P1"), pedido("2", pack_id="P1"), pedido("3")])
        self.assertEqual([x.venda_id for x in L], ["P1", "P1", "3"])
        self.assertEqual(resumo.total(L).vendas, 2)

    def test_por_anuncio(self):
        r = {x.anuncio_id: x for x in resumo.por_anuncio(self.linhas())}
        self.assertEqual((r["MLB1"].vendas, r["MLB1"].unidades), (2, 2))
        self.assertIsNone(r["MLB3"].margem_pct())

    def test_excel_com_todas_as_abas(self):
        from openpyxl import load_workbook
        par = ParametrosFalsos()
        abas = resumo.abas_excel(self.linhas(), par, ["TPP"], date(2026, 11, 1), date(2026, 11, 13), {"TPP": None})
        wb = load_workbook(io.BytesIO(exportar.para_excel(abas)))
        self.assertEqual(wb.sheetnames, ["Resumo", "Por produto", "Por anúncio", "Vendas", "Canceladas e devolvidas", "Custos",
                                         "Rebate", "Imposto", "Premissas"])
        cab = [c.value for c in wb["Vendas"][1]]
        self.assertEqual(cab[:9], ["Conta", "Data", "Pedido", "Venda", "Anúncio", "Título", "Produto", "Tipo", "Unidades"])
        self.assertIn("Margem (%)", [c.value for c in wb["Resumo"][1]])
        self.assertFalse(any(str(c.value).startswith("_") for c in wb["Resumo"][1]))
        self.assertEqual(wb["Vendas"]["B2"].number_format, "dd/mm/yyyy hh:mm")
        self.assertEqual(resumo.nome_arquivo(["TPP", "PD"], date(2026, 1, 1), date(2026, 11, 13)),
                         "vendas-ml_TPP-PD_2026-01-01_2026-11-13.xlsx")


class TestFormato(unittest.TestCase):
    def test_padrao_brasileiro(self):
        from painel.nucleo import formato as F
        self.assertEqual(F.brl(1234.5), "R$ 1.234,50")
        self.assertEqual(F.brl(-331.72), "−R$ 331,72")
        self.assertTrue(F.negativo(F.brl(-1)))
        self.assertEqual((F.brl(None), F.pct(12.34), F.inteiro(1034)), ("—", "12,3%", "1.034"))
        self.assertEqual(F.data_hora("2026-11-13T12:47:48"), "13/11/2026 12:47")
        self.assertEqual(F.mes("2026-03"), "Março/2026")


if __name__ == "__main__":
    unittest.main()
