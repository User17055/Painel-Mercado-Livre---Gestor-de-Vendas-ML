# -*- coding: utf-8 -*-
"""ml_margem.py: regra de custo do produto usada pelo painel. Nao chama a API nem grava nada.

classificar(titulo)        produto pelo titulo do anuncio (Bravecto por tamanho, Franpet pela primeira palavra)
unidades_no_titulo(titulo) unidades por venda em kits/combos
custo_mercadoria(...)      custo da tabela (- rebate % se aplica_rebate=sim) x unidades do kit + brinde nos combos
ler_custos()               custos_produtos.csv (pasta ML_CONFIG_DIR): produto -> linha
"""
import csv, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # py -I nao inclui a pasta do script
import ml_param  # noqa: E402

CONTAS = ("PD", "TPP")
NOMES = {"PD": "PetDelivery", "TPP": "TUDOPRAPET"}


def ler(p):
    p = Path(p)
    if not p.exists():
        return None
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def num(x, padrao=None):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return padrao


def _faixa(a, b):
    """Faixa de peso no titulo: '20 a 40', '20-40', '20 Kg A 40 Kg', '4,5 - 10', '4,5 10' (o 'Kg' entre os numeros aparece em titulos reais)."""
    return rf"(?<![\d,]){re.escape(a)}\s*(?:kg)?\s*(?:a|-|até|ate)?\s*{re.escape(b)}(?![\d,])"


def classificar(titulo):
    """Produto pelo titulo. Para Franpet vale a palavra que aparece PRIMEIRO (titulos de omega trazem 'pele pelo' no fim)."""
    t = (titulo or "").lower()
    if "bravecto" in t:
        if re.search(_faixa("2", "4,5") + r"|112,5|112\.5", t):
            return "Bravecto112"
        if re.search(_faixa("40", "56") + r"|1400", t):
            return "Bravecto1400"
        if re.search(_faixa("20", "40") + "|" + _faixa("20,1", "40") + r"|1000", t):
            return "Bravecto1000"
        if re.search(_faixa("10", "20") + r"|500|verde", t):
            return "Bravecto500"
        if re.search(_faixa("4,5", "10") + r"|250|laranja", t):
            return "Bravecto250"
        return None
    achados = []
    for chave, prod in (("condro", "Condro"), ("mega", "Omega"), ("pele", "PeleePelo"), ("pelo", "PeleePelo"), ("derme", "PeleePelo"), ("probi", "Probiotico")):
        i = t.find(chave)
        if i >= 0:
            achados.append((i, prod))
    if not achados:
        return None
    prod = min(achados)[1]
    if prod == "Condro":
        return "Condro1000" if "1000" in t else ("Condro500" if "500" in t else None)
    if prod == "Omega":
        return "Omega1000" if "1000" in t else ("Omega500" if "500" in t else None)
    return prod


def unidades_no_titulo(titulo):
    """Quantas unidades do produto vao em UMA venda do anuncio: 'Kit 2 Unid', 'Kit C/2', 'Combo ... (2 Unidades)' = 2; senao 1.
    So olha titulos com 'kit' ou 'combo' (evita confundir '30 comprimidos' com unidades)."""
    t = (titulo or "").lower()
    if "kit" not in t and "combo" not in t:
        return 1
    m = re.search(r"kit\s*(?:c/|com|de)?\s*(\d{1,2})\b", t) or re.search(r"\b(\d{1,2})\s*unid", t)
    n = int(m.group(1)) if m else 1
    return n if 1 <= n <= 10 else 1


def custo_mercadoria(prod, titulo, custos, rebate):
    """Custo da MERCADORIA comprada por venda de 1 unidade do anuncio: custo da tabela (- rebate % se aplica_rebate=sim) x unidades do kit,
    + brinde Franpet nos combos de Bravecto ('+ Fran'/'+ Gourmet'). E a base do credito de imposto (Lucro Real). None se nao ha custo."""
    c = custos.get(prod) if prod else None
    custo = num(c["custo_sem_rebate"]) if c else None
    if custo is None:
        return None
    ef = custo * (1 - (rebate / 100 if c["aplica_rebate"] == "sim" else 0)) * unidades_no_titulo(titulo)
    # combo: Bravecto vendido junto com produto Franpet (brinde). Custo do brinde: linha BrindeFranpet de custos_produtos.csv (sem valor, conta 0).
    if prod.startswith("Bravecto") and re.search(r"\+\s*(fran|gourmet)", (titulo or "").lower()):
        ef += num((custos.get("BrindeFranpet") or {}).get("custo_sem_rebate"), 0.0) or 0.0
    return ef


def ler_custos():
    return {r["produto"]: r for r in ler(ml_param.DIR_CONFIG / "custos_produtos.csv") or []}   # sem o arquivo: custos pendentes
