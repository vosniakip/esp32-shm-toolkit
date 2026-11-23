# Dados e comandos

`INFO`, `START,5000`, `STOP` e `HELP` devem terminar com nova linha. `START` usa milissegundos; `--duracao` no Python usa segundos. A janela implementada vai de 0,1 s a 24 h.

| Campo CSV | Significado |
|---|---|
| indice | Evento observado, começa em zero; saltos indicam perda |
| t_us | Tempo DRDY relativo ao início, em microssegundos inteiros |
| ax_raw, ay_raw, az_raw | Aceleração assinada de 20 bits em LSB |
| temp_raw | Temperatura bruta 0–4095; −1 significa inválida |
| perdidas_acum | Total cumulativo de eventos observados sem amostra preservada |
| descartes_fila | Descartes por fila de transmissão cheia |
| leituras_descartadas | Leituras atrasadas ou com risco de incoerência temporal |
| erros_spi | Falhas detectadas na verificação de identidade/configuração |

O prefixo `D` e o CRC de quatro dígitos aparecem na serial, mas são retirados ao salvar o CSV já validado. O bruto contém inteiros, sem casas decimais. Zero em `erros_spi` não garante detecção de toda corrupção de amostra.

O JSON inclui: formato `ADXL355_S3_V1`; exemplar em `sensor`; ensaio, posição, repetição e observação; `configuracao` recebida em INFO; horários do computador; `fim_firmware`; totais recebidos; linhas inválidas; `captura_completa`, interrupção e erro; hash do CSV e hashes dos fontes locais. Os horários do computador não sincronizam nós diferentes. Os campos de INFO chegam como strings e são convertidos explicitamente nas análises.

O log guarda comandos, mensagens e linhas rejeitadas, sem duplicar todas as amostras válidas. CSV, JSON e log devem ser preservados juntos.

Nas tabelas, `g` é aceleração dividida por 9,80665 m/s²; mg é milésimo de g; `ug` significa µg. `g2_hz` significa g²/Hz; `ug_raiz_hz`, µg/√Hz. RMS centralizado remove a média; RMS filtrado depende do filtro; RMS de banda vem da integral da PSD. Não compare essas métricas sem considerar banda e janela.

`calibracao.json` contém offsets em LSB e sensibilidades em LSB/g, vinculados a um exemplar/faixa. `analise.json` registra as entradas, hashes, parâmetros e estado da análise. Resultados de uma pasta com estado `falhou` ou `em_execucao` não devem ser tratados como concluídos.

## Metadados e calibração matricial — pacote 2.0.0

- `versao_pacote`: versão do Python/documentação; distinta de `fw` do firmware.
- `montagem`: identificador da relação física sensor/base, por exemplo NO01_M1.
- `referencial_posicao`: referência usada ao orientar e rotular a captura (conjunto, sensor ou nao_definido). Não altera os valores brutos.
- `formato=calibracao_adxl355_matriz_v1`: calibração de 12 parâmetros.
- `offset_lsb`: três offsets no referencial dos canais brutos.
- `matriz_correcao_g_lsb`: matriz 3×3, linha = saída Xn/Yn/Zn, coluna = entrada X/Y/Z bruta.
- `matriz_resposta_lsb_g`: modelo direto, r = A_lsb_g * a_ref + b.
- `referencial_saida`: nome conjunto e descrição de Xn/Yn/Zn.
- `configuracao_calibracao`: faixa, taxa, LPF e HPF que devem coincidir com a aplicação.
- `arquivos_ajuste`: caminhos, hashes de CSV/JSON, posição e repetição.
- `diagnostico_ajuste`: resíduos e metas; não é validação independente.
- `status=ajustada_nao_validada`: ajuste criado; verificar o relatório separado de validação.

Com a matriz, ax_g/ay_g/az_g e ax_ms2/ay_ms2/az_ms2 são componentes do conjunto. ax_raw/ay_raw/az_raw continuam no referencial do sensor. Sem matriz, as componentes seguem o sensor. As unidades e o referencial devem acompanhar qualquer tabela/figura utilizada no TFC.

A validação registra `calibracao_sha256`, fontes independentes, referências, erros por componente em mg, erro vetorial em mg, erro de módulo em % e erro angular em graus. `analise.json: concluida` é conclusão do cálculo; a aprovação de triagem está em `resumo.atende_metas_exploratorias`.
