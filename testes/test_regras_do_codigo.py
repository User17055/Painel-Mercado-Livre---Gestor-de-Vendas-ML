# -*- coding: utf-8 -*-
"""Regras fixas do projeto que da para conferir lendo os arquivos (nao roda nada, nao chama a API):

1. Nenhum caminho de um computador especifico (C:\\Users\\fulano, /home/fulano) em codigo ou configuracao: as pastas
   vem das variaveis de ambiente (painel/nucleo/caminhos.py). Exemplo com marcador (<seu-usuario>) pode.
2. .ps1 so com caracteres ASCII (o PowerShell 5.1 le arquivo sem BOM como ANSI e quebra acento).
3. API do Mercado Livre so leitura: nenhum codigo faz pedido HTTP de escrita (POST, PUT, PATCH, DELETE).

A lista do Docker fica em test_pacote.py; a regra de comprador, em test_privacidade.py.
"""
import re
import unittest
from pathlib import Path

PROJETO = Path(__file__).resolve().parents[1]
ESTE = Path(__file__).resolve()
FORA = {".git", ".venv", "venv", "dados", "__pycache__", ".pytest_cache"}
# codigo e configuracao (a documentacao em docs/ pode citar um caminho para explicar a regra)
EXTENSOES = {".py", ".ps1", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".txt"}
NOMES = {"Dockerfile", ".dockerignore", ".env.exemplo", ".gitignore", ".gitattributes", ".editorconfig"}

# Windows sem diferenca de maiuscula; /home e /Users (Linux e Mac) exatos, para nao confundir com o endereco /users/me da API
_RX_CAMINHO = re.compile(r"(?i:[a-z]:[\\/]+users[\\/]+)(?!<)|/home/(?!<)\w|/Users/(?!<)\w")
_RX_ESCRITA = re.compile(r"\.(post|put|patch|delete)\s*\(|method\s*=\s*['\"](POST|PUT|PATCH|DELETE)['\"]", re.I)


def _arquivos(filtro):
    return sorted(p for p in PROJETO.rglob("*")
                  if p.is_file() and not FORA & set(p.relative_to(PROJETO).parts) and filtro(p))


def _codigo_e_config(p: Path) -> bool:
    return p.resolve() != ESTE and (p.suffix in EXTENSOES or p.name in NOMES)


class TestRegrasDoCodigo(unittest.TestCase):
    def test_nenhum_caminho_de_um_pc_especifico(self):
        achados = []
        for arq in _arquivos(_codigo_e_config):
            for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
                if _RX_CAMINHO.search(linha):
                    achados.append(f"{arq.relative_to(PROJETO)}:{n}")
        self.assertEqual(achados, [], "use as variaveis de ambiente de painel/nucleo/caminhos.py")

    def test_ps1_so_ascii(self):
        achados = []
        for arq in _arquivos(lambda p: p.suffix == ".ps1"):
            for n, linha in enumerate(arq.read_bytes().splitlines(), 1):
                if any(b > 127 for b in linha):
                    achados.append(f"{arq.relative_to(PROJETO)}:{n}")
        self.assertEqual(achados, [], "tirar acentos e simbolos do .ps1")

    def test_api_so_leitura(self):
        achados = []
        for arq in _arquivos(lambda p: p.suffix == ".py" and p.resolve() != ESTE):
            for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
                if _RX_ESCRITA.search(linha):
                    achados.append(f"{arq.relative_to(PROJETO)}:{n}")
        self.assertEqual(achados, [], "a API do ML so pode ser lida (GET)")

    def test_regras_pegam_os_exemplos(self):
        for exemplo in (r"C:\Users\fulano\dados", "c:/users/fulano", "/home/fulano/x", "/Users/fulano/x"):
            self.assertTrue(_RX_CAMINHO.search(exemplo), exemplo)
        for exemplo in ("C:/Users/<seu-usuario>/.ml-api", "./dados", "/app/dados", "https://api.mercadolibre.com/users/me"):
            self.assertFalse(_RX_CAMINHO.search(exemplo), exemplo)
        for exemplo in ("requests.post(url)", "s.delete (url)", 'urlopen(Request(u, method="PUT"))'):
            self.assertTrue(_RX_ESCRITA.search(exemplo), exemplo)
        for exemplo in ("requests.get(url)", 'con.execute("DELETE FROM pedidos")', "postagem(x)"):
            self.assertFalse(_RX_ESCRITA.search(exemplo), exemplo)


if __name__ == "__main__":
    unittest.main()
