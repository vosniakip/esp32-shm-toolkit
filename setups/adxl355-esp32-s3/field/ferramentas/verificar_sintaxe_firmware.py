"""Verificacao limitada de sintaxe C++ com interfaces de teste. Nao compila para ESP32-S3."""
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = shutil.which('g++')
if not compiler:
    raise SystemExit('g++ nao encontrado. Esta verificacao opcional nao substitui o Arduino IDE.')
cmd = [compiler, '-std=gnu++17', '-Wall', '-Wextra', '-Wno-misleading-indentation', '-Werror=return-type',
       '-DCONFIG_IDF_TARGET_ESP32S3=1', '-I' + str(root/'tests/native_stubs'), '-fsyntax-only',
       '-x', 'c++', str(root/'firmware/adxl355_wifi_sd/node.cpp'), str(root/'firmware/adxl355_wifi_sd/adxl355_wifi_sd.ino')]
subprocess.run(cmd, check=True)
print('Sintaxe C++ verificada com interfaces simuladas. Compilacao com o core Espressif e validacao fisica continuam necessarias.')
