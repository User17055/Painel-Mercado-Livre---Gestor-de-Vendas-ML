# instalar.ps1 - SEM Docker: cria o ambiente do painel (.venv com Python 3.12) e instala requirements.txt (so ASCII: PowerShell 5.1)
# Uso (de qualquer pasta, em qualquer PC com Python 3.12):  powershell -ExecutionPolicy Bypass -File <projeto>\painel\sistema\instalar.ps1
# Com Docker nao precisa deste arquivo (ver compose.yaml). Precisa de internet (baixa os pacotes do PyPI).
$sistema = $PSScriptRoot
$venv = Join-Path $sistema ".venv"
if (-not (Test-Path $venv)) { & py -3.12 -m venv $venv }
& (Join-Path $venv "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $venv "Scripts\python.exe") -m pip install -r (Join-Path $sistema "requirements.txt")
