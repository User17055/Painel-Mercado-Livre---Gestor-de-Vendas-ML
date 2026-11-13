# Gestor de Vendas ML: instruções para o Claude Code

Ao abrir: ler `README.md` e `docs/LEIA-ME.md` (estado, próximos passos, armadilhas). Arquitetura e fórmulas:
`docs/ARQUITETURA.md`. Requisitos e fases: `docs/PLANO-PAINEL-ML.md`.

## Regras fixas
- API do Mercado Livre **só leitura** (só GET, pela função única `Coleta.get` quando a leitura de pedidos for feita).
- **Sem dado de comprador:** só a lista fechada de `analise/ml_pedidos.py`. Não escrever nomes de campos de comprador fora de
  `testes/` (o teste de privacidade é o único lugar que pode).
- **Nunca** colocar segredo, token, `.env`, parâmetros ou custos da empresa em arquivo versionado nem em mensagem.
- Nenhum caminho de um PC específico no código: pastas vêm das variáveis de ambiente (`painel/nucleo/caminhos.py`).
- Documentação só em `docs/`; as pastas `painel/`, `analise/` e `testes/` só têm código.
- `.ps1` só com caracteres ASCII (PowerShell 5.1). Downloads (pacotes, imagem Docker) só com o ok de quem pediu.

## Antes de terminar uma mudança
- `python -m unittest discover -s testes -t .` sem falha. Os testes já conferem as regras fixas acima (comprador,
  caminho de PC, `.ps1` ASCII, só GET) e a lista do Docker (`test_pacote.py`).
- Trabalhar na branch de quem pediu (cada pessoa tem a sua); a `main` só recebe merge, com os testes passando.
- Commit, push e merge só quando pedido.
