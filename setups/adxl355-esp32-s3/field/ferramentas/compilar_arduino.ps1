param([string]$CoreVersion = '3.3.2')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command arduino-cli -ErrorAction SilentlyContinue)) { throw 'Instale arduino-cli ou use o Arduino IDE conforme o guia.' }
$TaskIndex = 'https://espressif.github.io/arduino-esp32/package_esp32_index.json'
arduino-cli core update-index --additional-urls $TaskIndex
if ($LASTEXITCODE -ne 0) { throw 'Falha ao atualizar o indice. Verifique internet/DNS.' }
arduino-cli core install "esp32:esp32@$CoreVersion" --additional-urls $TaskIndex
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar o core.' }
arduino-cli compile --fqbn 'esp32:esp32:esp32s3:USBMode=hwcdc,CDCOnBoot=cdc,FlashSize=16M,PartitionScheme=huge_app,PSRAM=disabled' .\firmware\adxl355_wifi_sd
if ($LASTEXITCODE -ne 0) { throw 'Compilacao para ESP32-S3 falhou. Preserve a mensagem completa.' }
Write-Host 'Compilacao concluida. Este script nao faz upload. Confira a configuracao da sua placa antes de gravar.'
