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
    custo_vendedor: float        # senders[].cost de /shipments/{id}/costs (so quando a cobranca ainda nao tem o frete)
    custo_bruto: float = 0.0     # gross_amount (sem desconto do ML)


@dataclass(frozen=True)
class Cobranca:
    tipo: str                    # "<CHARGE|BONUS|RECEITA>/<CORE|SHIPPING|MP>/<subtipo>" (analise/ml_pedidos.buscar_cobrancas)
    valor: float                 # > 0 custo para o vendedor; < 0 estorno (BONUS) ou frete pago pelo comprador
    descricao: str = ""
    cobranca_id: str = ""        # detail_id do ML: num carrinho a mesma cobranca vem em cada pedido (o repositorio conta uma vez)

    def grupo(self) -> str:
        """CORE = tarifa de venda; SHIPPING = frete; MP = taxa de parcelamento paga pelo comprador (repasse: nao e custo)."""
        partes = self.tipo.split("/")
        return partes[1] if len(partes) > 1 else ""


@dataclass
class Pedido:
    """Regras do liquido conferidas contra o "Total (BRL)" do relatorio de vendas do ML (docs/LEIA-ME.md, conferencia da fase 1a)."""
    conta: str
    pedido_id: str
    fechado_em: datetime
    status: str
    itens: list[ItemPedido] = field(default_factory=list)
    pack_id: str = ""
    tags: tuple[str, ...] = ()
    envio: Envio | None = None
    cobrancas: list[Cobranca] = field(default_factory=list)
    reembolsado: float = 0.0     # soma devolvida ao comprador (payments)
    pagamento_detalhe: str = ""  # ex.: "accredited"; "bpp_covered" = o ML cobriu o reembolso e o vendedor ficou com o dinheiro

    def bruto(self) -> float:
        return round(sum(i.bruto() for i in self.itens), 2)

    def coberto_pelo_ml(self) -> bool:
        return "bpp_covered" in self.pagamento_detalhe

    def receita(self) -> float:
        """Bruto menos o que voltou ao comprador por conta do vendedor (se o ML cobriu, o vendedor fica com tudo).
        O reembolso pode incluir o frete que o comprador pagou: desconta no maximo o valor dos produtos."""
        devolvido = 0.0 if self.coberto_pelo_ml() else min(self.reembolsado, self.bruto())
        return round(self.bruto() - devolvido, 2)

    def _cancelado_sem_cobertura(self) -> bool:
        return self.status == "cancelled" and not self.coberto_pelo_ml()

    def tarifa(self) -> float:
        """Tarifa de venda: cobrancas CORE (ja com estornos). Sem cobranca ainda, a sale_fee dos itens; cancelado sem
        cobertura do ML e sem cobranca nao tem tarifa (nunca foi cobrada)."""
        core = [c.valor for c in self.cobrancas if c.grupo() == "CORE"]
        if core:
            return round(sum(core), 2)
        return 0.0 if self._cancelado_sem_cobertura() else round(sum(i.tarifa() for i in self.itens), 2)

    def frete(self) -> float:
        """Frete do vendedor: cobrancas SHIPPING (com estornos e menos o que o comprador pagou). Sem elas, o custo do envio
        (o repositorio so poe o envio num pedido por envio); cancelado sem cobertura do ML nao tem frete (nunca foi cobrado)."""
        fr = [c.valor for c in self.cobrancas if c.grupo() == "SHIPPING"]
        if fr:
            return round(sum(fr), 2)
        if self._cancelado_sem_cobertura():
            return 0.0
        return round(self.envio.custo_vendedor if self.envio else 0.0, 2)

    def liquido(self) -> float:
        """O que o vendedor recebe: receita - tarifa - frete (= "Total (BRL)" do relatorio de vendas do ML)."""
        return round(self.receita() - self.tarifa() - self.frete(), 2)

    def situacao(self) -> Situacao:
        """Cancelado com reembolso coberto pelo ML conta como venda valida (o vendedor recebeu). Cancelado e entregue = devolvido."""
        if self._cancelado_sem_cobertura():
            return Situacao.DEVOLVIDA if "delivered" in self.tags else Situacao.CANCELADA
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
