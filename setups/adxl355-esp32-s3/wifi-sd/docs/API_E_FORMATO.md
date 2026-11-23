# API, arquivos e definicoes v3

Este documento e o contrato entre firmware, navegador e Python. Endereco
padrao: http://192.168.4.1. Os comandos POST usam application/x-www-form-urlencoded.
As respostas de controle sao JSON UTF-8, sem cache. O modo AP utiliza a senha
de config.h; nao ha autenticacao HTTP adicional nem exposicao planejada a internet.

## Rotas

| Metodo e rota | Conteudo e condicao |
|---|---|
| GET / | Pagina embarcada; nao depende de CDN/internet |
| GET /api/info | IDs em cache, disponibilidade e recursos |
| GET /api/status | Estado, ultimo request_id, campanha, contagens e erros |
| POST /api/clock | epoch_ms do computador; apenas ocioso; nao sincroniza nos |
| POST /api/start | Programa uma sequencia; retorna 202 quando aceita |
| POST /api/stop | Solicita parada e cancela repeticoes restantes |
| POST /api/autostart | Salva uma unica partida futura em NVS, ou desarma |
| GET /api/files?offset=0 | Ate 50 campanhas; bloqueado durante a sequencia |
| GET /api/download?run=ID&kind=bin | Arquivo; kind tambem pode ser meta, manifest ou log |
| GET /api/download?...&offset=N | Retomada em bytes; resposta 206 se N > 0 |
| POST /api/ack | run e sha256: registra recebimento, sem apagar dados |

Erro HTTP 400 indica parametro invalido; 404 arquivo/rota ausente; 409 estado
ocupado ou conflito; 416 offset invalido; 503 sensor/cartao/tarefas indisponiveis.
O cliente nao deve transformar timeout de START em outro request_id por tentativa.
O firmware reconhece novamente apenas o ultimo request_id mantido em RAM.

## Parametros de START e da partida automatica

| Campo | Padrao | Limites/interpretacao |
|---|---|---|
| request_id | Obrigatorio em START | 1-64 caracteres ASCII seguros |
| sensor | adxl355-01 | Identificacao do exemplar, ate 24 caracteres |
| montagem | pcb-inclinada-v1 | Identificacao geometria sensor/base, ate 32 |
| ensaio | funcional | Etiqueta, ate 24 |
| posicao | zpos | Etiqueta do gabarito, ate 24 |
| referencial | conjunto | conjunto ou sensor |
| duracao_s | 30 | Inteiro de 1 a 21600, por arquivo |
| taxa | 500 | 250 ou 500 Hz |
| faixa | 2 | 2, 4 ou 8 g nominais |
| repeticao | 1 | Numero inicial, 1-999 |
| repeticoes | 1 | Quantidade autonoma, 1-20; ultimo numero <= 999 |
| intervalo_s | 10 | 0-3600 s entre arquivos |
| atraso_s | 5 | 0-3600 s antes de cada aquisicao |
| radio | ativo | ativo ou desligado |
| calibracao_id | nao-aplicada | Identificacao apenas; coeficientes nao vao para o sensor |
| nota | Vazia | Ate 240 bytes UTF-8 |

Identificadores permitem A-Z, a-z, 0-9, _ e -. Nao sao caminhos arbitrarios.
Autostart recebe os mesmos parametros, exceto request_id, e habilitar=1.
habilitar=0 desarma. A flag e consumida antes de executar na proxima partida.
As configuracoes de autostart persistem em NVS; relogio e ultimo request_id nao.

Uma sequencia tem uma unica posicao fisica e varias repeticoes. Mudanca de pose
e conduzida pelo operador/roteiro Python, que so envia a proxima etapa depois
de confirmacao. Uma sequencia aceita e autonoma; um roteiro de varias poses
depende da intervencao e do cliente para cada nova etapa.

## Estados e concorrencia

O firmware percorre preparando, aguardando_inicio, adquirindo, esvaziando_buffer,
finalizando e concluido. Pode entrar em intervalo entre registros, interrompido
por parada manual ou falha por erro. STATUS nao consulta o cartao durante a aquisicao: usa uma
fotografia protegida dos contadores em RAM. Downloads e listagens ficam bloqueados
enquanto ocupado=true. O aplicativo gera hashes depois de fechar raw.bin.

O motivo tempo_concluido distingue o termino programado. STOP, cancelamento,
FIFO perdido, desalinhamento, fila cheia, configuracao invalida ou falha de SD
nao sao tratados como aquisicoes aprovadas. Uma sequencia pode conter arquivos
concluidos antes da falha em uma repeticao seguinte; examine os JSONs de cada um.

## Binario little-endian

O arquivo e uma sequencia: cabecalho fixo, blocos e rodape. Nao possui CSV textual
nem compressao com perdas. As estruturas C++ sao packed; o leitor Python explicita
little-endian e os tamanhos. Os timestamps sao de 64 bits, inclusive em Allan longo.

Cabecalho, 64 bytes: `<8sHHHHIIQ32s`.

| Offset | Tamanho | Campo |
|---|---|---|
| 0 | 8 | A355SD3 seguido de byte zero |
| 8 | 2 | Versao = 3 |
| 10 | 2 | Tamanho do cabecalho = 64 |
| 12 | 2 | Tamanho do registro = 32 |
| 14 | 2 | Reservado = 0 |
| 16 | 4 | Taxa nominal, Hz |
| 20 | 4 | Faixa nominal, g |
| 24 | 8 | Duracao solicitada, microssegundos |
| 32 | 32 | run_id ASCII terminado/preenchido com zero |

Bloco, cabecalho de 16 bytes: `<4sIHHI`.

| Campo | Definicao |
|---|---|
| magic | BLK3 |
| sequence | uint32, inicia em zero e aumenta um por bloco |
| records | uint16, de 1 a 128 |
| recordBytes | uint16, sempre 32 |
| crc32 | CRC32 IEEE do payload inteiro (polinomio refletido 0xEDB88320) |

Cada registro, 32 bytes: `<QQiiihH`.

| Campo | Tipo | Significado |
|---|---|---|
| index | uint64 | Sequencia DRDY relativa ao primeiro registro aceito |
| timeUs | uint64 | ISR DRDY observado, relativo ao inicio do intervalo |
| x, y, z | int32 cada | Valor bruto de 20 bits estendido com sinal |
| temperature | int16 | ADC de temperatura, 0-4095; -1 se invalido |
| flags | uint16 | Bit 0: temperatura atualizada; bit 1: temperatura invalida |

A temperatura e lida nominalmente uma vez por segundo e mantida nos demais
registros. Ela nao e uma nova medicao independente a cada linha. O tempo nao e
o instante de escrita nem de chegada pela rede. A borda DRDY sucede o processamento
interno do sensor e incorpora o comportamento de seu filtro; nao representa
automaticamente a fase de uma referencia mecanica externa.

Rodape, 16 bytes: `<4sIQ`, contendo END3, numero de blocos e total de registros.
Qualquer byte excedente, indice decrescente, contagem divergente ou CRC invalido
causa rejeicao. Na recuperacao parcial, somente o prefixo de blocos inteiros e
considerado; CRC incorreto continua sendo erro. O binario sozinho nao permite
recuperar identificacao da montagem, posicao e todas as condicoes de aquisicao.

## JSON e integridade

meta.json tem schema ADXL355_SD_META_V3. Contem configuracao, IDs de campanha,
referencial, repeticao, modo de radio, pre-roll, tempo desde boot, hora civil
quando recebida do PC, contagens e motivo. arquivo_finalizado significa que o
arquivo foi fechado com rodape; captura_completa exige tambem termino programado.

manifest.json tem schema ADXL355_SD_MANIFEST_V3. Guarda SHA-256 e tamanho do
raw.bin, hashes do meta.json/events.log e contagens. CRC32 cobre cada payload;
SHA-256 compara os arquivos completos recebidos com os arquivos armazenados.
Essas verificacoes nao detectam um erro fisico ocorrido antes de os dados serem
registrados nem fornecem autenticacao criptografica contra um invasor do no.

raw.bin.part indica aquisicao ainda em andamento ou que nao pode ser finalizada.
Um arquivo com rodape pode corresponder a STOP/falha: leia meta.json. recebido.json
e somente um recibo de ACK; nao e apagamento nem uma segunda copia de seguranca.

## CSV compativel com os analisadores

A conversao cria aquisicao.csv e aquisicao.json, formato ADXL355_S3_V1, com:
indice,t_us,ax_raw,ay_raw,az_raw,temp_raw,perdidas_acum,descartes_fila,
leituras_descartadas,erros_spi,flags. Nenhuma calibracao e aplicada.

Os contadores de falha conhecidos apenas no fim sao anexados na ultima linha
e no JSON. perdas_acum inclui lacunas de indice observadas e um limite inferior
de perdas reportado pelo firmware. Nao interprete a ultima linha como o instante
fisico exato em que ocorreu cada falha. O JSON mantem os contadores especificos.

O conversor verifica o manifesto, compara cabecalho/JSON, blocos/rodape e salva
o hash do CSV. O leitor comum recusa CSV alterado pelo Excel. Em recuperacao
parcial, o JSON permanece captura_completa=false, de modo que PSD, Allan e
calibracao nao aceitam o registro como continuo/aprovado.
