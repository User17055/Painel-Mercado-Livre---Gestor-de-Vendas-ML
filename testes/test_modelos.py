# -*- coding: utf-8 -*-
"""Modelos, rateio, resumo (acumulado, sem custo, canceladas a parte), parametros reais (imposto da TPP) e exportacao."""
import io
import unittest
from datetime import datetime

from painel.nucleo import caminhos, exportar, resumo
from painel.nucleo.calculo import ratear
from painel.nucleo.modelos import ItemPedido, Pedido, ResultadoItem, ResumoPeriodo, Situacao
from painel.nucleo.repositorio import RepositorioParametros

import ml_margem as M  # noqa: E402  (caminhos poe analise/ no sys.path)
import ml_param  # noqa: E402


def linha(conta, dia, liquido, custo, lucro, situacao=Situacao.VALIDA, produto="Bravecto250"):
    return ResultadoItem(conta=conta, data=datetime.fromisoformat(dia), pedido_id=dia, venda_id=dia, anuncio_id="MLB1", titulo="t",
                         produto=produto, tipo_anuncio="Clássico", unidades=1, bruto=liquido, tarifa=0, frete=0, liquido=liquido,
                         custo=custo, rebate=0, lucro_antes_imposto=lucro, lucro_com_rebate=None, imposto=0,
                         lucro_depois_imposto=lucro, situacao=situacao)


class TestModelos(unittest.TestCase):
    def test_item_e_pedido(self):
        it = ItemPedido("MLB1", "Bravecto", 2, 157.99, 19.75)
        self.assertEqual((it.bruto(), it.tarifa()), (315.98, 39.5))
        p = Pedido("TPP", "1", datetime(2026, 11, 10), "paid", [it, it])
        self.assertEqual(p.bruto(), 631.96)
        self.assertEqual(p.situacao(), Situacao.VALIDA)
        self.assertEqual(Pedido("TPP", "2", datetime(2026, 11, 10), "cancelled").situacao(), Situacao.CANCELADA)

    def test_ratear_fecha_o_centavo(self):
        partes = ratear(20.0, [100.0, 50.0, 50.0])
        self.assertEqual(round(sum(partes), 2), 20.0)
        self.assertEqual(partes[:2], [10.0, 5.0])
        self.assertEqual(round(sum(ratear(10.0, [1, 1, 1])), 2), 10.0)

    def test_margem(self):
        self.assertEqual(ResumoPeriodo("TPP", "2026-11", liquido=200, lucro_depois_imposto=20).margem_pct(), 10.0)
        self.assertIsNone(ResumoPeriodo("TPP", "2026-11").margem_pct())


class TestResumo(unittest.TestCase):
    def test_por_mes_acumula_por_conta(self):
        L = [linha("TPP", "2026-10-05", 100, 80, 10), linha("TPP", "2026-11-05", 100, 80, -5),
             linha("PD", "2026-11-05", 100, 80, 7), linha("TPP", "2026-11-06", 100, 80, 99, Situacao.CANCELADA),
             linha("TPP", "2026-11-07", 50, None, None)]
        r = {(x.conta, x.periodo): x for x in resumo.por_mes(L)}
        self.assertEqual(r[("TPP", "2026-10")].acumulado, 10)
        self.assertEqual(r[("TPP", "2026-11")].acumulado, 5)       # cancelada fora; sem custo fora do lucro
        self.assertEqual(r[("TPP", "2026-11")].sem_custo_un, 1)
        self.assertEqual(r[("TPP", "2026-11")].liquido, 150)       # sem custo entra no liquido
        self.assertEqual(r[("PD", "2026-11")].acumulado, 7)
        self.assertEqual(len(resumo.separadas(L)), 1)


TEM_PARAMETROS = all((caminhos.CONFIG / f).exists() for f in ("ml_parametros.json", "custos_produtos.csv"))


@unittest.skipUnless(TEM_PARAMETROS, "sem ml_parametros.json e custos_produtos.csv em ML_CONFIG_DIR (dados da empresa)")
class TestParametrosReais(unittest.TestCase):
    """Le ml_parametros.json e custos_produtos.csv de verdade: o painel aplica a mesma regra de analise/ (ml_param e ml_margem)."""

    def test_imposto_igual_ao_ml_param(self):
        par = RepositorioParametros()
        for conta in ("TPP", "PD"):
            for prod in ("Condro500", "Bravecto250", ""):
                r = par.regra_imposto(conta, prod or None)
                if ml_param.tem_imposto(par.P, conta):
                    self.assertEqual(r.debito_pct, ml_param.imposto_pct(par.P, conta, prod or None))
                    self.assertEqual(r.credito_pct, ml_param.credito_pct(par.P, conta, prod or None) or 0.0)
                else:
                    self.assertTrue(r.pendente())

    def test_custo_igual_ao_da_tabela(self):
        par = RepositorioParametros()
        for prod, linha in par.custos_brutos().items():
            c = par.custo(prod)
            self.assertEqual(c.custo_unit, M.num(linha.get("custo_sem_rebate"), None))
            self.assertEqual(c.aplica_rebate, (linha.get("aplica_rebate") or "").lower() == "sim")
        self.assertTrue(par.custo("ProdutoQueNaoExiste").pendente())


class TestExportar(unittest.TestCase):
    def test_csv(self):
        b = exportar.para_csv([linha("TPP", "2026-11-05", 100.5, 80, 10)])
        txt = b.decode("utf-8-sig")
        self.assertTrue(txt.startswith("Conta;Data;"))
        self.assertIn("100,50", txt)
        self.assertIn("valida", txt)

    def test_excel_autor_e_fonte(self):
        from openpyxl import load_workbook
        b = exportar.para_excel({"Resumo": resumo.por_mes([linha("TPP", "2026-11-05", 100, 80, 10)]), "Vazia": []})
        wb = load_workbook(io.BytesIO(b))
        self.assertEqual(wb.properties.creator, exportar.AUTOR)
        self.assertEqual(wb.sheetnames, ["Resumo", "Vazia"])
        self.assertEqual(wb["Resumo"]["A1"].font.name, "Arial")
        self.assertEqual(wb["Resumo"]["A1"].value, "Conta")


if __name__ == "__main__":
    unittest.main()
