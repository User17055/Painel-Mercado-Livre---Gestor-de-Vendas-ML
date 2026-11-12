# -*- coding: utf-8 -*-
"""Pacote da equipe: so os modulos de analise/ que o painel usa entram na imagem Docker.

A lista esta escrita no Dockerfile (COPY) e no Dockerfile.dockerignore. Este teste segue os imports a partir do pacote do
painel e confere que as duas listas sao exatamente os modulos necessarios: se faltar um, a imagem quebra; se sobrar, vai
para a equipe uma ferramenta que o painel nao usa.
"""
import ast
import re
import unittest
from pathlib import Path

SISTEMA = Path(__file__).resolve().parents[1]
ANALISE = SISTEMA.parents[1] / "analise"


def _imports_ml(arquivo: Path) -> set[str]:
    nomes = set()
    for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            nomes |= {a.name for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module)
    return {n for n in nomes if n.startswith("ml_")}


def modulos_necessarios() -> set[str]:
    falta = set()
    for f in (SISTEMA / "painel").rglob("*.py"):
        falta |= _imports_ml(f)
    vistos = set()
    while falta:
        m = falta.pop()
        if m in vistos:
            continue
        vistos.add(m)
        falta |= _imports_ml(ANALISE / f"{m}.py") - vistos
    return vistos


class TestPacote(unittest.TestCase):
    def test_dockerfile_copia_so_o_necessario(self):
        txt = (SISTEMA / "Dockerfile").read_text(encoding="utf-8")
        copiados = set(re.findall(r"analise/(ml_\w+)\.py", txt))
        self.assertEqual(copiados, modulos_necessarios())

    def test_dockerignore_libera_so_o_necessario(self):
        txt = (SISTEMA / "Dockerfile.dockerignore").read_text(encoding="utf-8")
        liberados = set(re.findall(r"^!analise/(ml_\w+)\.py$", txt, re.M))
        self.assertEqual(liberados, modulos_necessarios())


if __name__ == "__main__":
    unittest.main()
