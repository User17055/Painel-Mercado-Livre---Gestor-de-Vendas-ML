# Gestor de Vendas ML

Painel web de vendas e lucro das contas do Mercado Livre **TUDOPRAPET (TPP)** e **PetDelivery (PD)**, com download em CSV e
Excel. Lê a API oficial do Mercado Livre **só para leitura** e **sem dado de comprador**.

**Estado:** esqueleto (estrutura, modelos, testes e Docker prontos; leitura dos pedidos pela API e telas ainda não feitas).
Detalhes e próximos passos: [`docs/LEIA-ME.md`](docs/LEIA-ME.md).

## Estrutura

```
painel/        código do painel: app Streamlit (app.py), núcleo (nucleo/) e telas (paginas/)
analise/       módulos de regra usados pelo painel: parâmetros, custo e coletor de pedidos
testes/        testes automáticos (rodam também no GitHub a cada push)
docs/          documentação: LEIA-ME (estado e como rodar), ARQUITETURA, PLANO (requisitos e fases)
Dockerfile, compose.yaml, .dockerignore, requirements.txt, .env.exemplo, instalar.ps1, rodar.ps1   (na raiz)
```

## Arquivos de parâmetros (não estão no repositório)

O painel usa dois arquivos com dados da empresa: `ml_parametros.json` (rebate e imposto por conta) e `custos_produtos.csv`
(custo de cada produto). Eles **não estão neste repositório** e nunca entram nele (estão no `.gitignore`).

- Quem vai rodar o painel recebe os dois pelo **canal interno da empresa** e coloca na pasta `analise/`. Outra pasta também
  serve: basta indicar o caminho em `ML_CONFIG_DIR` (sem Docker) ou `ML_CONFIG_HOST` (com Docker, no `.env`).
- Sem eles o painel roda do mesmo jeito: custo e imposto aparecem como **pendentes** e 2 testes são pulados com aviso.

## Começar

1. **Python 3.12** e, para rodar como servidor, **Docker**.
2. Pôr os arquivos de parâmetros em `analise/` (seção acima).
3. Copiar `.env.exemplo` para `.env` (na raiz) e ajustar. O `.env` é de cada PC e **nunca** vai para o repositório.
4. Testes (só precisam de `openpyxl`), na raiz:
   ```
   python -m unittest discover -s testes -t .
   ```
5. Rodar o painel, na raiz: `docker compose up -d --build` (ou, sem Docker, `instalar.ps1` uma vez e depois `rodar.ps1`).

## Regras do projeto

- **API do Mercado Livre só leitura** (só GET).
- **Sem dado de comprador:** pedidos entram por uma lista fechada de campos (`analise/ml_pedidos.py`); comprador, apelido,
  destinatário e endereço são descartados na leitura, nunca gravados nem mostrados.
- **Segredos e dados fora do git:** `.env`, tokens, arquivos de parâmetros, bancos e planilhas estão no `.gitignore`.
- **Um servidor só** guarda os tokens e atualiza (o refresh token do ML é de uso único); os usuários só abrem o endereço.
