# -*- coding: utf-8 -*-
"""ml_pedidos.py: vendas pela API (pedidos), SO LEITURA e SEM DADO DE COMPRADOR. Base do painel (docs\\ARQUITETURA.md).

Regra: so os campos necessarios ao lucro. Como garante: LISTA FECHADA. O coletor copia apenas as chaves de CAMPOS_*
  (abaixo); tudo o que nao esta na lista (comprador, apelido, destinatario, endereco, telefone, documento) e descartado
  na leitura: nao e gravado nem mostrado.
  painel\\nucleo\\conferencia.sem_comprador
  confere o banco.

Fontes (documentacao do ML; ainda nao validado com dado real):
  pedidos   GET /orders/search?seller=<id>&order.date_closed.from=..&order.date_closed.to=..&sort=date_asc  (50 por pagina;
            so os ultimos 12 meses; a busca do vendedor esconde cancelados)
  frete     GET /shipments/<id>/costs  (cabecalho x-format-new: true)  -> senders[].cost = o que o vendedor pagou
  cobranca  GET /billing/integration/group/ML/order/details?order_ids=a,b,..  (ate 60 por chamada) -> tarifa, frete, descontos
Liquido por item = preco x quantidade - tarifa - frete rateado (a conta fica em painel\\nucleo\\calculo.py).

Uso (pasta analise\\):
  python ml_pedidos.py criar-banco                     # cria dados\\vendas_api.db vazio (esquema abaixo)
  python ml_pedidos.py <CONTA> --desde AAAA-MM-DD       # (fase 1a) le os pedidos e mostra o resumo, sem gravar
  python ml_pedidos.py <CONTA> --desde AAAA-MM-DD --gravar   # (fase 1a) grava no banco (incremental: so o que falta)
Parametros: ml_parametros.json > pedidos (inicio, lote_cobranca, por_pagina).
"""
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # py -I nao inclui a pasta do script
import ml_param  # noqa: E402

BANCO = ml_param.DIR_DADOS / "vendas_api.db"

# --- LISTA FECHADA: coluna do banco -> caminho no JSON do ML. So isto entra. ------------------------------------------------
CAMPOS_PEDIDO = {
    "pedido_id": ("id",), "pack_id": ("pack_id",), "criado_em": ("date_created",), "fechado_em": ("date_closed",),
    "status": ("status",), "tags": ("tags",), "total": ("total_amount",), "cupom": ("coupon", "amount"),
    "envio_id": ("shipping", "id"),
}
CAMPOS_ITEM = {
    "anuncio_id": ("item", "id"), "variacao_id": ("item", "variation_id"), "sku": ("item", "seller_sku"),
    "titulo": ("item", "title"), "quantidade": ("quantity",), "preco_unit": ("unit_price",),
    "tarifa_unit": ("sale_fee",), "tipo_anuncio": ("listing_type_id",),
}

ESQUEMA = {
    "pedidos": ["conta", *CAMPOS_PEDIDO, "coletado_em"],
    "pedido_itens": ["conta", "pedido_id", "seq", *CAMPOS_ITEM],
    "envios": ["conta", "envio_id", "pedido_id", "custo_vendedor", "custo_bruto"],
    "cobrancas": ["conta", "pedido_id", "tipo", "seq", "valor", "descricao"],
    "execucoes": ["id", "conta", "tipo", "inicio", "fim", "pedidos_novos", "chamadas", "erros"],
}
CHAVES = {
    "pedidos": "PRIMARY KEY (conta, pedido_id)",
    "pedido_itens": "PRIMARY KEY (conta, pedido_id, seq)",
    "envios": "PRIMARY KEY (conta, envio_id)",
    "cobrancas": "PRIMARY KEY (conta, pedido_id, tipo, seq)",
    "execucoes": "",
}
TIPOS = {"id": "INTEGER PRIMARY KEY AUTOINCREMENT", "seq": "INTEGER", "quantidade": "INTEGER", "pedidos_novos": "INTEGER",
         "chamadas": "INTEGER", "erros": "INTEGER", "total": "REAL", "cupom": "REAL", "preco_unit": "REAL", "tarifa_unit": "REAL",
         "custo_vendedor": "REAL", "custo_bruto": "REAL", "valor": "REAL"}


def colunas_permitidas() -> dict[str, set[str]]:
    """Tabela -> colunas que podem existir no banco (usada por painel\\nucleo\\conferencia.sem_comprador)."""
    return {t: set(c) for t, c in ESQUEMA.items()} | {"sqlite_sequence": {"name", "seq"}}   # tabela interna do AUTOINCREMENT


def _pegar(d, caminho):
    for k in caminho:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def filtrar_pedido(conta: str, pedido: dict) -> tuple[dict, list[dict]]:
    """JSON de um pedido do ML -> (linha de 'pedidos', linhas de 'pedido_itens'), SO com a lista fechada.
    Copia campo a campo pelo caminho: o resto do JSON e descartado aqui, antes de qualquer gravacao."""
    linha = {"conta": conta, **{col: _pegar(pedido, cam) for col, cam in CAMPOS_PEDIDO.items()},
             "coletado_em": datetime.now().isoformat(timespec="seconds")}
    if isinstance(linha["tags"], list):
        linha["tags"] = ",".join(str(t) for t in linha["tags"])
    itens = []
    for seq, it in enumerate(pedido.get("order_items") or [], 1):
        itens.append({"conta": conta, "pedido_id": linha["pedido_id"], "seq": seq,
                      **{col: _pegar(it, cam) for col, cam in CAMPOS_ITEM.items()}})
    return linha, itens


def criar_banco(banco: Path = BANCO) -> Path:
    """Cria as tabelas que faltam (idempotente). Nao apaga nada."""
    banco = Path(banco)
    banco.parent.mkdir(parents=True, exist_ok=True)
    # closing(): "with sqlite3.connect()" so faz commit, NAO fecha (no Windows o arquivo fica preso)
    with closing(sqlite3.connect(banco)) as con, con:
        for tab, cols in ESQUEMA.items():
            defs = [f"{c} {TIPOS.get(c, 'TEXT')}" for c in cols] + ([CHAVES[tab]] if CHAVES[tab] else [])
            con.execute(f"CREATE TABLE IF NOT EXISTS {tab} ({', '.join(defs)})")
    return banco


# --- chamadas a API (fase 1a): todas por Coleta.get (so GET) -------------------------------------------------------------------
def buscar_pedidos(c, desde: str, ate: str | None = None) -> list[dict]:
    """Pagina /orders/search do vendedor no periodo (data de fechamento) e devolve as linhas ja filtradas."""
    raise NotImplementedError("fase 1a")


def buscar_fretes(c, envio_ids: list[str]) -> list[dict]:
    """/shipments/<id>/costs de cada envio -> linhas de 'envios' (custo do vendedor e bruto)."""
    raise NotImplementedError("fase 1a")


def buscar_cobrancas(c, pedido_ids: list[str], lote: int = 60) -> list[dict]:
    """/billing/integration/group/ML/order/details em lotes -> linhas de 'cobrancas' (tipo, valor, descricao)."""
    raise NotImplementedError("fase 1a")


def gravar(banco: Path, pedidos: list[dict], itens: list[dict], envios: list[dict], cobrancas: list[dict]) -> int:
    """Grava/atualiza (upsert) e devolve quantos pedidos novos. Status muda (ex.: devolucao): a linha e atualizada."""
    raise NotImplementedError("fase 1a")


def main(argv):
    if argv[:1] == ["criar-banco"]:
        print(f"Banco: {criar_banco()}")
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
