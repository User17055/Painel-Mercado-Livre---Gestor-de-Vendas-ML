# -*- coding: utf-8 -*-
"""Download em CSV e Excel. Recebe linhas prontas (dataclasses ou dicts); nao calcula nada.

CSV: separador ';', utf-8-sig (abre certo no Excel brasileiro), decimal com virgula.
Excel: uma aba por tabela (Resumo, Por produto, Vendas, Custos, Rebate, Imposto, Premissas), fonte Arial
cabecalho em negrito, primeira linha congelada. Sem formula (valores ja calculados pelo nucleo): nada para quebrar ao abrir.
"""
import csv
import io
from dataclasses import asdict, is_dataclass
from enum import Enum

AUTOR = "TI SF"
FONTE = "Arial"


def _como_dict(x) -> dict:
    d = asdict(x) if is_dataclass(x) else dict(x)
    return {k: (v.value if isinstance(v, Enum) else "; ".join(v) if isinstance(v, list) else v) for k, v in d.items()}


def _celula_csv(v):
    if isinstance(v, float):
        return f"{v:.2f}".replace(".", ",")
    return "" if v is None else v


def para_csv(linhas) -> bytes:
    """Bytes do CSV (para st.download_button ou para gravar em arquivo)."""
    rows = [_como_dict(x) for x in linhas]
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow({k: _celula_csv(v) for k, v in r.items()})
    return buf.getvalue().encode("utf-8-sig")


def para_excel(abas: dict[str, list]) -> bytes:
    """Bytes do .xlsx com uma aba por chave do dicionario (nome da aba -> linhas)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.creator = AUTOR
    wb.properties.lastModifiedBy = AUTOR
    normal, negrito = Font(name=FONTE, size=10), Font(name=FONTE, size=10, bold=True)
    for nome, linhas in abas.items():
        ws = wb.create_sheet(nome[:31])
        rows = [_como_dict(x) for x in linhas]
        if not rows:
            ws.append(["(sem dados)"])
            continue
        ws.append(list(rows[0]))
        for r in rows:
            ws.append([("" if v is None else v) for v in r.values()])
        for linha in ws.iter_rows():
            for c in linha:
                c.font = negrito if c.row == 1 else normal
        ws.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
