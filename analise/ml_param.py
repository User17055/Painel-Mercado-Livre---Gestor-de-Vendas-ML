# -*- coding: utf-8 -*-
"""ml_param.py: le o arquivo central de parametros (ml_parametros.json) com valores padrao seguros.

Uso nas outras ferramentas:
    import ml_param
    P = ml_param.carregar()
    P["rebate"]["percentual"]; ml_param.rebate_efetivo(P); ml_param.imposto_pct(P, "PD")
Se o arquivo faltar ou tiver um campo a menos, vale o padrao abaixo (nada quebra).
"""
import copy, json, os
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def _dir(variavel, padrao):
    """Pasta pela variavel de ambiente (qualquer PC / Docker) ou o padrao relativo ao projeto. Ver painel\\sistema\\painel\\nucleo\\caminhos.py."""
    v = os.environ.get(variavel, "").strip()
    return Path(v).expanduser().resolve() if v else padrao


DIR_CONFIG = _dir("ML_CONFIG_DIR", AQUI)                                     # ml_parametros.json, custos_produtos.csv
DIR_DADOS = _dir("ML_DADOS_DIR", AQUI.parent / "relatorios-ml" / "api")      # coletas, monitor, bancos
ARQ = DIR_CONFIG / "ml_parametros.json"

PADRAO = {
    "rebate": {"percentual": 11.0, "aplicar": False, "comparar": True},
    "margem": {"alvo_pct": 15.0, "min_vendas_frete": 5, "frete_ultimos_meses": 0, "contar_aporte_meli": False, "custo_extra_un": {"PD": 0.0, "TPP": 0.0}},
    "imposto": {"aliquota_pct": {"PD": None, "TPP": None}, "credito_custo_pct": {"PD": None, "TPP": None},
                "regime": {"PD": "simples", "TPP": "lucro_real"}, "ilustracao_pct": 9.25, "por_produto": {}},
    "ads": {"escalar_se_acos_abaixo_pct_do_equilibrio": 60, "cortar_se_acos_acima_pct_do_equilibrio": 100, "min_cliques": 30, "min_investimento": 20.0},
    "campanhas": {"margem_min_para_entrar_pct": 5.0},
    "estoque": {"janela_vendas_dias": 30, "ruptura_cobertura_dias": 15, "encalhe_cobertura_dias": 90},
    "vitrine": {"nota_alvo": 80, "topo": 10, "peso_visitas": 1.0, "peso_margem": 1.0, "peso_lacuna": 1.0},
    "reputacao": {"limites_mlb": {"reclamacoes": [1.0, 2.0, 4.5, 8.0], "cancelamentos": [0.5, 1.5, 3.5, 4.0], "atraso_despacho": [6.0, 10.0, 18.0, 22.0]},
                  "cores": ["Mercado Líder", "Verde", "Amarelo", "Laranja", "Vermelho"]},
    "mercado": {"categorias_extra": [], "destaques_por_categoria": 20, "nossos_termos": ["bravecto", "condro", "franpet", "fran pet", "omega", "probiotico", "pele e pelo", "pele pelo", "derme"]},
    "auditoria": {"tolerancia_pp": 0.5},
    "agenda": {"dia_semana": "Monday", "hora": "08:00"},
    "historico": {"min_vendas_mes_base": 20},
    "pipeline": {"desativar": []},
    "black_friday": {"mes_base": "2025-11", "cenarios": [0.8, 1.0, 1.3], "venda_extra_plausivel_pct": 40, "min_un_base": 10, "dias_preco_real": 60, "min_vendas_preco_real": 5},
    "monitor": {"prazo_reposicao_dias": 5, "folga_dias": 3, "janela_dias": 7, "min_dias_leitura": 1.0, "aceleracao_pct": 30, "janela_semanal_dias": 30, "min_un_anuncio_parado": 10,
                "multiplicador_pico": 1.0, "pico_inicio": None, "pico_fim": None, "reputacao_folga_casos": 1},
    "simulador": {"variacoes_pct": [-10, -5, 5, 10], "limite_frete_gratis": 79.0, "dias_tarifa_tipo": 90, "min_vendas_tipo": 5},
    "abc": {"meses": 12, "limite_a_pct": 80, "limite_b_pct": 95, "meses_recentes": 3, "topo_anuncios": 15},
    "conta_produto": {"diferenca_relevante_un": 2.0, "meses_reais": 3},
    "prova": {"dias_janela": 14, "min_dias_depois": 7, "variacao_preco_min_pct": 3.0, "dias_confirmam": 2, "min_un_antes": 10, "min_un_controle": 10, "min_eventos_resumo": 3},
    # pedidos pela API (ml_pedidos.py) e painel (codigo em painel\sistema): ver painel\docs\ARQUITETURA.md
    "pedidos": {"inicio": "2026-01-01", "lote_cobranca": 60, "por_pagina": 50},
    "painel": {"intervalo_atualizacao_min": 15},
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


def sem_imposto(P):
    """Copia dos parametros sem nenhum imposto (debito, credito e excecoes): para comparar contas quando so uma tem aliquota."""
    Q = copy.deepcopy(P)
    Q["imposto"]["aliquota_pct"] = {}
    Q["imposto"]["credito_custo_pct"] = {}
    Q["imposto"]["por_produto"] = {}
    return Q


def tem_imposto(P, conta):
    """A conta tem alguma aliquota informada (geral ou por produto)?"""
    return bool(imposto_pct(P, conta)) or any((d or {}).get("aliquota_pct") not in (None, "")
                                               for k, d in ((P["imposto"].get("por_produto") or {}).get(conta) or {}).items() if not k.startswith("_"))


def texto_imposto(P, contas):
    """Frase curta para os relatorios: o que entrou de imposto em cada conta."""
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


def opcao(args, nome, padrao=None, tipo=float):
    """--nome valor na linha de comando."""
    if nome in args:
        i = args.index(nome)
        if i + 1 < len(args):
            v = args[i + 1]
            return tipo(v.replace(",", ".")) if tipo is float else tipo(v)   # aceita 229,90 (virgula decimal)
    return padrao
