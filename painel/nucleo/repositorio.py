# -*- coding: utf-8 -*-
"""Camada de DADOS do painel: so le (SQLite, CSV, JSON) e devolve modelos. Nao escreve, nao chama a API.

RepositorioPedidos     vendas_api.db (gravado por analise\\ml_pedidos.py) -> Pedido com itens, envio e cobrancas
RepositorioParametros  ml_parametros.json + custos_produtos.csv (via ml_param e ml_margem) -> CustoProduto, RegraImposto, rebate
"""
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from painel.nucleo import caminhos
from painel.nucleo.modelos import Cobranca, Conta, CustoProduto, Envio, ItemPedido, Pedido, RegraImposto

import ml_margem as M  # noqa: E402  (caminhos poe analise\ no sys.path)
import ml_param  # noqa: E402
import ml_pedidos  # noqa: E402


class RepositorioPedidos:
    """Le pedidos do banco da API (gravado por analise/ml_pedidos.py)."""

    def __init__(self, banco: Path = caminhos.BANCO_VENDAS):
        self.banco = Path(banco)

    def existe(self) -> bool:
        return self.banco.exists()

    def _conexao(self) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{self.banco}?mode=ro", uri=True)   # so leitura de proposito
        con.row_factory = sqlite3.Row
        return con

    def pedidos(self, conta: str, de: date | None = None, ate: date | None = None) -> list[Pedido]:
        """Pedidos da conta no periodo (dia de fechamento em Brasilia, como no relatorio do ML), com itens, envio e cobrancas.
        Carrinho: a mesma cobranca (mesmo cobranca_id) vem em cada pedido do pacote; fica so no primeiro pedido (por id).
        O custo do envio (reserva, quando a cobranca ainda nao tem o frete) fica so no primeiro pedido do envio, e so se
        nenhum pedido daquele envio tiver cobranca de frete: um carrinho tem um envio so."""
        if not self.existe():
            return []
        with closing(self._conexao()) as con:
            peds = [dict(r) for r in con.execute("SELECT * FROM pedidos WHERE conta = ? ORDER BY pedido_id", (conta,))]
            itens, cobs = defaultdict(list), defaultdict(list)
            for r in con.execute("SELECT * FROM pedido_itens WHERE conta = ? ORDER BY pedido_id, seq", (conta,)):
                itens[r["pedido_id"]].append(ItemPedido(r["anuncio_id"] or "", r["titulo"] or "", int(r["quantidade"] or 0),
                                                        float(r["preco_unit"] or 0), float(r["tarifa_unit"] or 0),
                                                        r["tipo_anuncio"] or "", str(r["variacao_id"] or ""), r["sku"] or ""))
            for r in con.execute("SELECT * FROM cobrancas WHERE conta = ? ORDER BY pedido_id, seq", (conta,)):
                cobs[r["pedido_id"]].append(Cobranca(r["tipo"], float(r["valor"] or 0), r["descricao"] or "", r["cobranca_id"] or ""))
            envios = {r["envio_id"]: Envio(str(r["envio_id"]), float(r["custo_vendedor"] or 0), float(r["custo_bruto"] or 0))
                      for r in con.execute("SELECT * FROM envios WHERE conta = ?", (conta,))}
        com_frete = {p["envio_id"] for p in peds if any(c.grupo() == "SHIPPING" for c in cobs[p["pedido_id"]])}
        vistas, envios_usados, saida = set(), set(), []
        for p in peds:
            dia = ml_pedidos.dia_local(p["fechado_em"])
            if (de and dia < de.isoformat()) or (ate and dia > ate.isoformat()):
                continue
            proprias = []
            for c in cobs[p["pedido_id"]]:
                if c.cobranca_id and c.cobranca_id in vistas:
                    continue
                vistas.add(c.cobranca_id)
                proprias.append(c)
            envio = None
            if p["envio_id"] and p["envio_id"] not in com_frete and p["envio_id"] not in envios_usados:
                envio = envios.get(p["envio_id"])
                envios_usados.add(p["envio_id"])
            saida.append(Pedido(conta, str(p["pedido_id"]), datetime.fromisoformat(p["fechado_em"]).astimezone(ml_pedidos.FUSO_BR),
                                p["status"] or "", itens[p["pedido_id"]], str(p["pack_id"] or ""),
                                tuple(t for t in (p["tags"] or "").split(",") if t), envio, proprias,
                                float(p["reembolsado"] or 0), p["pagamento_detalhe"] or ""))
        return saida

    def ultima_atualizacao(self, conta: str) -> str | None:
        """Fim da ultima execucao da coleta de pedidos da conta (tabela execucoes), para mostrar na tela."""
        if not self.existe():
            return None
        with closing(self._conexao()) as con:   # closing: "with conexao" nao fecha o arquivo
            r = con.execute("SELECT max(fim) FROM execucoes WHERE conta = ?", (conta,)).fetchone()
        return r[0] if r else None


class RepositorioParametros:
    """Custos, rebate e imposto, pelas regras de analise/ (ml_param e ml_margem): uma regra so."""

    def __init__(self, P: dict | None = None):
        self.P = P or ml_param.carregar()
        self._custos = M.ler_custos()

    def contas(self) -> list[Conta]:
        reg = self.P["imposto"]["regime"]
        return [Conta(c, M.NOMES[c], reg.get(c, "")) for c in M.CONTAS]

    def custos_brutos(self) -> dict:
        """Linhas de custos_produtos.csv como ml_margem le (entrada de ml_margem.custo_mercadoria)."""
        return self._custos

    def custo(self, produto: str) -> CustoProduto:
        r = self._custos.get(produto) or {}
        v = M.num(r.get("custo_sem_rebate"), None) if r else None
        return CustoProduto(produto, v, r.get("fonte", ""), (r.get("aplica_rebate") or "").lower() == "sim")

    def rebate_pct(self) -> float:
        """Rebate do calculo principal (0 se 'aplicar' = false) e o de comparacao (com x sem) ficam no parametro 'rebate'."""
        return ml_param.rebate_efetivo(self.P)

    def rebate_comparacao(self) -> float | None:
        """% do cenario "com rebate" mostrado ao lado (rebate.comparar = true); None se a comparacao esta desligada."""
        r = self.P["rebate"]
        return float(r["percentual"]) if r.get("comparar") else None

    def custos(self) -> list[CustoProduto]:
        """Todos os produtos da tabela de custos (aba Custos do Excel)."""
        return [self.custo(p) for p in self._custos]

    def regras_imposto(self) -> list[RegraImposto]:
        """Regra padrao de cada conta e as excecoes por produto (aba Imposto do Excel)."""
        out = []
        for c in M.CONTAS:
            out.append(self.regra_imposto(c))
            for prefixo in ((self.P["imposto"].get("por_produto") or {}).get(c) or {}):
                if not prefixo.startswith("_"):
                    out.append(self.regra_imposto(c, prefixo))
        return out

    def regra_imposto(self, conta: str, produto: str | None = None) -> RegraImposto:
        deb = ml_param.imposto_pct(self.P, conta, produto) if ml_param.tem_imposto(self.P, conta) else None
        cred = ml_param.credito_pct(self.P, conta, produto) or 0.0
        return RegraImposto(conta, self.P["imposto"]["regime"].get(conta, ""), deb, cred, produto or "",
                            ml_param.texto_imposto(self.P, [conta]))
