$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) { throw 'Crear .venv e instalar watchflow/requirements.txt primero.' }
& $pythonExecutable -m watchflow.pipeline run
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
