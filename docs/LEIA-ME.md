# Painel de vendas e lucro do ML (TPP + PD): LEIA-ME
Estado em 13/11/2026: **coletor de pedidos pronto e conferido (fase 1a)**; cálculo de lucro e telas na fase 1b. Roda em
qualquer PC.
Requisitos e fases: `PLANO-PAINEL-ML.md`. Camadas, classes, fórmulas e modos de uso: `ARQUITETURA.md`. Telas: `TELAS.md`
(os três nesta pasta).
Código: `painel\`, `analise\` e `testes\` (esta pasta `docs` não tem código; as pastas de código não têm documentação). Visão geral: `README.md`
na raiz do repositório.

## O que está no repositório (e o que não está)
- **Está:** `painel\`, `testes\`, `docs\`, os arquivos de Docker e de instalação na raiz e, em `analise\`, `ml_param.py`, `ml_margem.py`, `ml_pedidos.py` e `ml_api.py` (os
  módulos que o painel importa; `testes\test_pacote.py` confere que a lista do Docker é exatamente essa).
- **Fica fora do git (`.gitignore`), cada PC põe o seu:** `analise\ml_parametros.json` e `analise\custos_produtos.csv`
  (custo e imposto da empresa; recebidos pelo canal interno, ver `README.md`), a pasta de dados
  (`dados\`, ou `ML_DADOS_DIR`), o `.env` e a pasta de tokens.

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
| Configuração portátil (pastas e modo por variável de ambiente) | `painel\nucleo\caminhos.py`, `analise\ml_param.py` (`DIR_DADOS`, `DIR_CONFIG`) | pronto e testado |
| Docker (imagem só com código; dados/parâmetros/tokens como volume) | `Dockerfile`, `.dockerignore`, `compose.yaml`, `.env.exemplo` | escrito; `docker compose config` válido; **imagem não construída** (Docker Desktop desligado e o build baixa a imagem base) |
| Parâmetros `pedidos` e `painel` | `analise\ml_param.py` + `analise\ml_parametros.json` | pronto |
| Lista fechada, filtro do pedido, esquema e criação do banco | `analise\ml_pedidos.py` | pronto e testado (sem comprador) |
| Acesso à API só leitura (função única `Coleta.get`, token que renova sozinho) | `analise\ml_api.py` | pronto e testado ao vivo |
| Leitura dos pedidos pela API (busca, cobrança, frete, gravação) | `analise\ml_pedidos.py` | pronto, testado ao vivo e conferido (ver "Conferência da fase 1a") |
| Modelos (Conta, Pedido, ItemPedido, Envio, Cobranca, CustoProduto, RegraImposto, ResultadoItem, ResumoPeriodo) | `painel\nucleo\modelos.py` | pronto e testado |
| Custos, rebate e imposto (regra de `analise\`: `ml_param` e `ml_margem`) | `painel\nucleo\repositorio.py` `RepositorioParametros` | pronto e testado com os parâmetros reais |
| Ler pedidos do banco | `painel\nucleo\repositorio.py` `RepositorioPedidos.pedidos` | pronto e testado (carrinho contado uma vez) |
| Líquido do pedido (receita − tarifa − frete) | `painel\nucleo\modelos.py` `Pedido.liquido` | pronto e conferido |
| Lucro por item | `painel\nucleo\calculo.py` `CalculadoraLucro.resultado` | fase 1b (rateio de frete pronto e testado) |
| Resumo por mês com acumulado, por produto, canceladas à parte | `painel\nucleo\resumo.py` | pronto e testado |
| CSV e Excel (Arial, autor, abas) | `painel\nucleo\exportar.py` | pronto e testado |
| Botão "Atualizar agora": trava e intervalo | `painel\nucleo\atualizar.py` | pronto e testado (ligar à coleta: fase 2; ver risco dos tokens na ARQUITETURA, seção 6) |
| Conferências: sem comprador / API × Excel / unidades | `painel\nucleo\conferencia.py` | prontas (também por linha de comando) |
| Telas (Visão geral, Vendas e lucro, Downloads) | `painel\app.py`, `painel\paginas\` | casca (fase 1b) |

## Como conferir
- Testes, na raiz do repositório (Python 3.12 ou mais novo com `openpyxl`, por exemplo o `.venv` do `instalar.ps1`):
  `python -m unittest discover -s testes -t .` (43 testes; sem os parâmetros da empresa,
  2 pulados com aviso). O GitHub roda os mesmos testes a cada push (`.github\workflows\testes.yml`).
- Regras fixas conferidas pelos testes: nenhum nome de campo de comprador no código (`test_privacidade.py`); nenhum
  `C:\Users\...` em código e configuração, `.ps1` só ASCII e nenhum pedido de escrita à API (`test_regras_do_codigo.py`);
  lista do Docker igual aos imports (`test_pacote.py`).
- Compose válido sem rodar nada: `docker compose config` na raiz do repositório.
- Criar o banco vazio (não chama a API): `python analise\ml_pedidos.py criar-banco`.
- Ler pedidos (só GET; precisa dos tokens e de `ML_CLIENT_ID`/`ML_CLIENT_SECRET`), na pasta `analise\`:
  `python ml_pedidos.py <CONTA> --desde AAAA-MM-DD [--ate AAAA-MM-DD]` mostra o resumo **sem gravar**; com `--gravar`, grava.
- Conferir o banco contra o relatório de vendas exportado do ML (não chama a API), na raiz:
  `python -m painel.nucleo.conferencia <CONTA> <relatorio.xlsx> <AAAA-MM-DD> <AAAA-MM-DD>`.

## Conferência da fase 1a
Líquido de cada venda pela API comparado com o "Total (BRL)" do relatório de vendas do ML, venda a venda, de 01/09 até a
data de exportação do relatório (fim de outubro), nas duas contas.
- **TPP:** todas as vendas iguais (até R$ 0,01); total igual ao centavo.
- **PD:** todas iguais menos 4, todas explicadas (a diferença no total fica abaixo de 0,1%):
  - 1 venda que, no dia da exportação, ainda ia ser enviada e foi cancelada depois (a API mostra a situação de hoje);
  - 1 devolução em que o ML pagou ao vendedor só parte do valor do produto (não aparece na cobrança por pedido);
  - 2 devoluções com frete de volta cobrado à parte (também fora da cobrança por pedido).
- Unidades: contagem pelos pedidos = contagem direta no banco, nas duas contas. Banco só com a lista fechada.
- As regras do líquido que saíram da conferência estão em `ARQUITETURA.md`, seção 3, e cada uma tem teste em
  `testes\test_pedidos.py`.

## Próximos passos (ordem)
0. **Organização (feito):** as regras de privacidade e portabilidade viraram teste (ver "Como conferir"). Fluxo da equipe:
   cada pessoa trabalha na sua própria branch e leva o trabalho para a `main` por merge, com os testes passando.
1. **Fase 1a (feito):** coletor (só GET), banco, `RepositorioPedidos.pedidos`, líquido e conferências. Falta só a carga
   inicial de 2026 no banco de verdade (`--gravar`, uma conta por vez), na máquina que vai guardar os dados.
2. **Fase 1b** (telas aprovadas em `TELAS.md`): `CalculadoraLucro.resultado` e as três telas;
   instalar os pacotes da tela e construir a imagem Docker (com ok: baixa a imagem base e pacotes).
3. **Fase 2**: filtros, gráficos, botão ligado à coleta; antes, resolver o risco dos tokens (ARQUITETURA, seção 6).
4. Decidir qual máquina é o servidor.

## Armadilhas já conhecidas
- `with sqlite3.connect(...)` **não fecha** a conexão; no Windows o arquivo fica preso. Usar `contextlib.closing(...)`.
- `Set-Content -Encoding UTF8` do PowerShell 5.1 grava com BOM; Python recusa `.py` com BOM.
- A busca de pedidos do ML devolve só os últimos 12 meses. A doc diz que esconde cancelados, mas eles vêm (conferido).
- O filtro de data da busca ignora os minutos e as datas vêm no fuso do ML (-04:00): o coletor busca com folga e corta
  pelo dia em Brasília, como no relatório do ML.
- A cobrança tem limite de chamadas mais apertado e o devolve como erro 400 com "[429]": o coletor espaça os lotes e repete.
  Se mesmo assim falhar, a leitura sai "INCOMPLETA" e não é gravada: é só rodar de novo mais tarde.
- Relatório de vendas exportado do ML para conferir: veja se ele cobre o período inteiro. Uma exportação pode vir com
  filtro e trazer menos vendas que outra mais antiga do mesmo período; nesse caso a conferência mostra "só na API".
- No relatório, as linhas de um carrinho sem dinheiro são os itens; o dinheiro está na linha do pacote (número do pacote).
- O `.env` é pessoal (pode ter segredo): nunca enviar nem versionar; só o `.env.exemplo` circula.
- Refresh token do ML de uso único: uma máquina só atualiza.
- Docker: se `ml_parametros.json` ou `custos_produtos.csv` não existir na pasta indicada, o `compose` cria uma **pasta** com
  esse nome no lugar do arquivo. Pôr os dois arquivos (ou ajustar `ML_CONFIG_HOST` no `.env`) antes do primeiro `up`.
