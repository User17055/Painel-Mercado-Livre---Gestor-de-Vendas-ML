# -*- coding: utf-8 -*-
"""ml_margem.py: margem de contribuicao e preco minimo por anuncio. Le so arquivos ja coletados; nao chama a API.

Uso (pasta analise\\):
  python ml_margem.py                 # cenario sem rebate da MSD, snapshot mais recente de cada conta
  python ml_margem.py --rebate 11     # rebate de 11% sobre o custo do Bravecto
  python ml_margem.py --alvo 20       # margem-alvo para o "preco sugerido" (padrao 15%)

Definicao: margem de contribuicao = preco - tarifa de venda - frete liquido - custo do produto,
ANTES de anuncios patrocinados, imposto, embalagem e pessoal. ACOS de equilibrio = margem / preco.
Entradas:
  custos_produtos.csv      custo por produto (editavel; fontes e pendencias dentro)
  anuncios/custos/promocoes_itens/competicao.csv do coletor (preco, tarifa %, campanhas, preco para ganhar)
  vendas_pd_proc.json / vendas_tp_proc.json   so para o frete liquido MEDIO por unidade (tarifa de envio menos o que o
                                              comprador pagou), por produto e conta; nenhum dado de comprador e gravado
Saidas: <conta>\\<data>\\margem.csv, precos_minimos_<CONTA>.csv (id;minimo) e MARGEM-<data>.md
Limites: custo do Franpet = Olist 28/10 sem nota de compra; custo do Bravecto 112,5/1000/1400 mg = Olist (fonte ainda nao confirmada);
frete = media historica (nao varia com o preco aqui); tarifa = percentual do ML no preco de hoje; sem imposto; sem Ads.
"""
import csv, json, re, sys, collections, functools
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # py -I nao inclui a pasta do script
import ml_param  # noqa: E402

AQUI = Path(__file__).resolve().parent
BASE = ml_param.DIR_DADOS               # ML_DADOS_DIR ou <projeto>\relatorios-ml\api
CONTAS = ("PD", "TPP")
NOMES = {"PD": "PetDelivery", "TPP": "TUDOPRAPET"}
VENDAS = {"PD": ml_param.DIR_CONFIG / "vendas_pd_proc.json", "TPP": ml_param.DIR_CONFIG / "vendas_tp_proc.json"}


def ler(p):
    p = Path(p)
    if not p.exists():
        return None
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def num(x, padrao=None):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return padrao


def _faixa(a, b):
    """Faixa de peso no titulo: '20 a 40', '20-40', '20 Kg A 40 Kg', '4,5 - 10', '4,5 10' (o 'Kg' entre os numeros aparece em titulos reais)."""
    return rf"(?<![\d,]){re.escape(a)}\s*(?:kg)?\s*(?:a|-|até|ate)?\s*{re.escape(b)}(?![\d,])"


def classificar(titulo):
    """Produto pelo titulo. Para Franpet vale a palavra que aparece PRIMEIRO (titulos de omega trazem 'pele pelo' no fim)."""
    t = (titulo or "").lower()
    if "bravecto" in t:
        if re.search(_faixa("2", "4,5") + r"|112,5|112\.5", t):
            return "Bravecto112"
        if re.search(_faixa("40", "56") + r"|1400", t):
            return "Bravecto1400"
        if re.search(_faixa("20", "40") + "|" + _faixa("20,1", "40") + r"|1000", t):
            return "Bravecto1000"
        if re.search(_faixa("10", "20") + r"|500|verde", t):
            return "Bravecto500"
        if re.search(_faixa("4,5", "10") + r"|250|laranja", t):
            return "Bravecto250"
        return None
    achados = []
    for chave, prod in (("condro", "Condro"), ("mega", "Omega"), ("pele", "PeleePelo"), ("pelo", "PeleePelo"), ("derme", "PeleePelo"), ("probi", "Probiotico")):
        i = t.find(chave)
        if i >= 0:
            achados.append((i, prod))
    if not achados:
        return None
    prod = min(achados)[1]
    if prod == "Condro":
        return "Condro1000" if "1000" in t else ("Condro500" if "500" in t else None)
    if prod == "Omega":
        return "Omega1000" if "1000" in t else ("Omega500" if "500" in t else None)
    return prod


def unidades_no_titulo(titulo):
    """Quantas unidades do produto vao em UMA venda do anuncio: 'Kit 2 Unid', 'Kit C/2', 'Combo ... (2 Unidades)' = 2; senao 1.
    So olha titulos com 'kit' ou 'combo' (evita confundir '30 comprimidos' com unidades)."""
    t = (titulo or "").lower()
    if "kit" not in t and "combo" not in t:
        return 1
    m = re.search(r"kit\s*(?:c/|com|de)?\s*(\d{1,2})\b", t) or re.search(r"\b(\d{1,2})\s*unid", t)
    n = int(m.group(1)) if m else 1
    return n if 1 <= n <= 10 else 1


def custo_mercadoria(prod, titulo, custos, rebate):
    """Custo da MERCADORIA comprada por venda de 1 unidade do anuncio: custo da tabela (- rebate % se aplica_rebate=sim) x unidades do kit,
    + brinde Franpet nos combos de Bravecto ('+ Fran'/'+ Gourmet'). E a base do credito de imposto (Lucro Real). None se nao ha custo."""
    c = custos.get(prod) if prod else None
    custo = num(c["custo_sem_rebate"]) if c else None
    if custo is None:
        return None
    ef = custo * (1 - (rebate / 100 if c["aplica_rebate"] == "sim" else 0)) * unidades_no_titulo(titulo)
    # combo: Bravecto vendido junto com produto Franpet (brinde). Custo do brinde: linha BrindeFranpet de custos_produtos.csv (pendente).
    if prod.startswith("Bravecto") and re.search(r"\+\s*(fran|gourmet)", (titulo or "").lower()):
        ef += num((custos.get("BrindeFranpet") or {}).get("custo_sem_rebate"), 0.0) or 0.0
    return ef


def custo_unitario(prod, titulo, conta, custos, rebate, P, credito=True):
    """Custo considerado por VENDA de 1 unidade do anuncio = mercadoria (custo_mercadoria) x (1 - credito de imposto %)
    + custo extra da conta x unidades do kit. O credito (imposto.credito_custo_pct; so fora do Simples) entra como desconto do custo:
    imposto liquido = preco x debito% - mercadoria x credito%. credito=False devolve o custo sem o credito (quadro com x sem)."""
    merc = custo_mercadoria(prod, titulo, custos, rebate)
    if merc is None:
        return None
    extra = float((P["margem"].get("custo_extra_un") or {}).get(conta) or 0.0)
    cred = ml_param.credito_pct(P, conta, prod) / 100 if credito else 0.0
    return merc * (1 - cred) + extra * unidades_no_titulo(titulo)


# --- Relatorio de vendas do painel: UMA leitura para todas as ferramentas -----------------------------------------------
# O arquivo traz nome do comprador; aqui so entram os campos de venda da lista abaixo (nada de comprador sai desta funcao).
CAMPOS_VENDA = ("venda", "anuncio", "titulo", "sku", "unid", "preco_unit", "rec_prod", "rec_acresc", "tx_parc", "tarifa_venda", "tarifa_envio",
                "rec_envio", "custo_envio_med", "custo_dif_med", "desc_bonus", "cancel_reemb", "total", "tipo_anuncio", "full", "ads", "prem", "has_fin", "kit",
                "pacote")


@functools.lru_cache(maxsize=None)
def _vendas(conta):
    arq = VENDAS.get(conta)
    if not arq or not arq.exists():
        return ()
    out = []
    for d in json.load(open(arq, encoding="utf-8")):
        v = {k: d.get(k) for k in CAMPOS_VENDA}
        v["ano"], v["mes"] = int(d.get("ano") or 2026), int(d.get("mes") or 0)   # a TPP nao traz 'ano': todo o relatorio dela e de 2026
        try:
            v["dt"] = date(v["ano"], v["mes"], int(d["dia"]))
        except (KeyError, ValueError, TypeError):
            v["dt"] = None
        v["unid"] = d.get("unid") or 1
        v["produto"] = classificar(d.get("titulo") or "")
        v["valida"] = bool(d.get("has_fin")) and (d.get("total") or 0) > 0     # venda que gerou dinheiro (sem cancelamento/devolucao)
        v["pacote_de"], v["cabecalho_pacote"] = None, False
        out.append(v)
    _repartir_pacotes(out)
    for v in out:
        v["frete_liq"] = -((v.get("tarifa_envio") or 0) + (v.get("rec_envio") or 0) + (v.get("custo_envio_med") or 0) + (v.get("custo_dif_med") or 0))
    return tuple(out)


FIN_PACOTE = ("rec_prod", "rec_acresc", "tx_parc", "tarifa_venda", "tarifa_envio", "rec_envio", "custo_envio_med", "custo_dif_med", "desc_bonus", "cancel_reemb", "total")


def _repartir_pacotes(out):
    """Pedido com varios itens (carrinho): o relatorio traz UMA linha-cabecalho com o dinheiro (titulo vazio, unid 0) e, logo abaixo, uma
    linha por item (pacote='Sim', sem financeiro). Aqui o dinheiro do cabecalho vai para os itens, na proporcao de preco_unit x unid
    (a soma dos itens bate centavo a centavo com a receita do cabecalho), e o cabecalho deixa de contar.
    Assim unidades, produto e anuncio do carrinho entram nas contas como qualquer venda."""
    i = 0
    while i < len(out):
        h = out[i]
        if h.get("has_fin") and not (h.get("titulo") or "").strip():
            j = i + 1
            while j < len(out) and out[j].get("pacote") == "Sim" and not out[j].get("has_fin"):
                j += 1
            filhos = out[i + 1:j]
            if filhos:
                pesos = [(f.get("preco_unit") or 0) * (f.get("unid") or 1) for f in filhos]
                tot = sum(pesos)
                for f, p in zip(filhos, pesos):
                    fr = p / tot if tot else 1 / len(filhos)
                    for k in FIN_PACOTE:
                        f[k] = (h.get(k) or 0) * fr
                    f["has_fin"], f["pacote_de"] = True, h.get("venda")
                    f["valida"] = (f.get("total") or 0) > 0
                    if f["dt"] is None:
                        f["dt"], f["ano"], f["mes"] = h["dt"], h["ano"], h["mes"]
                h["has_fin"], h["valida"], h["cabecalho_pacote"] = False, False, True
            i = j
        else:
            i += 1


def vendas(conta, validas=True):
    """Vendas do relatorio do painel da conta (lista de dicts; NAO alterar: o resultado e compartilhado em memoria).
    validas=True: so has_fin e total > 0. validas=False: todas as linhas (inclui cancelamento/devolucao com total <= 0 e linhas sem financeiro).
    Campos: CAMPOS_VENDA + ano, mes, dt (date ou None), produto (classificar), valida, frete_liq (frete liquido da venda, R$),
    pacote_de (venda-cabecalho do carrinho, se o item veio de um) e cabecalho_pacote (True = linha so de dinheiro, ja repartida nos itens)."""
    return [v for v in _vendas(conta) if v["valida"] or not validas]


def venda_extra_para_empatar(m_atual, m_novo):
    """% de unidades a mais que a margem nova (por unidade) precisa vender para dar o MESMO lucro total da atual.
    Negativo = pode vender menos e ainda empatar; None = sem resposta (margem nova ou atual <= 0, ou faltando)."""
    if m_atual is None or m_novo is None or m_novo <= 0 or m_atual <= 0:
        return None
    return (m_atual / m_novo - 1) * 100


def frete_historico(meses=None):
    """{(conta, produto, full|None): (frete liquido medio por unidade, n vendas)} + {(produto,): ...} como reserva. Agregado, sem comprador.
    meses = so as vendas dos ultimos N meses do relatorio de cada conta (margem.frete_ultimos_meses em ml_parametros.json; 0/None = todo o historico).
    O frete muda ao longo do tempo: olhar so os meses recentes e mais fiel ao custo de hoje."""
    if meses is None:
        meses = int(ml_param.carregar()["margem"].get("frete_ultimos_meses") or 0)
    ac = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for conta in VENDAS:
        corte = None
        if meses:
            ym = [(v["ano"], v["mes"]) for v in vendas(conta, validas=False) if v["mes"]]
            if ym:
                a, m = max(ym)
                total = a * 12 + (m - 1) - (meses - 1)
                corte = (total // 12, total % 12 + 1)
        for d in vendas(conta):
            if corte and (d["ano"], d["mes"]) < corte:
                continue
            prod = d["produto"]
            if not prod:
                continue
            fr, un = d["frete_liq"], d["unid"]
            for k in ((conta, prod, bool(d.get("full"))), (conta, prod, None), (prod,)):
                a_ = ac[k]
                a_[0] += fr
                a_[1] += un
                a_[2] += 1
    return {k: (v[0] / v[1], v[2]) for k, v in ac.items() if v[1]}


def data_ultima_coleta():
    """Data (AAAA-MM-DD) do snapshot mais recente entre as contas: e a data que os relatorios usam no nome do arquivo."""
    datas = [p.name for p in (ultimo_snapshot(c) for c in CONTAS) if p]
    return max(datas) if datas else None


def familia(titulo):
    """Familia do produto quando o titulo nao traz o tamanho (ex.: titulo de grupo de Ads cortado): 'Bravecto', 'Condro', 'Omega' ou None."""
    t = (titulo or "").lower()
    for chave, fam in (("bravecto", "Bravecto"), ("condro", "Condro"), ("mega", "Omega")):
        if chave in t:
            return fam
    return None


def mc(preco, custo, pct, frete, fixa=0.0):
    if None in (preco, custo, pct, frete):
        return None
    return preco * (1 - pct / 100) - fixa - frete - custo


def preco_para(margem_pct, custo, pct, frete, fixa=0.0):
    """Preco em que a margem de contribuicao e margem_pct% do preco (0 = preco minimo sem prejuizo). None se faltar custo, tarifa ou frete."""
    if None in (custo, pct, frete):
        return None
    d = 1 - pct / 100 - margem_pct / 100
    return (custo + frete + fixa) / d if d > 0 else None


def f2(v, n=2):
    return "n/d" if v is None else f"{v:.{n}f}".replace(".", ",")


def ultimo_snapshot(conta, base=None):
    """Pasta do snapshot mais recente da conta (ou None)."""
    b = Path(base) if base else BASE
    pastas = sorted(p for p in (b / conta).iterdir() if p.is_dir()) if (b / conta).exists() else []
    return pastas[-1] if pastas else None


def ler_custos():
    return {r["produto"]: r for r in ler(ml_param.DIR_CONFIG / "custos_produtos.csv")}


def linhas_da_conta(conta, pasta, custos, F, rebate, alvo, P):
    """Margem por anuncio ativo de um snapshot.
    rebate = % sobre o custo dos produtos com aplica_rebate=sim; imposto e custo extra vem de ml_parametros.json."""
    an = [r for r in (ler(pasta / "anuncios.csv") or []) if r["status"] == "active"]
    cu = {r["id"]: r for r in (ler(pasta / "custos.csv") or [])}
    pr = collections.defaultdict(list)
    for r in ler(pasta / "promocoes_itens.csv") or []:
        pr[r["id"]].append(r)
    comp = {r["id"]: r for r in (ler(pasta / "competicao.csv") or [])}
    minv = int(P["margem"].get("min_vendas_frete", 5))
    linhas, sem = [], []
    for r in an:
        prod = classificar(r["titulo"])
        custo_ef = custo_unitario(prod, r["titulo"], conta, custos, rebate, P)
        if custo_ef is None:
            sem.append(r)
            continue
        custo_bruto = custo_unitario(prod, r["titulo"], conta, custos, rebate, P, credito=False)   # sem o credito de imposto
        merc = custo_mercadoria(prod, r["titulo"], custos, rebate)
        t = cu.get(r["id"], {})
        pct, fixa = num(t.get("percentual")), num(t.get("taxa_fixa"), 0.0)
        full = r["logistic_type"] == "fulfillment"
        frete = None
        for k in ((conta, prod, full), (conta, prod, None), (prod,)):
            if k in F and F[k][1] >= minv:
                frete = F[k][0]
                break
        cheio = num(r["preco"])
        vig = [num(p["preco_na_campanha"]) for p in pr[r["id"]] if p["situacao"] == "started" and num(p["preco_na_campanha"], 0) > 0]
        vigente = min(vig + [cheio]) if vig else cheio
        bf = [num(p["preco_na_campanha"]) for p in pr[r["id"]] if p["nome"] == "Black Friday 2026" and p["situacao"] in ("pending", "started") and num(p["preco_na_campanha"], 0) > 0]
        bf = bf[0] if bf else None
        cp = comp.get(r["id"], {})
        imp = ml_param.imposto_pct(P, conta, prod)
        pt = None if pct is None else pct + imp          # tarifa + imposto: ambos proporcionais ao preco
        ok = None not in (pt, frete)
        minimo = preco_para(0, custo_ef, pt, frete, fixa) if ok else None
        sugerido = preco_para(alvo, custo_ef, pt, frete, fixa) if ok else None
        m_v, m_bf = mc(vigente, custo_ef, pt, frete, fixa), mc(bf, custo_ef, pt, frete, fixa)
        linhas.append(dict(id=r["id"], titulo=r["titulo"][:48], produto=prod, logistica="Full" if full else "Outra", tipo=r["tipo_anuncio"], cheio=cheio, vigente=vigente,
                           bf=bf, custo=custo_ef, custo_bruto=custo_bruto, mercadoria=merc, tarifa_pct=pct, imposto_pct=imp, pct_total=pt, fixa=fixa, frete=frete, mc_vig=m_v,
                           mc_vig_pct=(m_v / vigente * 100 if m_v is not None else None),
                           mc_bf=m_bf, mc_bf_pct=(m_bf / bf * 100 if m_bf is not None and bf else None), minimo=minimo, sugerido=sugerido,
                           p2w=num(cp.get("preco_para_ganhar")), situacao_cat=cp.get("situacao", ""), catalogo=bool(cp)))
    return linhas, sem


def quadro_imposto(conta, linhas, P):
    """Linhas do MARGEM: margem sem imposto x com imposto sem credito x com imposto e credito da compra (so conta fora do Simples).
    Com a aliquota da conta em branco, usa imposto.ilustracao_pct (regra geral de PIS/COFINS no Lucro Real) como ILUSTRACAO, nos dois lados."""
    if (P["imposto"].get("regime") or {}).get(conta) == "simples":
        return ["", f"**Imposto:** {conta} no Simples Nacional: não existe crédito da compra; o DAS entra como % sobre o preço (`imposto.aliquota_pct`)."]
    ilustra = not ml_param.tem_imposto(P, conta)
    il = float(P["imposto"].get("ilustracao_pct") or 9.25)
    fmt = lambda v: format(v, "g").replace(".", ",")
    titulo = (f"**Imposto com × sem crédito da compra: ILUSTRAÇÃO** (alíquota da {conta} ainda não informada; usei {fmt(il)}% de débito sobre o preço e {fmt(il)}% de crédito "
              f"sobre o custo da mercadoria = PIS/COFINS na regra geral do Lucro Real, sem ICMS/DIFAL; serve para ver o tamanho do efeito, não é a carga da empresa)"
              if ilustra else f"**Imposto com × sem crédito da compra** ({ml_param.texto_imposto(P, [conta])}; `imposto.*` em ml_parametros.json)")
    L = ["", titulo, "Imposto líquido por unidade = preço × débito − custo da mercadoria × crédito. Sem o crédito, o modelo cobra imposto sobre o preço inteiro e a margem sai menor do que é.",
         f"| Produto | Débito · crédito | Preço vigente | Margem sem imposto | Com imposto, SEM crédito | Com imposto e crédito | Crédito devolve/un | Preço mínimo sem × com crédito |\n|---|---|---|---|---|---|---|---|"]
    for prod in sorted({x["produto"] for x in linhas}):
        xs = [x for x in linhas if x["produto"] == prod and x["mc_vig"] is not None and x["mercadoria"] is not None]
        if not xs:
            continue
        d, c = (il, il) if ilustra else (ml_param.imposto_pct(P, conta, prod), ml_param.credito_pct(P, conta, prod))
        r = []
        for x in xs:
            cb, merc, t = x["custo_bruto"], x["mercadoria"], x["tarifa_pct"]
            r.append((x["vigente"], mc(x["vigente"], cb, t, x["frete"], x["fixa"]), mc(x["vigente"], cb, t + d, x["frete"], x["fixa"]),
                      mc(x["vigente"], cb - merc * c / 100, t + d, x["frete"], x["fixa"]), merc * c / 100,
                      preco_para(0, cb, t + d, x["frete"], x["fixa"]), preco_para(0, cb - merc * c / 100, t + d, x["frete"], x["fixa"])))
        med = lambda i: (sum(y[i] for y in r if y[i] is not None) / len([y for y in r if y[i] is not None])) if any(y[i] is not None for y in r) else None
        L.append(f"| {prod} | {fmt(d)}% · {fmt(c)}% | R$ {f2(med(0))} | {f2(med(1))} | {f2(med(2))} | {f2(med(3))} | {f2(med(4))} | {f2(med(5))} → {f2(med(6))} |")
    return L


def main(a):
    P = ml_param.carregar()
    rebate_cli = ml_param.opcao(a, "--rebate")
    rebate = ml_param.rebate_efetivo(P, rebate_cli)
    alvo = ml_param.opcao(a, "--alvo", float(P["margem"]["alvo_pct"]))
    pct_rebate = float(P["rebate"]["percentual"]) if rebate_cli is None else float(rebate_cli)
    custos = ler_custos()
    F = frete_historico()
    L = []
    data_ref = None
    por_conta, alt_conta = {}, {}
    for conta in CONTAS:
        pasta = ultimo_snapshot(conta)
        if not pasta:
            continue
        data_ref = max(data_ref or "", pasta.name)
        linhas, sem = linhas_da_conta(conta, pasta, custos, F, rebate, alvo, P)
        por_conta[conta] = (pasta, linhas, sem)
        # cenario oposto (com <-> sem rebate), so para o quadro comparativo
        outro = 0.0 if rebate > 0 else pct_rebate
        if P["rebate"].get("comparar", True) and outro != rebate:
            alt_conta[conta] = linhas_da_conta(conta, pasta, custos, F, outro, alvo, P)[0]
        cab = ["id", "titulo", "produto", "logistica", "preco_cheio", "preco_vigente", "preco_black_friday", "custo_considerado", "tarifa_pct",
               "imposto_pct", "frete_liquido_un", "mc_vigente", "mc_vigente_pct", "mc_black_friday", "mc_black_friday_pct", "preco_minimo_mc0",
               f"preco_sugerido_mc{alvo:g}", "preco_para_ganhar_catalogo", "situacao_catalogo"]
        r2 = lambda v: None if v is None else round(v, 2)
        with open(pasta / "margem.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(cab)
            for x in linhas:
                w.writerow([x["id"], x["titulo"], x["produto"], x["logistica"], x["cheio"], x["vigente"], x["bf"] or "", round(x["custo"], 2),
                            x["tarifa_pct"], x["imposto_pct"], r2(x["frete"]), r2(x["mc_vig"]),
                            None if x["mc_vig_pct"] is None else round(x["mc_vig_pct"], 1), r2(x["mc_bf"]),
                            None if x["mc_bf_pct"] is None else round(x["mc_bf_pct"], 1), r2(x["minimo"]), r2(x["sugerido"]),
                            x["p2w"] if x["p2w"] is not None else "", x["situacao_cat"]])
        with open(BASE / f"precos_minimos_{conta}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "minimo"])
            for x in linhas:
                if x["minimo"] is not None:
                    w.writerow([x["id"], round(x["minimo"], 2)])

    cen = "sem rebate" if rebate == 0 else f"rebate de {rebate:g}% sobre o custo do Bravecto"
    imp_txt = "imposto: " + ml_param.texto_imposto(P, CONTAS)
    L += [f"# Margem e preço mínimo por anúncio: {data_ref}",
          f"**Cenário principal: {cen}; {imp_txt}.** Margem de contribuição = preço − tarifa de venda − frete líquido − custo (− imposto, se informado), **antes de anúncios, embalagem e pessoal** (mesma definição do anexo 2).",
          "ACOS de equilíbrio = margem ÷ preço. **Preço mínimo** = margem zero (não vender com prejuízo). "
          f"**Preço sugerido** = margem de {alvo:g}% (`margem.alvo_pct` em ml_parametros.json ou `--alvo`). Preços de campanha vêm de `promocoes_itens.csv`; preço para ganhar, de `competicao.csv`.",
          "**Limites:** custo do Franpet = Olist 28/10, sem nota de compra; custo do Bravecto 112,5/250/500/1000 mg = tabela do e-commerce de 09/11 (sem rebate); 1400 mg = estimado (R$ 168,50); "
          f"frete = média por produto e conta, {'de todo o histórico' if not P['margem'].get('frete_ultimos_meses') else 'dos últimos ' + str(P['margem']['frete_ultimos_meses']) + ' meses do relatório de vendas (`margem.frete_ultimos_meses`)'} (não muda com o preço); tarifa = percentual do ML no preço de hoje. Tudo editável em `custos_produtos.csv` e `ml_parametros.json`.", ""]
    for conta, (pasta, linhas, sem) in por_conta.items():
        L.append(f"## {NOMES[conta]} ({conta}), snapshot {pasta.name}")
        L.append("| Produto | Anúncios | Preço vigente | Margem R$ | Margem % (ACOS equil.) | Preço mínimo | Preço sugerido | Custo (já sem o crédito de imposto) |\n|---|---|---|---|---|---|---|---|")
        for prod in sorted({x["produto"] for x in linhas}):
            xs = [x for x in linhas if x["produto"] == prod and x["mc_vig"] is not None]
            if not xs:
                continue
            n = len(xs)
            med = lambda k: sum(x[k] for x in xs) / n
            L.append(f"| {prod} | {n} | R$ {f2(min(x['vigente'] for x in xs))} a {f2(max(x['vigente'] for x in xs))} | {f2(min(x['mc_vig'] for x in xs))} a {f2(max(x['mc_vig'] for x in xs))} | "
                     f"{f2(min(x['mc_vig_pct'] for x in xs), 1)}% a {f2(max(x['mc_vig_pct'] for x in xs), 1)}% | R$ {f2(med('minimo'))} | R$ {f2(med('sugerido'))} | R$ {f2(xs[0]['custo'])} |")
        neg = [x for x in linhas if x["mc_vig"] is not None and x["mc_vig"] < 0]
        L.append("")
        L.append(f"**Anúncios com margem negativa no preço vigente: {len(neg)}.**" + ("" if not neg else " " + "; ".join(f"{x['titulo'][:30]} (R$ {f2(x['vigente'])}, margem R$ {f2(x['mc_vig'])})" for x in neg)))
        # quadro comparativo com x sem rebate (so produtos em que o rebate se aplica)
        if conta in alt_conta:
            alt = {x["id"]: x for x in alt_conta[conta]}
            rot_a, rot_b = ("sem rebate", f"com rebate {pct_rebate:g}%") if rebate == 0 else (f"com rebate {rebate:g}%", "sem rebate")
            L += ["", f"**Com × sem rebate (preço vigente):** só produtos em que o rebate se aplica.",
                  f"| Produto | Margem R$ {rot_a} | Margem R$ {rot_b} | Margem % {rot_a} | Margem % {rot_b} | Preço mínimo {rot_a} | Preço mínimo {rot_b} |\n|---|---|---|---|---|---|---|"]
            for prod in sorted({x["produto"] for x in linhas}):
                if custos.get(prod, {}).get("aplica_rebate") != "sim":
                    continue
                xs = [x for x in linhas if x["produto"] == prod and x["mc_vig"] is not None and x["id"] in alt]
                if not xs:
                    continue
                n = len(xs)
                mm = lambda lst, k: sum(y[k] for y in lst) / len(lst)
                ys = [alt[x["id"]] for x in xs]
                L.append(f"| {prod} | {f2(mm(xs, 'mc_vig'))} | {f2(mm(ys, 'mc_vig'))} | {f2(mm(xs, 'mc_vig_pct'), 1)}% | {f2(mm(ys, 'mc_vig_pct'), 1)}% | {f2(mm(xs, 'minimo'))} | {f2(mm(ys, 'minimo'))} |")
        L += quadro_imposto(conta, linhas, P)
        bfs = [x for x in linhas if x["bf"]]
        if bfs:
            L.append("")
            L.append("**Black Friday 2026: preço da campanha × margem** (anúncios já pendentes)")
            L.append("| Anúncio | Produto | Vigente | BF | Margem vigente | Margem BF | Mínimo |\n|---|---|---|---|---|---|---|")
            for x in sorted(bfs, key=lambda x: (x["mc_bf"] is None, x["mc_bf"] or 0)):
                L.append(f"| {x['titulo'][:34]} | {x['produto']} | {f2(x['vigente'])} | {f2(x['bf'])} | {f2(x['mc_vig'])} ({f2(x['mc_vig_pct'], 0)}%) | {f2(x['mc_bf'])} ({f2(x['mc_bf_pct'], 0)}%) | {f2(x['minimo'])} |")
        cats = [x for x in linhas if x["p2w"] is not None and x["situacao_cat"] != "winning"]
        if cats:
            L.append("")
            L.append("**Catálogo: o preço para ganhar dá lucro?** (só anúncios perdendo a página)")
            L.append("| Anúncio | Vigente | Para ganhar | Mínimo (margem 0) | Margem ao ganhar |\n|---|---|---|---|---|")
            for x in sorted(cats, key=lambda x: x["produto"]):
                m = mc(x["p2w"], x["custo"], x["pct_total"], x["frete"], x["fixa"])
                L.append(f"| {x['titulo'][:34]} | {f2(x['vigente'])} | {f2(x['p2w'])} | {f2(x['minimo'])} | {f2(m)} {'**(prejuízo)**' if m is not None and m < 0 else ''} |")
        if sem:
            L.append("")
            L.append(f"Sem custo mapeado ({len(sem)} anúncios ativos): " + "; ".join(r["titulo"][:30] for r in sem) + ". Falta o custo no `custos_produtos.csv`.")
        L.append("")
    out = BASE / f"MARGEM-{data_ref}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Margem: {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
