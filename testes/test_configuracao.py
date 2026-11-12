# -*- coding: utf-8 -*-
"""Portabilidade: as pastas vem das variaveis de ambiente (qualquer PC / Docker) e, sem elas, do proprio projeto."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJETO = Path(__file__).resolve().parents[1]
SONDA = (
    "import sys, json; sys.path.insert(0, sys.argv[1]);"
    "from painel.nucleo import caminhos; import ml_param, ml_margem, ml_pedidos;"
    "print(json.dumps({'dados': str(caminhos.DADOS), 'config': str(caminhos.CONFIG), 'banco_pai': str(ml_pedidos.BANCO.parent),"
    "'param': str(ml_param.ARQ), 'banco': str(ml_pedidos.BANCO), 'atualizar': caminhos.PERMITE_ATUALIZAR}))"
)


def sondar(extra_env: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ML_", "PAINEL_"))}
    env.update(extra_env)
    r = subprocess.run([sys.executable, "-I", "-c", SONDA, str(PROJETO)], env=env, capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


class TestConfiguracao(unittest.TestCase):
    def test_padrao_e_o_projeto(self):
        d = sondar({})
        projeto = PROJETO
        self.assertEqual(Path(d["dados"]), projeto / "dados")
        self.assertEqual(Path(d["banco_pai"]), Path(d["dados"]))            # coletor e painel olham a mesma pasta
        self.assertEqual(Path(d["param"]), projeto / "analise" / "ml_parametros.json")
        self.assertFalse(d["atualizar"])                                    # padrao: so leitura

    def test_variaveis_mandam(self):
        with tempfile.TemporaryDirectory() as dados, tempfile.TemporaryDirectory() as config:
            d = sondar({"ML_DADOS_DIR": dados, "ML_CONFIG_DIR": config, "PAINEL_PERMITE_ATUALIZAR": "1"})
            self.assertEqual(Path(d["dados"]), Path(dados).resolve())
            self.assertEqual(Path(d["banco_pai"]), Path(dados).resolve())
            self.assertEqual(Path(d["banco"]), Path(dados).resolve() / "vendas_api.db")
            self.assertEqual(Path(d["param"]), Path(config).resolve() / "ml_parametros.json")
            self.assertTrue(d["atualizar"])


if __name__ == "__main__":
    unittest.main()
