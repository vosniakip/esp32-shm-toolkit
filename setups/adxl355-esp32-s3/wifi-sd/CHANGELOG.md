# v3.0.0

- Novo firmware ESP32-S3 com dois controladores SPI, FIFO e pareamento DRDY.
- Fila RAM de 2048 registros; tarefas de aquisicao, armazenamento e controle.
- Controle HTTP local por navegador ou Python, sem dependencia da internet.
- Sequencias autonomas de repeticoes e partida automatica de uso unico em NVS.
- Modos de radio ativo ou desligado durante toda a sequencia.
- Armazenamento binario local com CRC32 por bloco, rodape, metadados e SHA-256.
- Download posterior retomavel, conversao verificada e ACK sem exclusao local.
- Analisadores e calibracao matricial da v2 preservados; verificacao de repeticoes
  passa a distinguir tambem montagem e modo de radio.
- Todos os nomes de saida de analises permanecem exclusivos por execucao.
- Novo guia completo em texto/PDF, esquemas vetoriais, roteiros e exemplos sinteticos.

Mudancas de operacao: 01_capturar.py utiliza Wi-Fi (--host), nao COM (--porta).
Monitor Serial em 115200 serve a diagnostico, sem stream de dados D.
Os formatos de transporte serial anteriores nao foram incluidos neste firmware.

A v2.0.0 original foi utilizada como base dos analisadores, modelos de calibracao
e testes numericos; nao foi sobrescrita nem teve seus dados modificados.
