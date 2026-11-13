# -*- coding: utf-8 -*-
"""ml_pedidos.py: vendas pela API (pedidos), SO LEITURA e SEM DADO DE COMPRADOR. Base do painel (docs\\ARQUITETURA.md).

Regra: so os campos necessarios ao lucro. Como garante: LISTA FECHADA. O coletor copia apenas as chaves de CAMPOS_*
  (abaixo); tudo o que nao esta na lista (comprador, apelido, destinatario, endereco, telefone, documento) e descartado
  na leitura: nao e gravado nem mostrado. painel\\nucleo\\conferencia.sem_comprador confere o banco.

Fontes (so GET, por ml_api.Coleta.get):
  pedidos   /orders/search?seller=<id>&order.date_closed.from=..&order.date_closed.to=..&sort=date_asc  (por_pagina por
            chamada; so os ultimos 12 meses). O filtro de data ignora minutos: busca com folga e corta aqui.
            Datas vem no fuso do ML (-04:00): o dia de cada venda e o de Brasilia (-03:00), como no relatorio do ML.
  cobranca  /billing/integration/group/ML/order/details?order_ids=a,b,..  (ate 60 por chamada) -> cada cobranca do pedido:
            tarifa de venda (marketplace CORE) e frete do vendedor (SHIPPING). Fonte principal do frete: 60 pedidos por chamada.
  frete     /shipments/<id>/costs (cabecalho x-format-new: true) -> senders[].cost: so para envio sem frete na cobranca.
Liquido do pedido: painel\\nucleo\\modelos.Pedido.liquido (regras conferidas contra o relatorio de vendas do ML).

Uso (pasta analise\\):
  python ml_pedidos.py criar-banco                                  # cria dados\\vendas_api.db vazio (esquema abaixo)
  python ml_pedidos.py <CONTA> --desde AAAA-MM-DD [--ate AAAA-MM-DD] # le e mostra o resumo, SEM gravar
  python ml_pedidos.py <CONTA> --desde AAAA-MM-DD --gravar           # grava no banco (pedido relido e atualizado)
Leitura com erro (pagina ou lote que falhou) nunca e gravada: o banco nao fica com um periodo pela metade.
Parametros: ml_parametros.json > pedidos (inicio, lote_cobranca, por_pagina).
"""
import sqlite3
import sys
import time
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
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
# Do pagamento (lista payments) so entram estes tres, somados/juntados aqui; o resto (inclusive o id de quem pagou) fica fora.
# Servem para saber se a venda cancelada foi reembolsada pelo vendedor (bpp_refunded) ou coberta pelo ML (bpp_covered).
CAMPOS_PAGAMENTO = {"pagamento_status": "status", "pagamento_detalhe": "status_detail", "reembolsado": "transaction_amount_refunded"}

ESQUEMA = {
    "pedidos": ["conta", *CAMPOS_PEDIDO, *CAMPOS_PAGAMENTO, "coletado_em"],
    "pedido_itens": ["conta", "pedido_id", "seq", *CAMPOS_ITEM],
    "envios": ["conta", "envio_id", "pedido_id", "custo_vendedor", "custo_bruto"],
    "cobrancas": ["conta", "pedido_id", "tipo", "seq", "cobranca_id", "valor", "descricao"],
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
         "custo_vendedor": "REAL", "custo_bruto": "REAL", "valor": "REAL", "reembolsado": "REAL"}


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
    pags = [p for p in pedido.get("payments") or [] if isinstance(p, dict)]

    def juntar(chave):   # varios pagamentos: os valores distintos, em ordem, separados por virgula
        return ",".join(sorted({str(p[chave]) for p in pags if p.get(chave) is not None})) or None

    linha = {"conta": conta, **{col: _pegar(pedido, cam) for col, cam in CAMPOS_PEDIDO.items()},
             "pagamento_status": juntar(CAMPOS_PAGAMENTO["pagamento_status"]),
             "pagamento_detalhe": juntar(CAMPOS_PAGAMENTO["pagamento_detalhe"]),
             "reembolsado": round(sum(float(p.get(CAMPOS_PAGAMENTO["reembolsado"]) or 0) for p in pags), 2),
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


FUSO_BR = timezone(timedelta(hours=-3))   # Brasilia (sem horario de verao desde 2019)


def dia_local(iso: str | None) -> str | None:
    """'2026-11-10T23:30:00.000-04:00' -> '2026-11-11' (dia em Brasilia, o mesmo do relatorio de vendas do ML)."""
    return datetime.fromisoformat(iso).astimezone(FUSO_BR).date().isoformat() if iso else None


def _janelas(desde: date, ate: date):
    """Periodo em pedacos de ate 31 dias (paginacao curta em cada um)."""
    ini = desde
    while ini <= ate:
        fim = min(ini + timedelta(days=30), ate)
        yield ini, fim
        ini = fim + timedelta(days=1)


# --- chamadas a API: todas por ml_api.Coleta.get (so GET) ------------------------------------------------------------------
def buscar_pedidos(c, desde: date, ate: date, por_pagina: int = 50) -> tuple[list[dict], list[dict]]:
    """Pedidos do vendedor com dia de fechamento (Brasilia) entre desde e ate -> (linhas de 'pedidos', de 'pedido_itens')."""
    vistos, pedidos, itens = set(), [], []
    for ini, fim in _janelas(desde, ate):
        offset = 0
        while True:
            # folga de 1 dia em cada ponta (fuso e hora truncada pela API); o corte exato e feito abaixo pelo dia em Brasilia
            r = c.get("/orders/search", {"seller": c.uid, "order.date_closed.from": f"{ini - timedelta(days=1)}T00:00:00.000-03:00",
                                         "order.date_closed.to": f"{fim + timedelta(days=1)}T23:00:00.000-03:00",
                                         "sort": "date_asc", "limit": por_pagina, "offset": offset},
                      ref=f"pedidos {ini}..{fim} offset {offset}")
            if r is None:
                break                                  # erro ja registrado em c.erros: a leitura fica marcada como incompleta
            for p in r.get("results") or []:
                linha, its = filtrar_pedido(c.conta, p)
                dia = dia_local(linha["fechado_em"]) or ""
                if linha["pedido_id"] in vistos or not (ini.isoformat() <= dia <= fim.isoformat()):
                    continue
                vistos.add(linha["pedido_id"])
                pedidos.append(linha)
                itens.extend(its)
            offset += por_pagina
            if offset >= (r.get("paging") or {}).get("total", 0):
                break
    return pedidos, itens


RECEITA_ENVIO = "RECEITA/SHIPPING/COMPRADOR"   # frete pago pelo comprador: o ML cobra o frete cheio e devolve esta parte
# Da cobranca, alem de tipo/valor/descricao, so entra este numero: quanto o comprador pagou de frete (valor, nao identidade).
# E a unica excecao nomeada da regra de privacidade do codigo (testes/test_privacidade.py, CAMPOS_PERMITIDOS).
CAMPO_FRETE_COMPRADOR = "receiver_shipping_cost"


def buscar_cobrancas(c, pedido_ids: list, lote: int = 60) -> list[dict]:
    """Cobrancas de cada pedido (lista fechada: tipo, valor, descricao). valor > 0 = custo para o vendedor.
    tipo = "<detail_type>/<marketplace>/<sub_type>": CHARGE soma; BONUS (estorno de cobranca) subtrai.
    marketplace CORE = tarifa de venda; SHIPPING = frete; MP = taxa de parcelamento paga pelo comprador (repasse: nao e custo).
    Mais uma linha RECEITA_ENVIO (valor negativo) por cobranca de frete em que o comprador pagou parte (CAMPO_FRETE_COMPRADOR
    da PROPRIA linha de frete; nas outras linhas o numero pode ser o do carrinho inteiro).
    cobranca_id = detail_id do ML: num carrinho a mesma cobranca de frete vem repetida em cada pedido; quem le conta uma vez."""
    linhas = []
    for i in range(0, len(pedido_ids), lote):
        bloco = pedido_ids[i:i + lote]
        if i:
            time.sleep(1)   # a cobranca tem limite de chamadas mais apertado que o resto da API
        r = c.get("/billing/integration/group/ML/order/details", {"order_ids": ",".join(str(x) for x in bloco)},
                  ref=f"cobrancas {i}..{i + len(bloco) - 1}")
        for o in (r or {}).get("results") or []:
            seq = 0
            for d in o.get("details") or []:
                ci = d.get("charge_info") or {}
                tipo_det = ci.get("detail_type") or ""
                valor = float(ci.get("detail_amount") or 0)
                mercado = (d.get("marketplace_info") or {}).get("marketplace", "")
                seq += 1
                linhas.append({"conta": c.conta, "pedido_id": o.get("order_id"), "seq": seq, "cobranca_id": str(ci.get("detail_id")),
                               "tipo": f"{tipo_det}/{mercado}/{ci.get('detail_sub_type', '')}",
                               "valor": -valor if tipo_det == "BONUS" else valor,
                               "descricao": ci.get("transaction_detail") or ""})
                pago = float((d.get("shipping_info") or {}).get(CAMPO_FRETE_COMPRADOR) or 0)
                # so se a cobranca de frete continua valendo (status vazio); estornada (BONUS_ON_...) nao tem frete a devolver
                if mercado == "SHIPPING" and tipo_det == "CHARGE" and pago and not ci.get("status"):
                    seq += 1
                    linhas.append({"conta": c.conta, "pedido_id": o.get("order_id"), "seq": seq,
                                   "cobranca_id": f"{ci.get('detail_id')}:comprador", "tipo": RECEITA_ENVIO, "valor": -pago,
                                   "descricao": "Receita por envio (frete pago pelo comprador)"})
    return linhas


def buscar_fretes(c, envios: dict) -> list[dict]:
    """envio_id -> pedido_id. /shipments/<id>/costs de cada um -> linhas de 'envios' (o que o vendedor pagou e o bruto)."""
    linhas = []
    for envio_id, pedido_id in envios.items():
        r = c.get(f"/shipments/{envio_id}/costs", headers={"x-format-new": "true"}, ref=f"frete {envio_id}")
        if r is None:
            continue
        custo = sum(float(s.get("cost") or 0) for s in r.get("senders") or [] if s.get("user_id") == c.uid)
        linhas.append({"conta": c.conta, "envio_id": envio_id, "pedido_id": pedido_id,
                       "custo_vendedor": round(custo, 2), "custo_bruto": float(r.get("gross_amount") or 0)})
    return linhas


def eh_frete(tipo_cobranca: str) -> bool:
    return tipo_cobranca.split("/")[1:2] == ["SHIPPING"]


def coletar(conta: str, desde: date, ate: date, com_fretes: bool = True) -> dict:
    """Uma leitura da conta no periodo (so GET, nada gravado). 'completa' = sem nenhum erro de leitura."""
    import ml_api
    P = ml_param.carregar()["pedidos"]
    c = ml_api.Coleta(conta)
    inicio = datetime.now().isoformat(timespec="seconds")
    pedidos, itens = buscar_pedidos(c, desde, ate, int(P["por_pagina"]))
    cobrancas = buscar_cobrancas(c, [p["pedido_id"] for p in pedidos], int(P["lote_cobranca"]))
    envios = []
    if com_fretes:   # so os envios sem frete na cobranca de nenhum pedido (ex.: cobranca ainda nao gerada); um carrinho = um envio
        envio_de = {p["pedido_id"]: p["envio_id"] for p in pedidos}
        com_frete = {envio_de.get(x["pedido_id"]) for x in cobrancas if eh_frete(x["tipo"])}
        faltam = {}
        for p in pedidos:
            if p["envio_id"] and p["envio_id"] not in com_frete:
                faltam.setdefault(p["envio_id"], p["pedido_id"])
        envios = buscar_fretes(c, faltam)
    return {"conta": conta, "inicio": inicio, "fim": datetime.now().isoformat(timespec="seconds"), "pedidos": pedidos,
            "itens": itens, "envios": envios, "cobrancas": cobrancas, "chamadas": c.chamadas, "erros": c.erros,
            "completa": not c.erros}


def gravar(banco: Path, leitura: dict) -> int:
    """Grava uma leitura COMPLETA (recusa leitura com erro) e devolve quantos pedidos novos.
    Pedido relido (ex.: status mudou para devolvido) substitui o anterior inteiro: linha, itens e cobrancas."""
    if not leitura.get("completa"):
        raise ValueError(f"leitura com {len(leitura.get('erros') or [])} erro(s): nada gravado")
    criar_banco(banco)
    conta = leitura["conta"]
    ids = [p["pedido_id"] for p in leitura["pedidos"]]
    with closing(sqlite3.connect(banco)) as con, con:
        antes = {r[0] for r in con.execute("SELECT pedido_id FROM pedidos WHERE conta = ?", (conta,))}
        for tab in ("pedido_itens", "cobrancas"):
            con.executemany(f"DELETE FROM {tab} WHERE conta = ? AND pedido_id = ?", [(conta, i) for i in ids])
        for tab, linhas in (("pedidos", leitura["pedidos"]), ("pedido_itens", leitura["itens"]),
                            ("cobrancas", leitura["cobrancas"]), ("envios", leitura["envios"])):
            cols = ESQUEMA[tab]
            con.executemany(f"INSERT OR REPLACE INTO {tab} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                            [tuple(linha.get(col) for col in cols) for linha in linhas])
        novos = len(set(ids) - antes)
        con.execute("INSERT INTO execucoes (conta, tipo, inicio, fim, pedidos_novos, chamadas, erros) VALUES (?,?,?,?,?,?,?)",
                    (conta, "pedidos", leitura["inicio"], leitura["fim"], novos, leitura["chamadas"], 0))
    return novos


def resumo(leitura: dict) -> str:
    """Totais brutos da leitura (nenhum dado de comprador), para ver antes de gravar. O liquido oficial, com as regras de
    cancelamento, reembolso e carrinho, e o de painel\\nucleo\\modelos.Pedido.liquido (depois de gravar)."""
    from collections import Counter
    ped, its, cob = leitura["pedidos"], leitura["itens"], leitura["cobrancas"]

    def soma(grupo):
        return sum(x["valor"] for x in cob if x["tipo"].split("/")[1:2] == [grupo])

    receita = sum(i["preco_unit"] * i["quantidade"] for i in its)
    tarifa = sum(i["tarifa_unit"] * i["quantidade"] for i in its)
    frete_env = sum(e["custo_vendedor"] for e in leitura["envios"])
    return "\n".join([
        f"Conta {leitura['conta']}: {len(ped)} pedido(s), {len(its)} item(ns), {sum(i['quantidade'] for i in its)} unidade(s); "
        f"status {dict(Counter(p['status'] for p in ped))}",
        f"  receita (preco x qtd) R$ {receita:,.2f} | tarifa dos itens R$ {tarifa:,.2f} | tarifa na cobranca R$ {soma('CORE'):,.2f} "
        f"| parcelamento (repasse, nao e custo) R$ {soma('MP'):,.2f}",
        f"  frete na cobranca R$ {soma('SHIPPING'):,.2f} (ja menos o que o comprador pagou) | "
        f"frete por envio (sem cobranca) R$ {frete_env:,.2f} ({len(leitura['envios'])} envios)",
        f"  chamadas {leitura['chamadas']} | erros {len(leitura['erros'])} | {'COMPLETA' if leitura['completa'] else 'INCOMPLETA'}",
    ] + [f"  erro: {e}" for e in leitura["erros"][:10]])


def main(argv):
    if argv[:1] == ["criar-banco"]:
        print(f"Banco: {criar_banco()}")
        return
    if not argv or argv[0].upper() not in ("PD", "TPP") or "--desde" not in argv:
        sys.exit(__doc__)

    def opcao(nome, padrao=None):
        return argv[argv.index(nome) + 1] if nome in argv else padrao

    desde = date.fromisoformat(opcao("--desde"))
    ate = date.fromisoformat(opcao("--ate", date.today().isoformat()))
    leitura = coletar(argv[0].upper(), desde, ate)
    print(resumo(leitura))
    if "--gravar" in argv:
        print(f"Gravado em {BANCO}: {gravar(BANCO, leitura)} pedido(s) novo(s)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
