# Solução de problemas

| Sintoma | Ação |
|---|---|
| Python/py não encontrado | Instale Python e reabra PowerShell |
| .venv não existe | Execute `py -m venv .venv` na raiz do projeto |
| can't open file ...01\_capturar.py | Retire a barra antes de `_`; use `python\01_capturar.py` |
| Porta ocupada | Feche Monitor Serial, Plotter e outro capturador |
| Sem INFO | Confira porta COM, firmware ADXL355, baud e USB CDC On Boot |
| Texto ilegível na UART | Use 921600 baud; a mensagem de boot pode usar outro baud |
| Erro de upload | Confira placa S3, cabo de dados e BOOT + EN/RESET |
| pronto=0 ou IDs 00/FF | Desligue e confira 3V/GND, CS10, MISO13, MOSI11, clock12 e soldas |
| sem_drdy / nenhum dado | Terminal DRDY deve estar no GPIO14; INT1 não o substitui |
| timeout_transmissao | Confira cabo, USB/UART, baud e carga do computador |
| CRC inválido | Confira firmware/protocolo, baud e comunicação; preserve o log |
| Perdas/leituras descartadas | Analise intervalos, alimentação e cabos; se testar 250 Hz, registre a mudança em config.h e regrave |
| CSV alterado | Restaure o original; não remova hash para esconder edição |
| Falta JSON | Restaure o JSON daquele CSV, nunca de outra aquisição |
| Calibração recusada | Confira exemplar; matriz exige montagem, faixa, taxa e filtros iguais |
| Posições ausentes/invertidas | Confira etiquetas e orientação física; não force sensibilidade negativa |
| Dinâmico muito curto | Aumente duração ou ajuste banda/bordas com justificativa |
| Ruído com picos | Investigue ambiente e montagem antes de atribuir ao sensor |

Para diagnóstico, envie log, JSON, foto das ligações e comando utilizado. Os pacotes MPU/ADXL345 possuem escalas e protocolos diferentes; seus capturadores não devem ser usados aqui. Neste SPI, prender CS/SCL em 3V3 impede as transações.

A compilação e os testes simulados não verificam soldas, ruído de alimentação, autenticidade do componente ou desempenho dinâmico real. Comece por cinco segundos no Monitor Serial, depois 30 s salvos e temporização, antes de aquisições longas.

## Calibração completa — versão 2.0.0

| Mensagem/situação | Ação |
|---|---|
| Captura sem referencial conjunto | Oriente pela base e faça novas capturas com --referencial conjunto |
| Falta montagem | Nas novas capturas use --montagem NO01_M1, conservando essa fixação |
| Captura antiga sem montagem | Para reprocessar, confirme a mesma fixação por --confirmar-montagem NO01_M1; não contorne uma troca real da montagem |
| Repetição repetida | Use números 1, 2, 3 distintos por posição; não conte cópias como novas repetições |
| Posição ausente nas referências | Confira etiqueta e arquivo --referencias; padrão de ajuste é seis faces e padrão de validação é seis direções intermediárias |
| Matriz de referências sem posto 4 | Referências não cobrem três dimensões; revise as poses conhecidas |
| Referencial invertido | Confira sinais e os eixos de mão direita; evite trocar X/Y no rótulo |
| Dispersão elevada | Confira movimento, temperatura, apoio e fios; --max-dp-mg é triagem que exige justificativa |
| Validação contém CSV usado no ajuste | Faça novas aquisições; renomear/copiar não cria independência |
| Descrição de eixos diferente | Use a mesma definição de Xn/Yn/Zn nos JSONs de referências |
| Ajuste concluído mas validação não atende | Examine erros por componente/direção, gabarito, estabilidade e temperatura; não reajuste usando os mesmos registros de validação |
| Z corrigido difere do Z bruto | A matriz combina canais; Zn é normal à base e Z bruto é o canal inclinado do sensor |

Consulte CALIBRACAO_COMPLETA.md e MIGRACAO_V2.md para o procedimento operacional.
