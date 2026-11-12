# Painel de vendas e lucro do ML (TPP + PD): LEIA-ME
Estado em 12/11/2026: **esqueleto**, no repositório da equipe; roda em qualquer PC.
Requisitos e fases: `PLANO-PAINEL-ML.md`. Camadas, classes, fórmulas e modos de uso: `ARQUITETURA.md` (os dois nesta pasta).
Código: `painel\`, `analise\` e `testes\` (esta pasta `docs` não tem código; as pastas de código não têm documentação). Visão geral: `README.md`
na raiz do repositório.

## O que está no repositório (e o que não está)
- **Está:** `painel\`, `testes\`, `docs\`, os arquivos de Docker e de instalação na raiz e, em `analise\`, `ml_param.py`, `ml_margem.py` e `ml_pedidos.py` (os
  módulos que o painel importa; `testes\test_pacote.py` confere que a lista do Docker é exatamente essa).
- **Fica fora do git (`.gitignore`), cada PC põe o seu:** `analise\ml_parametros.json` e `analise\custos_produtos.csv`
  (custo e imposto da empresa; recebidos pelo canal interno, ver `README.md`), a pasta de dados
  (`relatorios-ml\api`, ou `ML_DADOS_DIR`), o `.env` e a pasta de tokens.

## Como rodar
**Uso combinado (11/11): um servidor só; todos acessam pelo navegador.** Quem só consulta não instala nada: abre o endereço do
servidor. Os passos abaixo são para **montar o servidor** (ou testar no próprio PC).

**Com Docker (qualquer PC):** na raiz do repositório
1. copiar `.env.exemplo` para `.env` e ajustar (padrão: só leitura, só este PC, pastas do próprio projeto);
2. `docker compose up -d --build`;
3. abrir `http://localhost:8501`. Parar: `docker compose down`.

**Sem Docker (desenvolvimento):** `instalar.ps1` (uma vez; precisa do Python 3.12) e `rodar.ps1`, os dois na raiz.

Configuração: só variáveis de ambiente (tabela em `painel\nucleo\caminhos.py`). Nada aponta para um PC específico.

## Estado de cada peça
| Peça | Arquivo (caminho a partir da raiz) | Estado |
|---|---|---|
| Configuração portátil (pastas e modo por variável de ambiente) | `painel\nucleo\caminhos.py`, `analise\ml_param.py` (`DIR_DADOS`, `DIR_CONFIG`) | pronto e testado; relatórios das análises idênticos antes × depois (17 de 17) |
| Docker (imagem só com código; dados/parâmetros/tokens como volume) | `Dockerfile`, `.dockerignore`, `compose.yaml`, `.env.exemplo` | escrito; `docker compose config` válido; **imagem não construída** (Docker Desktop desligado e o build baixa a imagem base) |
| Parâmetros `pedidos` e `painel` | `analise\ml_param.py` + `analise\ml_parametros.json` | pronto |
| Lista fechada, filtro do pedido, esquema e criação do banco | `analise\ml_pedidos.py` | pronto e testado (sem comprador) |
| Leitura dos pedidos pela API (busca, frete, cobrança, gravação) | `analise\ml_pedidos.py` | fase 1a (`NotImplementedError`) |
| Modelos (Conta, Pedido, ItemPedido, Envio, Cobranca, CustoProduto, RegraImposto, ResultadoItem, ResumoPeriodo) | `painel\nucleo\modelos.py` | pronto e testado |
| Custos, rebate e imposto (mesma regra das análises) | `painel\nucleo\repositorio.py` `RepositorioParametros` | pronto e testado com os parâmetros reais |
| Ler pedidos do banco | `painel\nucleo\repositorio.py` `RepositorioPedidos.pedidos` | fase 1a |
| Lucro por item | `painel\nucleo\calculo.py` `CalculadoraLucro.resultado` | fase 1b (rateio de frete pronto e testado) |
| Resumo por mês com acumulado, por produto, canceladas à parte | `painel\nucleo\resumo.py` | pronto e testado |
| CSV e Excel (Arial, autor, abas) | `painel\nucleo\exportar.py` | pronto e testado |
| Botão "Atualizar agora": trava e intervalo | `painel\nucleo\atualizar.py` | pronto e testado (ligar à coleta: fase 2; ver risco dos tokens na ARQUITETURA, seção 6) |
| Conferências: sem comprador / API × Excel / unidades | `painel\nucleo\conferencia.py` | sem comprador pronto e testado; as outras fase 1a |
| Telas (Visão geral, Vendas e lucro, Downloads) | `painel\app.py`, `painel\paginas\` | casca (fase 1b) |

## Como conferir
- Testes, na raiz do repositório (Python 3.12 ou mais novo com `openpyxl`, por exemplo o `.venv` do `instalar.ps1`):
  `python -m unittest discover -s testes -t .` (12/11: 21 testes; sem os parâmetros da empresa,
  2 pulados com aviso). O GitHub roda os mesmos testes a cada push (`.github\workflows\testes.yml`).
- Regras de privacidade e portabilidade (nenhum campo de comprador e nenhum `C:\Users\...` no código, `.ps1` só ASCII): hoje
  checadas por uma ferramenta que **não está neste repositório**; trazer para um teste em `testes\` é o
  primeiro passo da fase 1a.
- Compose válido sem rodar nada: `docker compose config` na raiz do repositório.
- Criar o banco vazio (não chama a API): `python analise\ml_pedidos.py criar-banco`.

## Próximos passos (ordem)
0. **Antes da fase 1a (organização):** transformar as regras de privacidade e portabilidade num teste em `testes\`; combinar
   como a equipe trabalha (branch por tarefa e pull request, ou direto na `main`).
1. **Fase 1a**: `ml_pedidos.buscar_pedidos/buscar_fretes/buscar_cobrancas/gravar` (só GET), primeiro numa conta e num período
   curto **sem gravar**; depois `RepositorioPedidos.pedidos` e as conferências API × Excel (01/09 a 30/10, venda a venda).
2. **Fase 1b**: `CalculadoraLucro.resultado` e as três telas; construir a imagem Docker (com ok: baixa a imagem base e pacotes).
3. **Fase 2**: filtros, gráficos, botão ligado à coleta; antes, resolver o risco dos tokens (ARQUITETURA, seção 6).
4. Decidir qual máquina é o servidor e se o acesso é só na rede interna ou também de fora (com login).

## Armadilhas já conhecidas
- `with sqlite3.connect(...)` **não fecha** a conexão; no Windows o arquivo fica preso. Usar `contextlib.closing(...)`.
- `Set-Content -Encoding UTF8` do PowerShell 5.1 grava com BOM; Python recusa `.py` com BOM.
- A busca de pedidos do ML devolve só os últimos 12 meses e esconde cancelados (doc): tratar na fase 1a.
- O `.env` é pessoal (pode ter segredo): nunca enviar nem versionar; só o `.env.exemplo` circula.
- Refresh token do ML de uso único: uma máquina só atualiza.
- Docker: se `ml_parametros.json` ou `custos_produtos.csv` não existir na pasta indicada, o `compose` cria uma **pasta** com
  esse nome no lugar do arquivo. Pôr os dois arquivos (ou ajustar `ML_CONFIG_HOST` no `.env`) antes do primeiro `up`.
