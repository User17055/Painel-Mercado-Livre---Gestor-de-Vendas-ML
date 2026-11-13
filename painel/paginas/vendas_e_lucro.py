# -*- coding: utf-8 -*-
"""Pagina 2, Vendas e lucro (docs/TELAS.md, secao 4): abas Por mes, Por produto, Por anuncio, Vendas e Canceladas e devolvidas.
Total na ultima linha; ordenar clicando no cabecalho; "expandir" = escolher mes, produto ou anuncio e ver as vendas na aba Vendas."""
import streamlit as st

from painel import tela
from painel.nucleo import formato, resumo

st.title("Vendas e lucro")
contas, de, ate = tela.filtros()
repo = tela.exigir_banco()
par = tela.parametros()
L = tela.linhas(contas, de, ate)

ANTES, COM = tela.rotulo_lucro_antes(par), tela.rotulo_com_rebate(par)
LUCRO = [("lucro_antes_imposto", ANTES, "brl")] + ([("lucro_com_rebate", COM, "brl")] if COM else []) + [
    ("imposto", "Imposto", "brl"), ("lucro_depois_imposto", "Lucro depois", "brl")]
RESUMO = [("vendas", "Vendas", "int"), ("unidades", "Unidades", "int"), ("bruto", "Bruto", "brl"), ("liquido", "Líquido", "brl"),
          ("custo", "Custo", "brl"), ("rebate", "Rebate", "brl")] + LUCRO + [("margem_pct", "Margem", "pct")]
VENDAS = [("data", "Data", "data"), ("conta", "Conta", "txt"), ("pedido_id", "Pedido", "txt"), ("venda_id", "Venda", "txt"),
("anuncio_id", "Anúncio", "txt"),
          ("titulo", "Título", "txt"), ("produto", "Produto", "txt"), ("tipo_anuncio", "Tipo", "txt"),
          ("unidades", "Unid.", "int"), ("bruto", "Bruto", "brl"), ("tarifa", "Tarifa", "brl"), ("frete", "Frete", "brl"),
          ("liquido", "Líquido", "brl"), ("custo", "Custo", "brl"), ("rebate", "Rebate", "brl")] + LUCRO + [
          ("avisos", "Avisos", "txt")]


def total_de(linhas_) -> dict:
    """Linha de total pelo nucleo (resumo.total): so vendas validas, como os totais da tela."""
    t = resumo.total(linhas_)
    d = {k: getattr(t, k) for k in ("vendas", "unidades", "bruto", "liquido", "custo", "rebate", "lucro_antes_imposto",
                                    "lucro_com_rebate", "imposto", "lucro_depois_imposto", "sem_custo_un")}
    d["margem_pct"] = t.margem_pct()
    d["conta"] = "Total"
    return d


def linhas_vendas(xs) -> list[dict]:
    return [{**x.__dict__, "avisos": "; ".join(x.avisos), "situacao": x.situacao.value} for x in xs]


for a in tela.avisos_pendencia(L, par, contas):
    st.warning(a)

aba_mes, aba_prod, aba_anun, aba_vendas, aba_canc = st.tabs(
    ["Por mês", "Por produto", "Por anúncio", "Vendas", "Canceladas e devolvidas"])

with aba_mes:
    tela.tabela(resumo.por_mes(L), [("conta", "Conta", "txt"), ("periodo", "Mês", "txt")] + RESUMO
                + [("acumulado", "Acumulado", "brl"), ("sem_custo_un", "Un. sem custo", "int")], total=total_de(L))

with aba_prod:
    tela.tabela(resumo.por_produto(L), [("conta", "Conta", "txt"), ("periodo", "Produto", "txt")] + RESUMO
                + [("sem_custo_un", "Un. sem custo", "int")], total=total_de(L))

with aba_anun:
    busca = st.text_input("Buscar (anúncio ou título)", key="busca_anuncio").strip().lower()
    an = [r for r in resumo.por_anuncio(L) if not busca or busca in r.anuncio_id.lower() or busca in r.titulo.lower()]
    escolhidos = {(r.conta, r.anuncio_id) for r in an}
    tela.tabela(an, [("conta", "Conta", "txt"), ("anuncio_id", "Anúncio", "txt"), ("titulo", "Título", "txt"),
                     ("tipo_anuncio", "Tipo", "txt"), ("produto", "Produto", "txt"), ("vendas", "Vendas", "int"),
                     ("unidades", "Unidades", "int"), ("liquido", "Líquido", "brl"),
                     ("lucro_depois_imposto", "Lucro depois", "brl"), ("margem_pct", "Margem", "pct")],
                total=total_de([x for x in L if (x.conta, x.anuncio_id) in escolhidos]))

with aba_vendas:
    val = resumo.validas(L)
    c1, c2, c3, c4 = st.columns(4)
    meses = sorted({x.data.strftime("%Y-%m") for x in val})
    m = c1.selectbox("Mês", ["Todos"] + meses, format_func=lambda v: v if v == "Todos" else formato.mes(v))
    p = c2.selectbox("Produto", ["Todos"] + sorted({x.produto or "(sem produto)" for x in val}))
    a = c3.selectbox("Anúncio", ["Todos"] + sorted({x.anuncio_id for x in val}))
    busca = c4.text_input("Buscar (pedido, venda, anúncio, título)").strip().lower()
    sel = [x for x in val if (m == "Todos" or x.data.strftime("%Y-%m") == m)
           and (p == "Todos" or (x.produto or "(sem produto)") == p) and (a == "Todos" or x.anuncio_id == a)
           and (not busca or busca in x.pedido_id or busca in x.venda_id or busca in x.anuncio_id.lower() or busca in x.titulo.lower())]
    sel.sort(key=lambda x: x.data, reverse=True)
    tot = total_de(sel) | {"tarifa": round(sum(x.tarifa for x in sel), 2), "frete": round(sum(x.frete for x in sel), 2)}
    st.caption(f"{formato.inteiro(len(sel))} itens em {formato.inteiro(tot['vendas'])} vendas. "
               "No total, custo e lucro somam só os itens com custo.")
    tela.tabela(linhas_vendas(sel), VENDAS, total=tot, altura=600)

with aba_canc:
    sep = sorted(resumo.separadas(L), key=lambda x: x.data, reverse=True)
    st.caption("Ficam fora dos totais. O líquido pode ser negativo: frete e devolução que o vendedor pagou. "
               "Sem custo de mercadoria (o produto volta ao estoque).")
    tot = {"conta": "Total", "unidades": sum(x.unidades for x in sep)}
    tot |= {k: round(sum(getattr(x, k) for x in sep), 2) for k in ("bruto", "tarifa", "frete", "liquido")}
    tela.tabela(linhas_vendas(sep), VENDAS[:13] + [("situacao", "Situação", "txt"), ("avisos", "Avisos", "txt")], total=tot)

tela.rodape(repo, par, contas)
