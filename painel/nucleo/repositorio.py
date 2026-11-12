# -*- coding: utf-8 -*-
"""Camada de DADOS do painel: so le (SQLite, CSV, JSON) e devolve modelos. Nao escreve, nao chama a API.

RepositorioPedidos     vendas_api.db (gravado por analise\\ml_pedidos.py) -> Pedido com itens, envio e cobrancas
RepositorioParametros  ml_parametros.json + custos_produtos.csv (via ml_param e ml_margem) -> CustoProduto, RegraImposto, rebate
"""
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from painel.nucleo import caminhos
from painel.nucleo.modelos import Conta, CustoProduto, Pedido, RegraImposto

import ml_margem as M  # noqa: E402  (caminhos poe analise\ no sys.path)
import ml_param  # noqa: E402


class RepositorioPedidos:
    """Le pedidos do banco da API. Fase 1a: implementar depois que ml_pedidos gravar dado real."""

    def __init__(self, banco: Path = caminhos.BANCO_VENDAS):
        self.banco = Path(banco)

    def existe(self) -> bool:
        return self.banco.exists()

    def _conexao(self) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{self.banco}?mode=ro", uri=True)   # so leitura de proposito
        con.row_factory = sqlite3.Row
        return con

    def pedidos(self, conta: str, de: date | None = None, ate: date | None = None) -> list[Pedido]:
        """Pedidos da conta no periodo (pela data de fechamento), com itens, envio e cobrancas."""
        raise NotImplementedError("fase 1a: montar Pedido a partir de pedidos + pedido_itens + envios + cobrancas")

    def ultima_atualizacao(self, conta: str) -> str | None:
        """Fim da ultima execucao da coleta de pedidos da conta (tabela execucoes), para mostrar na tela."""
        if not self.existe():
            return None
        with closing(self._conexao()) as con:   # closing: "with conexao" nao fecha o arquivo
            r = con.execute("SELECT max(fim) FROM execucoes WHERE conta = ?", (conta,)).fetchone()
        return r[0] if r else None


class RepositorioParametros:
    """Custos, rebate e imposto: a MESMA fonte das analises (uma regra so)."""

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

    def regra_imposto(self, conta: str, produto: str | None = None) -> RegraImposto:
        deb = ml_param.imposto_pct(self.P, conta, produto) if ml_param.tem_imposto(self.P, conta) else None
        cred = ml_param.credito_pct(self.P, conta, produto) or 0.0
        return RegraImposto(conta, self.P["imposto"]["regime"].get(conta, ""), deb, cred, produto or "",
                            ml_param.texto_imposto(self.P, [conta]))
