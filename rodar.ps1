# rodar.ps1 - SEM Docker: abre o painel no navegador (http://localhost:8501). So ASCII (PowerShell 5.1).
# Uso: powershell -ExecutionPolicy Bypass -File <projeto>\rodar.ps1
# Pastas e opcoes: variaveis de ambiente (ML_DADOS_DIR, ML_CONFIG_DIR, PAINEL_PERMITE_ATUALIZAR...; ver painel\nucleo\caminhos.py).
# Sem nenhuma variavel, usa as pastas do proprio projeto (analise\ e dados\).
$raiz = $PSScriptRoot
$py = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Rode antes: instalar.ps1"; exit 2 }
& $py -m streamlit run (Join-Path $raiz "painel\app.py") --server.address localhost
