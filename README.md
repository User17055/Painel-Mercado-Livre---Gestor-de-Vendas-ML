# Gestor de Vendas ML

Painel web de vendas e lucro das contas do Mercado Livre **TUDOPRAPET (TPP)** e **PetDelivery (PD)**, com download em CSV e
Excel. Lê a API oficial do Mercado Livre **só para leitura** e **sem dado de comprador**.

**Estado:** esqueleto (estrutura, modelos, testes e Docker prontos; leitura dos pedidos pela API e telas ainda não feitas).
Detalhes e próximos passos: [`painel/docs/LEIA-ME.md`](painel/docs/LEIA-ME.md).

## Estrutura

```
painel/
  docs/        documentação: LEIA-ME (estado e como rodar), ARQUITETURA, PLANO (requisitos e fases)
  sistema/     código que roda: app Streamlit, núcleo, testes, Docker
analise/       módulos de regra usados pelo painel: parâmetros, custo e coletor de pedidos
```

## Começar

1. **Python 3.12** e, para rodar como servidor, **Docker**.
2. Copiar `painel/sistema/.env.exemplo` para `painel/sistema/.env` e ajustar. O `.env` é de cada PC e **nunca** vai para o
   repositório.
3. Testes (só precisam de `openpyxl`):
   ```
   python -m unittest discover -s painel/sistema/testes -t painel/sistema
   ```
   Sem os arquivos de parâmetros da empresa, 2 testes são pulados com aviso; é o esperado.
4. Rodar o painel: `docker compose up -d --build` na pasta `painel/sistema` (ou, sem Docker, `instalar.ps1` e `rodar.ps1`).

## Regras do projeto

- **API do Mercado Livre só leitura** (só GET).
- **Sem dado de comprador:** pedidos entram por uma lista fechada de campos (`analise/ml_pedidos.py`); comprador, apelido,
  destinatário e endereço são descartados na leitura, nunca gravados nem mostrados.
- **Segredos e dados fora do git:** `.env`, tokens, `ml_parametros.json`, `custos_produtos.csv`, bancos e planilhas estão no
  `.gitignore` e entram por variável de ambiente ou volume do Docker.
- **Um servidor só** guarda os tokens e atualiza (o refresh token do ML é de uso único); os usuários só abrem o endereço.
