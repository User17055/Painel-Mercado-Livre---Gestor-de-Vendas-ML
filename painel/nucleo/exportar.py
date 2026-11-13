# -*- coding: utf-8 -*-
"""Download em CSV e Excel. Recebe linhas prontas (dataclasses ou dicts); nao calcula nada.

CSV: separador ';', utf-8-sig (abre certo no Excel brasileiro), decimal com virgula.
Excel: uma aba por tabela (resumo.abas_excel), fonte Arial,
cabecalho em negrito, primeira linha congelada. Sem formula (valores ja calculados pelo nucleo): nada para quebrar ao abrir.
"""
import csv
import io
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum

AUTOR = "TI SF"
FONTE = "Arial"


ROTULOS = {  # cabecalho das colunas (campo do nucleo -> nome na planilha); campo fora da lista sai com o proprio nome
    "conta": "Conta", "periodo": "Período", "data": "Data", "pedido_id": "Pedido", "anuncio_id": "Anúncio",
    "titulo": "Título", "produto": "Produto", "tipo_anuncio": "Tipo", "vendas": "Vendas", "unidades": "Unidades",
    "bruto": "Bruto", "tarifa": "Tarifa", "frete": "Frete", "liquido": "Líquido", "custo": "Custo", "rebate": "Rebate",
    "lucro_antes_imposto": "Lucro antes do imposto", "lucro_com_rebate": "Lucro antes com rebate (comparação)",
    "imposto": "Imposto", "lucro_depois_imposto": "Lucro depois do imposto", "margem_pct": "Margem (%)",
    "acumulado": "Acumulado", "sem_custo_un": "Unidades sem custo", "situacao": "Situação", "avisos": "Avisos",
}


def _valor(v):
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, list):
        return "; ".join(v)
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)   # Excel nao aceita fuso; a data ja vem no horario de Brasilia
    return v


def _como_dict(x) -> dict:
    """Campos na ordem do modelo, sem os internos (comecam com _), margem depois do lucro e cabecalho em portugues."""
    d = asdict(x) if is_dataclass(x) else dict(x)
    if hasattr(x, "margem_pct"):
        d2 = {}
        for k, v in d.items():
            d2[k] = v
            if k == "lucro_depois_imposto":
                d2["margem_pct"] = x.margem_pct()
        d = d2
    return {ROTULOS.get(k, k): _valor(v) for k, v in d.items() if not k.startswith("_")}


def _celula_csv(v):
    if isinstance(v, float):
        return f"{v:.2f}".replace(".", ",")
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M")
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
                if isinstance(c.value, datetime):
                    c.number_format = "dd/mm/yyyy hh:mm"
        ws.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
