# syntax=docker/dockerfile:1
# Imagem do painel. Contexto do build = raiz do projeto (ver compose.yaml). Arquivos que entram: .dockerignore (lista fechada).
# Na imagem so entra CODIGO: dados, parametros e tokens ficam fora e entram como volume na hora de rodar (nada da empresa na imagem).
FROM python:3.12.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ML_ANALISE_DIR=/app/analise \
    ML_DADOS_DIR=/dados \
    ML_CONFIG_DIR=/config \
    ML_API_DIR=/segredos \
    PAINEL_PERMITE_ATUALIZAR=0

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# so os modulos de analise/ que o painel usa (mesma lista do .dockerignore; testes/test_pacote.py confere)
COPY analise/ml_param.py analise/ml_margem.py analise/ml_pedidos.py analise/ml_api.py /app/analise/
COPY painel /app/painel

# usuario sem privilegio; as pastas de volume existem mesmo sem volume montado
RUN useradd --create-home painel && mkdir -p /dados /config /segredos && chown painel /dados /segredos
USER painel

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["python", "-m", "streamlit", "run", "/app/painel/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
