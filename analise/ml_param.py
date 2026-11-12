# -*- coding: utf-8 -*-
"""ml_param.py: le o arquivo central de parametros (ml_parametros.json) com valores padrao seguros.

Uso:
    import ml_param
    P = ml_param.carregar()
    P["rebate"]["percentual"]; ml_param.rebate_efetivo(P); ml_param.imposto_pct(P, "PD")
Se o arquivo faltar ou tiver um campo a menos, vale o padrao abaixo (nada quebra).
"""
import copy, json, os
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def _dir(variavel, padrao):
    """Pasta pela variavel de ambiente (qualquer PC / Docker) ou o padrao relativo ao projeto. Ver painel\\nucleo\\caminhos.py."""
    v = os.environ.get(variavel, "").strip()
    return Path(v).expanduser().resolve() if v else padrao


DIR_CONFIG = _dir("ML_CONFIG_DIR", AQUI)                                     # ml_parametros.json, custos_produtos.csv
DIR_DADOS = _dir("ML_DADOS_DIR", AQUI.parent / "dados")                      # vendas_api.db
ARQ = DIR_CONFIG / "ml_parametros.json"

PADRAO = {
    "rebate": {"percentual": 11.0, "aplicar": False, "comparar": True},
    "imposto": {"aliquota_pct": {"PD": None, "TPP": None}, "credito_custo_pct": {"PD": None, "TPP": None},
                "regime": {"PD": "simples", "TPP": "lucro_real"}, "por_produto": {}},
    "pedidos": {"inicio": "2026-01-01", "lote_cobranca": 60, "por_pagina": 50},     # coletor de pedidos (ml_pedidos.py)
    "painel": {"intervalo_atualizacao_min": 15},                                    # botao "Atualizar agora"
}


def _mescla(base, extra):
    for k, v in (extra or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _mescla(base[k], v)
        else:
            base[k] = v
    return base


def carregar(arquivo=None):
    P = copy.deepcopy(PADRAO)
    arq = Path(arquivo) if arquivo else ARQ
    if arq.exists():
        _mescla(P, json.loads(arq.read_text(encoding="utf-8")))
    return P


def rebate_efetivo(P, cli=None):
    """Percentual de rebate que entra no calculo principal: o da linha de comando (se veio), senao o do arquivo se 'aplicar'."""
    if cli is not None:
        return float(cli)
    return float(P["rebate"]["percentual"]) if P["rebate"]["aplicar"] else 0.0


def _por_produto(P, conta, prod, chave):
    """Excecao por produto (imposto.por_produto.<conta>.<prefixo>.<chave>): o prefixo casa com o inicio do nome do produto
    ('Bravecto' vale para Bravecto250, Bravecto500...). None se nao ha excecao."""
    for prefixo, d in ((P["imposto"].get("por_produto") or {}).get(conta) or {}).items():
        if prod and not prefixo.startswith("_") and prod.startswith(prefixo) and (d or {}).get(chave) not in (None, ""):
            return float(d[chave])
    return None


def imposto_pct(P, conta, prod=None):
    """Debito: % sobre o PRECO de venda (Simples: DAS efetivo; Lucro Real: PIS/COFINS + ICMS + DIFAL medio). 0 se em branco.
    Com prod, vale a excecao de imposto.por_produto (ex.: Bravecto monofasico, sem PIS/COFINS na revenda)."""
    v = _por_produto(P, conta, prod, "aliquota_pct")
    if v is not None:
        return v
    v = (P["imposto"]["aliquota_pct"] or {}).get(conta)
    return float(v) if v not in (None, "") else 0.0


def credito_pct(P, conta, prod=None):
    """Credito: % sobre o CUSTO da mercadoria comprada que volta como desconto do imposto (so fora do Simples). 0 se em branco
    ou se a conta esta no Simples (no Simples nao existe credito de PIS/COFINS/ICMS para quem compra). Com prod, vale a excecao."""
    if (P["imposto"].get("regime") or {}).get(conta) == "simples":
        return 0.0
    v = _por_produto(P, conta, prod, "credito_custo_pct")
    if v is not None:
        return v
    v = (P["imposto"].get("credito_custo_pct") or {}).get(conta)
    return float(v) if v not in (None, "") else 0.0


def tem_imposto(P, conta):
    """A conta tem alguma aliquota informada (geral ou por produto)?"""
    return bool(imposto_pct(P, conta)) or any((d or {}).get("aliquota_pct") not in (None, "")
                                               for k, d in ((P["imposto"].get("por_produto") or {}).get(conta) or {}).items() if not k.startswith("_"))


def texto_imposto(P, contas):
    """Frase curta: o que entrou de imposto em cada conta."""
    fmt = lambda v: format(v, "g").replace(".", ",")
    partes = []
    for c in contas:
        if not tem_imposto(P, c):
            partes.append(f"{c} sem imposto (alíquota pendente)")
            continue
        t = f"{c} débito {fmt(imposto_pct(P, c))}% do preço"
        if credito_pct(P, c):
            t += f", crédito {fmt(credito_pct(P, c))}% do custo"
        for k, d in ((P["imposto"].get("por_produto") or {}).get(c) or {}).items():
            if not k.startswith("_"):
                t += f" ({k}: {fmt(imposto_pct(P, c, k))}% / {fmt(credito_pct(P, c, k))}%)"
        partes.append(t)
    return "; ".join(partes)
