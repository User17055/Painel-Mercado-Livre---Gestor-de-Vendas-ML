# -*- coding: utf-8 -*-
"""O coletor de pedidos so deixa passar a lista fechada: nada de comprador chega ao banco.
E nenhum codigo do painel ou de analise/ escreve o nome de um campo de comprador do ML.
Este arquivo de teste e o UNICO lugar que escreve esses nomes (para provar que sao descartados)."""
import re
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

PROJETO = Path(__file__).resolve().parents[1]
# Campos de comprador no JSON do ML. Pega tambem dentro de nomes compostos (buyer_id, payer_nickname, receiver_address).
CAMPOS_COMPRADOR = ("buyer", "payer", "receiver", "nickname", "first_name", "last_name", "email", "doc_number", "phone",
                    "address")
_RX_COMPRADOR = re.compile(r"(?<![a-z])(" + "|".join(CAMPOS_COMPRADOR) + r")(?![a-z])", re.I)


def _codigo():
    """Todo .py fora de testes/ (o painel e analise/)."""
    return sorted(PROJETO.glob("painel/**/*.py")) + sorted(PROJETO.glob("analise/*.py"))


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


class TestCodigoSemCampoDeComprador(unittest.TestCase):
    def test_nenhum_nome_de_campo_de_comprador_no_codigo(self):
        achados = []
        for arq in _codigo():
            for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
                m = _RX_COMPRADOR.search(linha)
                if m:
                    achados.append(f"{arq.relative_to(PROJETO)}:{n}: {m.group(0)}")
        self.assertEqual(achados, [], "use so a lista fechada de analise/ml_pedidos.py")

    def test_regra_pega_nome_composto(self):
        for exemplo in ("x = pedido['buyer']['id']", "payer_id = 1", "receiver_address", "BUYER", "dados.nickname"):
            self.assertTrue(_RX_COMPRADOR.search(exemplo), exemplo)
        for exemplo in ("comprador descartado", "quantidade", "anuncio_id"):
            self.assertFalse(_RX_COMPRADOR.search(exemplo), exemplo)


if __name__ == "__main__":
    unittest.main()
