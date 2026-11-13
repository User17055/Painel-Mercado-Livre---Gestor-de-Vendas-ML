# -*- coding: utf-8 -*-
"""Conferencias de que o controle de vendas bate com a fonte. Cada uma devolve (ok, texto) para mostrar na tela.

sem_comprador      colunas do vendas_api.db so da lista fechada (nenhum dado de comprador no banco)
api_x_excel        liquido por venda pela API = "Total (BRL)" do relatorio de vendas do ML (Excel), venda a venda
unidades           unidades por contagem independente (soma dos itens montados x soma direta no banco)

Linha de comando (raiz do repositorio; le o banco, nao chama a API):
  python -m painel.nucleo.conferencia <CONTA> <relatorio_de_vendas.xlsx> <AAAA-MM-DD> <AAAA-MM-DD>
"""
import re
import sqlite3
import warnings
from collections import defaultdict
from contextlib import closing
from datetime import date
from pathlib import Path

from painel.nucleo import caminhos
from painel.nucleo.repositorio import RepositorioPedidos

import ml_pedidos  # noqa: E402  (lista fechada de colunas: a mesma do coletor)

# Relatorio de vendas do ML (painel do ML > Vendas > exportar Excel): so estas colunas sao lidas, pelo inicio do cabecalho.
# As outras (inclusive as do comprador) nunca sao lidas.
COLUNAS_EXCEL = {"venda": "N.º de venda", "data": "Data de venda", "estado": "Estado", "receita": "Receita por produtos",
                 "total": "Total (BRL)"}
MESES = {m: i for i, m in enumerate(("janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro "
                                     "dezembro").split(), 1)}


def sem_comprador(banco: Path = caminhos.BANCO_VENDAS) -> tuple[bool, str]:
    """Toda coluna de toda tabela do banco tem de estar no esquema do coletor (nada a mais entra escondido)."""
    banco = Path(banco)
    if not banco.exists():
        return True, "banco de pedidos ainda não existe"
    permitidas = ml_pedidos.colunas_permitidas()
    extras = []
    with closing(sqlite3.connect(f"file:{banco}?mode=ro", uri=True)) as con:
        for (tab,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
            for col in con.execute(f"PRAGMA table_info({tab})"):
                if col[1] not in permitidas.get(tab, set()):
                    extras.append(f"{tab}.{col[1]}")
    return (not extras), ("só colunas da lista fechada" if not extras else "colunas fora da lista: " + ", ".join(extras))


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def ler_relatorio_ml(arquivo: Path) -> list[dict]:
    """Linhas do relatorio de vendas do ML com dinheiro (venda, dia, estado, receita, total). As linhas sem dinheiro sao os
    itens de um carrinho: o dinheiro fica na linha do pacote."""
    import openpyxl
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
        linhas = list(wb.worksheets[0].iter_rows(values_only=True))
        wb.close()
    i = next((i for i, r in enumerate(linhas[:15]) if r and str(r[0] or "").strip().startswith(COLUNAS_EXCEL["venda"])), None)
    if i is None:
        raise ValueError("cabeçalho 'N.º de venda' não encontrado: é o relatório de vendas do ML?")
    cab = [str(c or "").strip() for c in linhas[i]]
    idx = {}
    for campo, inicio in COLUNAS_EXCEL.items():
        j = next((j for j, c in enumerate(cab) if c.startswith(inicio)), None)
        if j is None:
            raise ValueError(f"coluna '{inicio}' não encontrada (o ML mudou o relatório?)")
        idx[campo] = j
    saida = []
    for r in linhas[i + 1:]:
        if not r or r[idx["venda"]] in (None, ""):
            continue
        receita, total = _num(r[idx["receita"]]), _num(r[idx["total"]])
        if not receita and not total:
            continue
        m = re.match(r"(\d+) de (\w+) de (\d+)", str(r[idx["data"]]))
        if not m or m.group(2).lower() not in MESES:
            raise ValueError(f"data em formato inesperado na venda {r[idx['venda']]}")
        saida.append({"venda": str(r[idx["venda"]]).strip(), "estado": str(r[idx["estado"]] or ""), "total": total,
                      "dia": date(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1))).isoformat()})
    return saida


def api_x_excel(conta: str, arquivo: Path, de: date, ate: date, banco: Path = caminhos.BANCO_VENDAS,
                tolerancia: float = 0.01, mostrar: int = 20) -> tuple[bool, str]:
    """Venda a venda: liquido pela API (banco) x "Total (BRL)" do relatorio exportado do ML, no periodo [de, ate].
    O numero da venda do relatorio e o do pedido ou, no carrinho, o do pacote (soma os pedidos do pacote).
    Diferenca esperada e explicada: venda que mudou de situacao depois de o relatorio ser exportado (ex.: cancelada depois)."""
    rel = [x for x in ler_relatorio_ml(arquivo) if de.isoformat() <= x["dia"] <= ate.isoformat()]
    peds = RepositorioPedidos(banco).pedidos(conta, de, ate)
    por_numero = defaultdict(list)
    for p in peds:
        por_numero[p.pedido_id].append(p)
        if p.pack_id:
            por_numero[p.pack_id].append(p)
    usados, difs, so_rel = set(), [], []
    for x in rel:
        grupo = por_numero.get(x["venda"]) or []
        if not grupo:
            so_rel.append(x)
            continue
        usados |= {p.pedido_id for p in grupo}
        api = round(sum(p.liquido() for p in grupo), 2)
        if abs(api - x["total"]) > tolerancia:
            difs.append((x["venda"], x["estado"][:45], x["total"], api))
    so_api = [p for p in peds if p.pedido_id not in usados and abs(p.liquido()) > tolerancia]
    tot_rel, tot_api = sum(x["total"] for x in rel), sum(p.liquido() for p in peds)
    ok = not difs and not so_rel and not so_api
    txt = [f"{conta} {de:%d/%m/%Y} a {ate:%d/%m/%Y}: {len(rel)} vendas no relatório, {len(rel) - len(difs) - len(so_rel)} iguais "
           f"(até R$ {tolerancia:.2f}), {len(difs)} diferentes, {len(so_rel)} só no relatório, {len(so_api)} só na API",
           f"Total do relatório R$ {tot_rel:,.2f} | total pela API R$ {tot_api:,.2f} | diferença R$ {tot_api - tot_rel:,.2f}"]
    txt += [f"  diferente: venda {v} ({e}) relatório {t:,.2f} x API {a:,.2f}" for v, e, t, a in difs[:mostrar]]
    txt += [f"  só no relatório: venda {x['venda']} {x['dia']} total {x['total']:,.2f}" for x in so_rel[:mostrar]]
    txt += [f"  só na API: pedido {p.pedido_id} {p.fechado_em:%Y-%m-%d} {p.status} líquido {p.liquido():,.2f}" for p in so_api[:mostrar]]
    return ok, "\n".join(txt)


def unidades(conta: str, de: date | None = None, ate: date | None = None,
             banco: Path = caminhos.BANCO_VENDAS) -> tuple[bool, str]:
    """Soma das quantidades dos pedidos montados pelo repositorio x soma direta da tabela pedido_itens (mesmos pedidos)."""
    if not Path(banco).exists():
        return False, "banco de pedidos ainda não existe"
    peds = RepositorioPedidos(banco).pedidos(conta, de, ate)
    montado = sum(i.quantidade for p in peds for i in p.itens)
    ids = [int(p.pedido_id) for p in peds]
    direto = 0
    with closing(sqlite3.connect(f"file:{Path(banco)}?mode=ro", uri=True)) as con:
        for k in range(0, len(ids), 500):
            bloco = ids[k:k + 500]
            direto += con.execute(f"SELECT COALESCE(SUM(quantidade), 0) FROM pedido_itens WHERE conta = ? AND pedido_id IN "
                                  f"({','.join('?' * len(bloco))})", (conta, *bloco)).fetchone()[0]
    return montado == direto, f"{conta}: {montado} unidades nos pedidos x {direto} na contagem direta do banco"


def main(argv: list[str]) -> int:
    import sys
    if len(argv) != 4 or argv[0].upper() not in ("PD", "TPP"):
        print(__doc__)
        return 2
    conta, arquivo, de, ate = argv[0].upper(), Path(argv[1]), date.fromisoformat(argv[2]), date.fromisoformat(argv[3])
    resultados = [sem_comprador(), unidades(conta, de, ate), api_x_excel(conta, arquivo, de, ate, mostrar=50)]
    sys.stdout.reconfigure(encoding="utf-8")
    for ok, txt in resultados:
        print(("OK  " if ok else "VER ") + txt)
    return 0 if all(ok for ok, _ in resultados) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
