# -*- coding: utf-8 -*-
"""Botao "Atualizar agora": uma atualizacao por vez e intervalo minimo; falha nao bloqueia nova tentativa."""
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from painel.nucleo.atualizar import AtualizacaoRecusada, Atualizador


class TestAtualizador(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        self.a = Atualizador(15, trava=d / "t.trava", registro=d / "r.json")

    def tearDown(self):
        self.dir.cleanup()

    def test_executa_e_registra(self):
        self.assertEqual(self.a.executar(lambda: {"pedidos_novos": 3}), {"pedidos_novos": 3})
        u = self.a.ultima()
        self.assertTrue(u["ok"])
        self.assertFalse(self.a.trava.exists())

    def test_intervalo_minimo(self):
        self.a.executar(lambda: {})
        ok, motivo = self.a.pode_atualizar()
        self.assertFalse(ok)
        self.assertIn("próxima liberada", motivo)
        self.assertTrue(self.a.pode_atualizar(datetime.now() + timedelta(minutes=16))[0])
        with self.assertRaises(AtualizacaoRecusada):
            self.a.executar(lambda: {})

    def test_uma_por_vez(self):
        self.a.trava.write_text("123")
        self.assertFalse(self.a.pode_atualizar()[0])
        with self.assertRaises(AtualizacaoRecusada):
            self.a.executar(lambda: {})

    def test_trava_abandonada_e_liberada(self):
        self.a.trava.write_text("123")
        velho = time.time() - 31 * 60
        os.utime(self.a.trava, (velho, velho))
        self.assertTrue(self.a.pode_atualizar()[0])
        self.a.executar(lambda: {})
        self.assertFalse(self.a.trava.exists())

    def test_falha_nao_bloqueia(self):
        def quebra():
            raise RuntimeError("API fora")
        with self.assertRaises(RuntimeError):
            self.a.executar(quebra)
        self.assertFalse(self.a.ultima()["ok"])
        self.assertFalse(self.a.trava.exists())
        self.assertTrue(self.a.pode_atualizar()[0])


if __name__ == "__main__":
    unittest.main()
