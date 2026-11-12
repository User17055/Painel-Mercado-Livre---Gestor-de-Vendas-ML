# -*- coding: utf-8 -*-
"""O coletor de pedidos so deixa passar a lista fechada: nada de comprador chega ao banco.
Este arquivo de teste e o UNICO lugar que escreve os nomes dos campos de comprador do ML (para provar que sao descartados)."""
import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path

from painel.nucleo import caminhos  # noqa: F401  (analise\ no sys.path)
from painel.nucleo import conferencia

import ml_pedidos

PEDIDO_FALSO = {
    "id": 2000001, "pack_id": None, "date_created": "2026-11-10T10:00:00.000-03:00", "date_closed": "2026-11-10T10:01:00.000-03:00",
    "status": "paid", "tags": ["paid", "delivered"], "total_amount": 157.99, "coupon": {"id": None, "amount": 0},
    "shipping": {"id": 4000001},
    "buyer": {"id": 99, "nickname": "COMPRADOR_TESTE", "first_name": "Fulano", "last_name": "Teste",
              "email": "fulano@exemplo.com", "phone": {"number": "999999999"}, "billing_info": {"doc_number": "00000000000"}},
    "payments": [{"payer_id": 99, "transaction_amount": 157.99}],
    "order_items": [{"item": {"id": "MLB1", "title": "Bravecto 250mg", "variation_id": None, "seller_sku": ""},
                     "quantity": 1, "unit_price": 157.99, "sale_fee": 19.75, "listing_type_id": "gold_special"}],
}
SENSIVEIS = ("COMPRADOR_TESTE", "Fulano", "fulano@exemplo.com", "999999999", "00000000000")


class TestListaFechada(unittest.TestCase):
    def test_filtrar_descarta_comprador(self):
        linha, itens = ml_pedidos.filtrar_pedido("TPP", PEDIDO_FALSO)
        texto = repr((linha, itens))
        for s in SENSIVEIS:
            self.assertNotIn(s, texto)
        self.assertEqual(set(linha), set(ml_pedidos.ESQUEMA["pedidos"]))
        self.assertEqual(set(itens[0]), set(ml_pedidos.ESQUEMA["pedido_itens"]))

    def test_filtrar_mantem_o_necessario(self):
        linha, itens = ml_pedidos.filtrar_pedido("TPP", PEDIDO_FALSO)
        self.assertEqual(linha["pedido_id"], 2000001)
        self.assertEqual(linha["envio_id"], 4000001)
        self.assertEqual(linha["tags"], "paid,delivered")
        self.assertEqual((itens[0]["anuncio_id"], itens[0]["quantidade"], itens[0]["preco_unit"], itens[0]["tarifa_unit"]),
                         ("MLB1", 1, 157.99, 19.75))

    def test_banco_novo_passa_na_conferencia(self):
        with tempfile.TemporaryDirectory() as d:
            banco = ml_pedidos.criar_banco(Path(d) / "v.db")
            ok, txt = conferencia.sem_comprador(banco)
            self.assertTrue(ok, txt)

    def test_coluna_extra_e_pega(self):
        with tempfile.TemporaryDirectory() as d:
            banco = ml_pedidos.criar_banco(Path(d) / "v.db")
            with closing(sqlite3.connect(banco)) as con, con:
                con.execute("ALTER TABLE pedidos ADD COLUMN nickname TEXT")
            ok, txt = conferencia.sem_comprador(banco)
            self.assertFalse(ok)
            self.assertIn("pedidos.nickname", txt)


if __name__ == "__main__":
    unittest.main()
