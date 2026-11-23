# Versão 2.0.0 — 2026-10-05

- Calibração completa por matriz 3×3 e offsets, no referencial da base do conjunto.
- Modelo direto por mínimos quadrados, inversão verificada e diagnóstico de pares opostos.
- Validação estática em novos arquivos, com referências conhecidas e erros de componente/módulo/direção.
- Aplicação da matriz a funcional, ruído, repetibilidade, deriva, dinâmico e Allan.
- Metadados de montagem e referencial; reprocessamento explícito de brutos legados.
- Exportação do sinal corrigido em novo CSV e rastreabilidade do JSON da calibração.
- Método diagonal e JSONs legados preservados; scripts 03 usam matriz por padrão.
- Roteiro de poses, guia de migração, referências e testes numéricos atualizados.

O firmware de aquisição permanece byte a byte igual à versão 1.0.0. A versão 2.0.0 é do pacote Python/documentação. A matriz real é calculada em novos ensaios; não há coeficientes de um sensor físico incluídos.

# Versão 1.0.0 — 2026-09-21

Pacote independente ADXL355/ESP32-S3 com a pinagem informada. SPI/DRDY, 500 Hz e ±2 g iniciais, timestamps de 64 bits, validação de identidade/configuração, fila e CRC serial, captura com preservação de parciais, análises de bancada, saídas exclusivas com data/hora, resumos XLSX, manuais, referências e testes.

Não inclui OTA, Wi-Fi, microSD ou sincronização entre sensores. Não mistura os protocolos e as escalas dos pacotes ADXL345 e MPU.
