# -*- coding: utf-8 -*-
"""Formato brasileiro para a tela (docs/TELAS.md, secao 1): R$ 1.234,56; 12,3%; dd/mm/aaaa; negativo com o sinal "−".
So texto: nenhuma conta de negocio aqui."""
from datetime import date, datetime

MENOS = "−"   # sinal de menos de verdade (o "-" do teclado some no meio do texto)
VAZIO = "—"


def _milhar(v: float, casas: int) -> str:
    return f"{abs(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v) -> str:
    if v is None:
        return VAZIO
    return f"{MENOS if v < 0 else ''}R$ {_milhar(v, 2)}"


def pct(v) -> str:
    if v is None:
        return VAZIO
    return f"{MENOS if v < 0 else ''}{_milhar(v, 1)}%"


def inteiro(v) -> str:
    if v is None:
        return VAZIO
    return f"{MENOS if v < 0 else ''}{_milhar(v, 0)}"


def data(v) -> str:
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    return VAZIO if v is None else str(v)


def data_hora(v) -> str:
    """datetime ou texto ISO (ex.: fim da execucao gravado pelo coletor) -> dd/mm/aaaa hh:mm."""
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v)
        except ValueError:
            return v
    return v.strftime("%d/%m/%Y %H:%M") if isinstance(v, datetime) else VAZIO


def negativo(texto: str) -> bool:
    return isinstance(texto, str) and texto.startswith(MENOS)


MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
         "dezembro")


def mes(am: str) -> str:
    """'2026-11' -> 'Novembro/2026'."""
    a, m = am.split("-")
    return f"{MESES[int(m) - 1].capitalize()}/{a}"
