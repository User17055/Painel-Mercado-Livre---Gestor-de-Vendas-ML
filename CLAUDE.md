# Gestor de Vendas ML: instruções para o Claude Code

Ao abrir: ler `README.md` e `painel/docs/LEIA-ME.md` (estado, próximos passos, armadilhas). Arquitetura e fórmulas:
`painel/docs/ARQUITETURA.md`. Requisitos e fases: `painel/docs/PLANO-PAINEL-ML.md`.

## Regras fixas
- API do Mercado Livre **só leitura** (só GET, pela função única `Coleta.get` quando a leitura de pedidos for feita).
- **Sem dado de comprador:** só a lista fechada de `analise/ml_pedidos.py`. Não escrever nomes de campos de comprador fora de
  `painel/sistema/testes/` (o teste de privacidade é o único lugar que pode).
- **Nunca** colocar segredo, token, `.env`, parâmetros ou custos da empresa em arquivo versionado nem em mensagem.
- Nenhum caminho de um PC específico no código: pastas vêm das variáveis de ambiente (`painel/sistema/painel/nucleo/caminhos.py`).
- Documentação só em `painel/docs/`; a pasta `painel/sistema/` só tem o que roda.
- `.ps1` só com caracteres ASCII (PowerShell 5.1). Downloads (pacotes, imagem Docker) só com o ok de quem pediu.

## Antes de terminar uma mudança
- `python -m unittest discover -s painel/sistema/testes -t painel/sistema` sem falha.
- Lista do Docker coerente com os imports (`test_pacote.py`).
- Commit e push só quando pedido.
