$ErrorActionPreference = "Stop"

Set-Location -Path (Join-Path $PSScriptRoot '..')

Write-Host "Running Atlas offline test suite..."

python -m pytest -q
exit $LASTEXITCODE
