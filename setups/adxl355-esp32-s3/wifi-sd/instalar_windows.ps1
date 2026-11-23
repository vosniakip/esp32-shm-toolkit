$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -m venv .venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { python -m venv .venv }
    else { throw 'Instale Python 3.12 de 64 bits, reabra o terminal e execute novamente.' }
    if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel criar o ambiente virtual.' }
}
$TaskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $TaskPython -m pip install -r .\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Instalacao falhou. Consulte DNS/rede/proxy em docs/GUIA_COMPLETO.md; o ambiente virtual pode ja ter sido criado.' }
& $TaskPython .\python\00_controlar_no.py --help
Write-Host 'Ambiente preparado. Conecte-se a rede ADXL355-ENSAIOS para operar o no.'
