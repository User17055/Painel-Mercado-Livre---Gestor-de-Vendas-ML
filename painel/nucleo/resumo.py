# -*- coding: utf-8 -*-
"""Agregacoes para a tela e para o Excel: por conta x mes (com acumulado), por conta x produto e por conta x anuncio; e o
montador das abas do Excel (docs/TELAS.md, secao 5).

So vendas validas entram nos totais; canceladas/devolvidas ficam numa lista a parte (separadas()).
Item sem custo: entra em vendas, unidades, bruto e liquido, fica fora do custo e do lucro e soma em sem_custo_un (aviso na tela).

Linha de comando (le o banco, nao chama a API), na raiz do repositorio:
    python -m painel.nucleo.resumo <TPP|PD|TODAS> <AAAA-MM-DD> <AAAA-MM-DD> [--excel <pasta>]
"""
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime

from painel.nucleo.modelos import ResultadoItem, ResumoAnuncio, ResumoPeriodo, Situacao

FORMULAS = [
    ("Líquido", "bruto − reembolso ao comprador − tarifa de venda − frete do vendedor (= Total do relatório de vendas do ML)"),
    ("Item de carrinho", "receita, tarifa e frete do pedido rateados pelo bruto de cada item"),
    ("Custo", "custo da tabela × unidades do kit (+ brinde nos combos) × quantidade, sem rebate"),
    ("Rebate", "custo sem rebate − custo com rebate (só produtos com aplica_rebate = sim)"),
    ("Lucro antes do imposto", "líquido − custo + rebate"),
    ("Imposto", "bruto × débito % − custo da mercadoria × crédito % (crédito 0 no Simples)"),
    ("Lucro depois do imposto", "lucro antes do imposto − imposto"),
    ("Margem", "lucro depois do imposto ÷ líquido (só itens com custo)"),
    ("Totais", "só vendas válidas; canceladas e devolvidas à parte, sem custo de mercadoria"),
]


def _somar(r, x: ResultadoItem, pedidos: set) -> None:
    if x.venda_id not in pedidos:   # carrinho (varios pedidos no mesmo pacote) = 1 venda, como no relatorio do ML
        pedidos.add(x.venda_id)
        r.vendas += 1
    r.unidades += x.unidades
    r.liquido = round(r.liquido + x.liquido, 2)
    if hasattr(r, "bruto"):
        r.bruto = round(r.bruto + x.bruto, 2)
    if x.custo is None:
        r.sem_custo_un += x.unidades
        return
    r._liquido_com_custo = round(r._liquido_com_custo + x.liquido, 2)
    r.lucro_depois_imposto = round(r.lucro_depois_imposto + (x.lucro_depois_imposto or 0), 2)
    if isinstance(r, ResumoAnuncio):
        return
    r.custo = round(r.custo + x.custo, 2)
    r.rebate = round(r.rebate + x.rebate, 2)
    r.imposto = round(r.imposto + x.imposto, 2)
    r.lucro_antes_imposto = round(r.lucro_antes_imposto + (x.lucro_antes_imposto or 0), 2)
    if x.lucro_com_rebate is not None:
        r.lucro_com_rebate = round((r.lucro_com_rebate or 0) + x.lucro_com_rebate, 2)


def validas(linhas: list[ResultadoItem]) -> list[ResultadoItem]:
    return [x for x in linhas if x.situacao == Situacao.VALIDA]


def separadas(linhas: list[ResultadoItem]) -> list[ResultadoItem]:
    return [x for x in linhas if x.situacao != Situacao.VALIDA]


def _agrupar(linhas, chave, novo) -> dict:
    g, peds = {}, defaultdict(set)
    for x in validas(linhas):
        k = chave(x)
        if k not in g:
            g[k] = novo(x, k)
        _somar(g[k], x, peds[k])
    return g


def por_mes(linhas: list[ResultadoItem]) -> list[ResumoPeriodo]:
    """Conta x AAAA-MM em ordem, com acumulado do lucro depois do imposto dentro de cada conta."""
    g = _agrupar(linhas, lambda x: (x.conta, x.data.strftime("%Y-%m")), lambda x, k: ResumoPeriodo(*k))
    acum: dict[str, float] = defaultdict(float)
    out = []
    for k in sorted(g):
        r = g[k]
        acum[r.conta] = round(acum[r.conta] + r.lucro_depois_imposto, 2)
        r.acumulado = acum[r.conta]
        out.append(r)
    return out


def por_produto(linhas: list[ResultadoItem]) -> list[ResumoPeriodo]:
    """Conta x produto (periodo = nome do produto; '(sem produto)' quando o titulo nao classifica), do maior lucro ao menor."""
    g = _agrupar(linhas, lambda x: (x.conta, x.produto or "(sem produto)"), lambda x, k: ResumoPeriodo(*k))
    return sorted(g.values(), key=lambda r: (r.conta, -r.lucro_depois_imposto))


def por_anuncio(linhas: list[ResultadoItem]) -> list[ResumoAnuncio]:
    """Conta x anuncio, do maior lucro ao menor (titulo e tipo da venda mais recente do anuncio)."""
    recentes = sorted(validas(linhas), key=lambda x: x.data, reverse=True)
    g = _agrupar(recentes, lambda x: (x.conta, x.anuncio_id),
                 lambda x, k: ResumoAnuncio(x.conta, x.anuncio_id, x.titulo, x.tipo_anuncio, x.produto))
    return sorted(g.values(), key=lambda r: (r.conta, -r.lucro_depois_imposto))


def total(linhas: list[ResultadoItem], conta: str = "Total") -> ResumoPeriodo:
    """Uma linha com a soma das vendas validas (linha de total das tabelas e coluna "As duas" da Visao geral)."""
    r = ResumoPeriodo(conta, "total")
    peds: set = set()
    for x in validas(linhas):
        _somar(r, x, peds)
    return r


# ---- abas do Excel (docs/TELAS.md, secao 5) ----
def tabela(linhas: list[ResumoPeriodo], periodo: str, tirar: tuple = ()) -> list[dict]:
    """Resumo como tabela: 'periodo' com o nome certo ("Mês" ou "Produto"), margem depois do lucro, sem os campos internos."""
    out = []
    for r in linhas:
        d = {}
        for k, v in asdict(r).items():
            if k.startswith("_") or k in tirar:
                continue
            d[periodo if k == "periodo" else k] = v
            if k == "lucro_depois_imposto":
                d["margem_pct"] = r.margem_pct()
        out.append(d)
    return out


def _data_br(txt: str | None) -> str:
    try:
        return datetime.fromisoformat(txt).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return txt or "—"


def aba_custos(par) -> list[dict]:
    return [{"Produto": c.produto, "Custo unitário sem rebate": c.custo_unit, "Fonte": c.fonte,
             "Aplica rebate": "sim" if c.aplica_rebate else "não", "Situação": "pendente" if c.pendente() else "ok"}
            for c in par.custos()]


def aba_rebate(linhas: list[ResultadoItem], par) -> list[dict]:
    pct, cmp = par.rebate_pct(), par.rebate_comparacao()
    out = []
    for r in por_produto(linhas):
        d = {"Conta": r.conta, "Produto": r.periodo, "Unidades": r.unidades, "Rebate usado (%)": pct,
             "Rebate no lucro (R$)": r.rebate}
        if cmp is not None:
            d["Rebate de comparação (%)"] = cmp
            d["Lucro antes com rebate de comparação (R$)"] = r.lucro_com_rebate
        out.append(d)
    return out


def aba_imposto(par) -> list[dict]:
    return [{"Conta": r.conta, "Regime": r.regime, "Produto (exceção)": r.produto or "(padrão da conta)",
             "Débito % do preço": r.debito_pct, "Crédito % do custo": r.credito_pct,
             "Situação": "pendente" if r.pendente() else "ok", "Origem": r.origem} for r in par.regras_imposto()]


def aba_premissas(par, contas: list[str], de: date, ate: date, atualizado: dict) -> list[dict]:
    L = [("Contas", ", ".join(contas)), ("Período", f"{de:%d/%m/%Y} a {ate:%d/%m/%Y}"),
         ("Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M"))]
    L += [(f"Dados até ({c})", _data_br(atualizado.get(c))) for c in contas]
    cmp = par.rebate_comparacao()
    L.append(("Rebate no cálculo principal", f"{par.rebate_pct():g}%"))
    if cmp is not None:
        L.append(("Rebate de comparação", f"{cmp:g}%"))
    L += [(f"Fórmula: {n}", f) for n, f in FORMULAS]
    pend = [c.produto for c in par.custos() if c.pendente()]
    if pend:
        L.append(("Pendente: custo", ", ".join(pend)))
    for c in contas:
        if par.regra_imposto(c).pendente():
            L.append(("Pendente: imposto", f"{c} sem alíquota (lucro depois do imposto = antes)"))
    return [{"Item": a, "Valor": b} for a, b in L]


def abas_excel(linhas: list[ResultadoItem], par, contas: list[str], de: date, ate: date, atualizado: dict) -> dict[str, list]:
    """Dicionario aba -> linhas para exportar.para_excel (ordem de docs/TELAS.md, secao 5)."""
    return {"Resumo": tabela(por_mes(linhas), "Mês"), "Por produto": tabela(por_produto(linhas), "Produto", ("acumulado",)),
            "Por anúncio": por_anuncio(linhas),
            "Vendas": validas(linhas), "Canceladas e devolvidas": separadas(linhas), "Custos": aba_custos(par),
            "Rebate": aba_rebate(linhas, par), "Imposto": aba_imposto(par),
            "Premissas": aba_premissas(par, contas, de, ate, atualizado)}


def nome_arquivo(contas: list[str], de: date, ate: date) -> str:
    return f"vendas-ml_{'-'.join(contas)}_{de.isoformat()}_{ate.isoformat()}.xlsx"


def main(argv=None) -> int:
    import argparse
    from pathlib import Path

    from painel.nucleo import exportar
    from painel.nucleo.calculo import CalculadoraLucro
    from painel.nucleo.repositorio import RepositorioParametros, RepositorioPedidos

    a = argparse.ArgumentParser(description="Resumo de vendas e lucro do banco (nao chama a API).")
    a.add_argument("conta", choices=["TPP", "PD", "TODAS"])
    a.add_argument("de", type=date.fromisoformat)
    a.add_argument("ate", type=date.fromisoformat)
    a.add_argument("--excel", type=Path, help="pasta onde gravar o Excel")
    o = a.parse_args(argv)
    contas = ["TPP", "PD"] if o.conta == "TODAS" else [o.conta]
    repo, par = RepositorioPedidos(), RepositorioParametros()
    if not repo.existe():
        print(f"Banco nao encontrado: {repo.banco}")
        return 1
    calc = CalculadoraLucro(par)
    linhas = [r for c in contas for r in calc.resultados(repo.pedidos(c, o.de, o.ate))]

    def brl(v):
        return "—" if v is None else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    for r in por_mes(linhas) + [total(linhas)]:
        m = r.margem_pct()
        print(f"{r.conta:5} {r.periodo:8} vendas {r.vendas:5} un {r.unidades:5} liquido {brl(r.liquido):>15} "
              f"lucro antes {brl(r.lucro_antes_imposto):>14} depois {brl(r.lucro_depois_imposto):>14} "
              f"margem {'—' if m is None else f'{m:.1f}%':>6} sem custo {r.sem_custo_un} un")
    sep = separadas(linhas)
    print(f"canceladas/devolvidas: {len(sep)} itens, liquido {brl(round(sum(x.liquido for x in sep), 2))}")
    if o.excel:
        arq = o.excel / nome_arquivo(contas, o.de, o.ate)
        atualizado = {c: repo.ultima_atualizacao(c) for c in contas}
        arq.write_bytes(exportar.para_excel(abas_excel(linhas, par, contas, o.de, o.ate, atualizado)))
        print(f"Excel: {arq}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
