# -*- coding: utf-8 -*-
"""Modelos (entidades) do painel. So dados e regras simples deles; nenhuma leitura de arquivo nem chamada de API.

Relacoes (docs/ARQUITETURA.md, secao 2): Conta 1-* Pedido; Pedido 1-1..* ItemPedido; Pedido 1-0..1 Envio; Pedido 1-* Cobranca;
ItemPedido *-0..1 Produto (pelo titulo); Produto 1-0..1 CustoProduto; Conta 1-* RegraImposto (padrao + excecao por produto).
Nenhum modelo tem campo de comprador: nao existe onde guardar.
Dinheiro em float arredondado a 2 casas.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Situacao(str, Enum):
    VALIDA = "valida"
    CANCELADA = "cancelada"
    DEVOLVIDA = "devolvida"


@dataclass(frozen=True)
class Conta:
    codigo: str          # "TPP" | "PD"
    nome: str            # "TUDOPRAPET" | "PetDelivery"
    regime: str          # "lucro_real" | "simples" (ml_parametros.json > imposto.regime)


@dataclass(frozen=True)
class ItemPedido:
    anuncio_id: str
    titulo: str
    quantidade: int
    preco_unit: float            # unit_price: ja com desconto do vendedor
    tarifa_unit: float           # sale_fee por unidade
    tipo_anuncio: str = ""       # gold_special = Classico, gold_pro = Premium
    variacao_id: str = ""
    sku: str = ""

    def bruto(self) -> float:
        return round(self.preco_unit * self.quantidade, 2)

    def tarifa(self) -> float:
        return round(self.tarifa_unit * self.quantidade, 2)


@dataclass(frozen=True)
class Envio:
    envio_id: str
    custo_vendedor: float        # senders[].cost de /shipments/{id}/costs
    custo_bruto: float = 0.0     # gross_amount (sem desconto do ML)


@dataclass(frozen=True)
class Cobranca:
    tipo: str                    # ex.: "CV" (tarifa de venda), "CXD" (frete): /billing/.../order/details
    valor: float
    descricao: str = ""


@dataclass
class Pedido:
    conta: str
    pedido_id: str
    fechado_em: datetime
    status: str
    itens: list[ItemPedido] = field(default_factory=list)
    pack_id: str = ""
    tags: tuple[str, ...] = ()
    envio: Envio | None = None
    cobrancas: list[Cobranca] = field(default_factory=list)

    def bruto(self) -> float:
        return round(sum(i.bruto() for i in self.itens), 2)

    def situacao(self) -> Situacao:
        """Regra a confirmar no teste com dado real (fase 1a): status/tags de cancelamento e devolucao do ML."""
        if self.status == "cancelled":
            return Situacao.CANCELADA
        if self.status == "partially_refunded" or "refunded" in self.tags:
            return Situacao.DEVOLVIDA
        return Situacao.VALIDA


@dataclass(frozen=True)
class CustoProduto:
    produto: str
    custo_unit: float | None     # None = pendente (nao inventar custo)
    fonte: str = ""              # de onde veio o custo (ex.: "Omie preco unitario")
    aplica_rebate: bool = False

    def pendente(self) -> bool:
        return self.custo_unit is None


@dataclass(frozen=True)
class RegraImposto:
    conta: str
    regime: str
    debito_pct: float | None     # None = pendente (aliquota ainda nao informada)
    credito_pct: float = 0.0     # 0 no Simples
    produto: str = ""            # vazio = padrao da conta; preenchido = excecao (ml_parametros.json > imposto.por_produto)
    origem: str = ""

    def pendente(self) -> bool:
        return self.debito_pct is None


@dataclass
class ResultadoItem:
    """Uma linha da aba/tela "Vendas": um item de pedido com o lucro calculado. Sem comprador."""
    conta: str
    data: datetime
    pedido_id: str
    anuncio_id: str
    titulo: str
    produto: str
    unidades: int
    bruto: float
    tarifa: float
    frete: float
    liquido: float
    custo: float | None
    rebate: float
    lucro_antes_imposto: float | None
    imposto: float
    lucro_depois_imposto: float | None
    situacao: Situacao = Situacao.VALIDA
    avisos: list[str] = field(default_factory=list)   # ex.: "custo pendente", "imposto pendente"


@dataclass
class ResumoPeriodo:
    """Uma linha do Resumo: conta x periodo (mes) ou conta x produto, com acumulado."""
    conta: str
    periodo: str                 # "AAAA-MM" ou nome do produto
    unidades: int = 0
    bruto: float = 0.0
    liquido: float = 0.0
    custo: float = 0.0
    rebate: float = 0.0
    imposto: float = 0.0
    lucro_antes_imposto: float = 0.0
    lucro_depois_imposto: float = 0.0
    acumulado: float = 0.0
    sem_custo_un: int = 0        # unidades sem custo (ficam fora do lucro e aparecem como aviso)

    def margem_pct(self) -> float | None:
        return round(self.lucro_depois_imposto / self.liquido * 100, 1) if self.liquido else None
