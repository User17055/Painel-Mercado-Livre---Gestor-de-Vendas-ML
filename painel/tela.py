# -*- coding: utf-8 -*-
"""Pecas comuns das tres paginas (Streamlit): filtros da barra lateral, leitura com cache, tabela formatada e rodape.

A tela so filtra, ordena e mostra: o calculo e do nucleo (painel/nucleo). Especificacao: docs/TELAS.md.
"""
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from painel.nucleo import caminhos, formato, resumo
from painel.nucleo.calculo import CalculadoraLucro
from painel.nucleo.repositorio import RepositorioParametros, RepositorioPedidos

CONTAS = ("TPP", "PD")
OPCOES_CONTA = {"As duas": ["TPP", "PD"], "TPP": ["TPP"], "PD": ["PD"]}
ATALHOS = ("Ano até hoje", "Mês atual", "Mês anterior", "Escolher datas")
ARQ_PARAMETROS = ("ml_parametros.json", "custos_produtos.csv")


def md(texto: str) -> str:
    """Texto com valor em reais para st.caption/st.write: sem escapar, dois "R$" viram formula matematica (LaTeX)."""
    return texto.replace("$", "\\$")


def _marca(*arquivos) -> tuple:
    """Data de modificacao dos arquivos: muda quando o banco ou os parametros mudam (e so ai o cache rele)."""
    return tuple(a.stat().st_mtime if a.exists() else 0 for a in arquivos)


def _marca_dados() -> tuple:
    return _marca(caminhos.BANCO_VENDAS, *(caminhos.CONFIG / f for f in ARQ_PARAMETROS))


@st.cache_resource(show_spinner=False)
def _parametros(marca: tuple) -> RepositorioParametros:
    return RepositorioParametros()


def parametros() -> RepositorioParametros:
    return _parametros(_marca_dados())


@st.cache_data(show_spinner="Lendo as vendas...")
def _linhas(contas: tuple, de: date, ate: date, marca: tuple) -> list:
    repo, calc = RepositorioPedidos(), CalculadoraLucro(_parametros(marca))
    return [r for c in contas for r in calc.resultados(repo.pedidos(c, de, ate))]


def linhas(contas, de: date, ate: date) -> list:
    """Linhas (ResultadoItem) das contas no periodo; cache ate o banco ou os parametros mudarem."""
    return _linhas(tuple(contas), de, ate, _marca_dados())


def _periodo(atalho: str, hoje: date) -> tuple[date, date]:
    if atalho == "Mês atual":
        return hoje.replace(day=1), hoje
    if atalho == "Mês anterior":
        fim = hoje.replace(day=1) - timedelta(days=1)
        return fim.replace(day=1), fim
    return date(hoje.year, 1, 1), hoje


def _guardar(chave_widget: str, chave: str):
    st.session_state[chave] = st.session_state[chave_widget]


def filtros() -> tuple[list[str], date, date]:
    """Barra lateral: conta e periodo (docs/TELAS.md, secao 2). O valor fica guardado ao trocar de pagina."""
    hoje = date.today()
    ss = st.session_state
    ss.setdefault("f_conta", "As duas")
    ss.setdefault("f_atalho", ATALHOS[0])
    ss.setdefault("f_de", date(hoje.year, 1, 1))
    ss.setdefault("f_ate", hoje)
    with st.sidebar:
        st.header("Filtros")
        st.radio("Conta", list(OPCOES_CONTA), index=list(OPCOES_CONTA).index(ss.f_conta), key="w_conta",
                 on_change=_guardar, args=("w_conta", "f_conta"))
        st.selectbox("Período", ATALHOS, index=ATALHOS.index(ss.f_atalho), key="w_atalho",
                     on_change=_guardar, args=("w_atalho", "f_atalho"))
        if ss.f_atalho == "Escolher datas":
            st.date_input("De", value=ss.f_de, format="DD/MM/YYYY", key="w_de", on_change=_guardar, args=("w_de", "f_de"))
            st.date_input("Até", value=ss.f_ate, format="DD/MM/YYYY", key="w_ate", on_change=_guardar, args=("w_ate", "f_ate"))
            de, ate = ss.f_de, ss.f_ate
        else:
            de, ate = _periodo(ss.f_atalho, hoje)
        st.caption(f"{formato.data(de)} a {formato.data(ate)}")
    if de > ate:
        st.error("A data inicial é depois da final.")
        st.stop()
    return OPCOES_CONTA[ss.f_conta], de, ate


def exigir_banco() -> RepositorioPedidos:
    """Sem banco de pedidos: aviso e como gravar; nenhuma tabela (docs/TELAS.md, secao 6)."""
    repo = RepositorioPedidos()
    if not repo.existe():
        st.info("Ainda sem vendas pela API: o banco de pedidos não existe. Gravar com "
                "`python ml_pedidos.py <CONTA> --desde AAAA-MM-DD --gravar` (pasta `analise`).")
        st.stop()
    if not all((caminhos.CONFIG / f).exists() for f in ARQ_PARAMETROS):
        st.warning("Sem os arquivos de parâmetros (custo e imposto): vendas e líquido normais; custo e imposto pendentes em tudo.")
    return repo


def rotulo_lucro_antes(par) -> str:
    pct = par.rebate_pct()
    return "Lucro antes" + (f" (rebate {pct:g}%)" if pct else (" (sem rebate)" if par.rebate_comparacao() is not None else ""))


def rotulo_com_rebate(par) -> str | None:
    cmp = par.rebate_comparacao()
    return None if cmp is None else f"Lucro antes (com rebate {cmp:g}%)"


def _vermelho(v):
    return "color: #c62828" if isinstance(v, (int, float)) and not isinstance(v, bool) and v < 0 else ""


def tabela(linhas_, colunas: list[tuple[str, str, str]], total: dict | None = None, altura: int | None = None) -> None:
    """Mostra uma tabela: colunas = [(campo, rotulo, tipo)] com tipo 'brl', 'pct', 'int', 'data' ou 'txt'.
    O valor fica numerico (ordenar pelo cabecalho funciona) e so a exibicao vira formato brasileiro; negativo em vermelho
    e com o sinal "−". total = linha de total (campo -> valor), mostrada por ultimo."""
    if not linhas_:
        st.info("Nenhuma venda no período.")
        return
    regs = []
    for x in linhas_:
        d = asdict(x) if is_dataclass(x) else dict(x)
        if hasattr(x, "margem_pct"):
            d["margem_pct"] = x.margem_pct()
        regs.append({rot: d.get(campo) for campo, rot, _ in colunas})
    if total:
        regs.append({rot: total.get(campo) for campo, rot, _ in colunas})
    df = pd.DataFrame(regs)
    fmt = {"brl": formato.brl, "pct": formato.pct, "int": formato.inteiro, "data": formato.data}
    formatos = {rot: (lambda v, f=fmt[t]: formato.VAZIO if v is None or pd.isna(v) else f(v))   # vazio: None, NaN ou NaT
                for _, rot, t in colunas if t in fmt}
    for _, rot, t in colunas:
        if t == "txt":
            df[rot] = df[rot].fillna("")
    numericas = [rot for _, rot, t in colunas if t in ("brl", "pct", "int")]
    estilo = df.style.format(formatos).map(_vermelho, subset=numericas)
    st.dataframe(estilo, hide_index=True, use_container_width=True, height=altura)


def rodape(repo: RepositorioPedidos, par, contas) -> None:
    """Dados ate <data> por conta (em destaque se tiver mais de 1 dia) e as premissas em uma linha."""
    partes, velho = [], False
    for c in contas:
        u = repo.ultima_atualizacao(c)
        partes.append(f"{formato.data_hora(u) if u else formato.VAZIO} ({c})")
        try:
            velho |= datetime.now() - datetime.fromisoformat(u).replace(tzinfo=None) > timedelta(days=1)
        except (TypeError, ValueError):
            velho = True
    cmp = par.rebate_comparacao()
    reb = f"rebate {par.rebate_pct():g}%" + (f" (comparação {cmp:g}%)" if cmp is not None else "")
    st.divider()
    texto = "Dados até " + " · ".join(partes)
    if velho:
        st.warning(texto + ": atualize.")
    else:
        st.caption(texto)
    st.caption(f"Premissas: {reb}; imposto: " + "; ".join(par.regra_imposto(c).origem for c in contas))


def avisos_pendencia(L, par, contas) -> list[str]:
    """Avisos que acompanham qualquer total de lucro (docs/TELAS.md, secao 1)."""
    out = [f"{c}: imposto pendente (lucro depois = antes)." for c in contas if par.regra_imposto(c).pendente()]
    sem = resumo.total(L).sem_custo_un
    if sem:
        out.append(f"{formato.inteiro(sem)} unidades sem custo (fora do lucro).")
    return out
