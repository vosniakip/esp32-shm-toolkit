# Ensaios do ADXL355 com ESP32-S3 por USB

A versão 2.0.0 (5 de outubro de 2026) permite calibrar o ADXL355 já fixado à base, mesmo que ele esteja inclinado. O ajuste usa os eixos da montagem como referência e estima uma matriz 3×3 e os offsets para corrigir as diferenças de ganho e a mistura entre canais. A correção é feita no computador; o firmware continua na versão 1.0.0.

Se você já consegue capturar dados no formato `ADXL355_S3_V1`, pode seguir para a [calibração com o conjunto montado](docs/CALIBRACAO_COMPLETA.md) sem regravar a placa. Se for o primeiro uso, comece pelo [guia da primeira leitura](docs/PRIMEIRA_LEITURA.md).

## Ligação do módulo

| Inscrição no ADXL355 | ESP32-S3 | Função |
|---|---|---|
| GND | GND | Terra comum |
| VCC / 3V | 3V3 | Alimentação 3,3 V |
| DRDY | GPIO14 | Sinal de nova amostra |
| INT1 | Sem conexão | Não utilizado |
| SCLK | GPIO12 | Clock SPI |
| MISO/AS | GPIO13 | Dados do sensor para o ESP32-S3 |
| MOSI/SDA | GPIO11 | Dados do ESP32-S3 para o sensor |
| CS/SCL | GPIO10 | Seleção do sensor no SPI |

Com o USB desconectado, faça as sete ligações seguindo a numeração dos GPIO na placa. Ligue `CS/SCL` ao GPIO10; a alimentação de 3,3 V vai apenas ao pino `VCC / 3V`. Veja a [foto da montagem e as opções do Arduino IDE](docs/LIGACOES_E_ARDUINO.md).

## Parâmetros de aquisição

O ESP32-S3 lê o sensor por SPI em modo 0, a 1 MHz. O ADXL355 opera a 500 Hz, na faixa de ±2 g, com passa-baixas interno de 125 Hz, passa-altas desligado e escala nominal de 256000 LSB/g. O instante de cada amostra é registrado em 64 bits no evento DRDY. A identificação confere `DEVID_AD=0xAD`, `DEVID_MST=0x1D` e `PARTID=0xED`.

A serial está configurada para 921600 baud. O guia de montagem cobre o USB nativo e o conversor USB–UART. A taxa de 500 Hz dá margem para analisar de 0,5 a 50 Hz; para interpretar amplitudes, leve em conta a resposta do sensor e do filtro. Os parâmetros seguem a [ficha técnica do ADXL355](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl354_adxl355.pdf). Para selecionar 250 Hz ou as faixas de ±4 g e ±8 g, altere `config.h` e recompile.

## Instalação e primeira captura

Depois de extrair o ZIP, abra o PowerShell na pasta que contém este guia e o `requirements.txt`. Crie o ambiente, instale as dependências e liste as portas:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe .\python\00_listar_portas.py
```

Grave `firmware/adxl355_aquisicao/adxl355_aquisicao.ino` conforme o guia do Arduino IDE. Feche o Monitor Serial e faça a primeira captura, usando a porta do seu ESP32-S3 no lugar de `COM3`:

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM3 --duracao 30 --ensaio funcional --posicao Zpos --sensor ADXL355-01 --repeticao 1 --montagem NO01_M1 --referencial conjunto
```

O terminal mostra os caminhos de `aquisicao.csv`, `aquisicao.json` e `aquisicao.log.txt`. Guarde os três juntos. Nos comandos de verificação, troque o caminho de exemplo pelo caminho real do CSV:

```powershell
.\.venv\Scripts\python.exe .\python\02_verificar_funcional.py "CAMINHO_REAL\aquisicao.csv"
.\.venv\Scripts\python.exe .\python\05_analisar_temporizacao.py "CAMINHO_REAL\aquisicao.csv"
```

Os nomes dos scripts usam sublinhados, sem barra antes deles. Como os exemplos chamam o executável dentro de `.venv`, não é preciso ativar o ambiente virtual.

## Calibração do conjunto inclinado

Marque Xn, Yn e Zn na base. Use o gabarito para orientar o conjunto inteiro, mantendo a posição do ADXL355 em relação à base. A opção `--montagem NO01_M1` identifica a fixação, e `--referencial conjunto` indica que os rótulos das posições seguem os eixos da base. A serial continua transmitindo os valores brutos de X, Y e Z do sensor.

Para a primeira captura, deixe +Xn voltado para cima:

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM3 --duracao 30 --ensaio calibracao_completa --posicao Xpos --repeticao 1 --sensor ADXL355-01 --montagem NO01_M1 --referencial conjunto
```

Faça três repetições em cada posição: `Xpos`, `Xneg`, `Ypos`, `Yneg`, `Zpos` e `Zneg`. Com os 18 arquivos prontos, informe ao script a pasta da campanha:

```powershell
.\.venv\Scripts\python.exe .\python\03_calibrar_matriz_completa.py "dados\brutos\AAAA-MM-DD\calibracao_completa"
```

O ajuste gera `calibracao.json`, tabelas em XLSX e CSV, gráficos e um diagnóstico. Valide a matriz com novas capturas antes de usá-la nos ensaios. Use os coeficientes já calculados, sem reajustá-los com as amostras de validação:

```powershell
.\.venv\Scripts\python.exe .\python\11_validar_calibracao.py "PASTA_REAL_DA_VALIDACAO" --calibracao "PASTA_REAL_DO_AJUSTE\calibracao.json"
```

Por padrão, a validação lê em `fichas/orientacoes_validacao.json` as direções intermediárias `xypos`, `xyneg`, `xzpos`, `xzneg`, `yzpos` e `yzneg`. Use-as se tiver um gabarito verificado para essas direções. Outra opção é fazer uma nova campanha nas seis faces com `--referencias .\fichas\orientacoes_calibracao.json`, conforme o guia.

Para analisar ou exportar o registro com a matriz, indique o JSON do ajuste:

```powershell
.\.venv\Scripts\python.exe .\python\08_analisar_dinamico.py "CAMINHO_REAL\aquisicao.csv" --eixo z --calibracao "PASTA_REAL_DO_AJUSTE\calibracao.json"
.\.venv\Scripts\python.exe .\python\12_exportar_corrigido.py "CAMINHO_REAL\aquisicao.csv" --calibracao "PASTA_REAL_DO_AJUSTE\calibracao.json"
```

Com a matriz aplicada, `--eixo z` seleciona Zn da base. Na leitura sem calibração, a mesma opção seleciona Z do sensor. Se os dados antigos não identificam a montagem, use `--confirmar-montagem NO01_M1` somente quando souber que a fixação era a mesma. Consulte o [guia de migração](docs/MIGRACAO_V2.md). Se mudar a posição do sensor em relação à base, revise a calibração antes de aplicar a matriz.

## Programas

| Programa | O que faz |
|---|---|
| `00_listar_portas.py` | Identifica as portas USB/serial |
| `01_capturar.py` | Salva as amostras brutas em CSV, os metadados e o log |
| `02_verificar_funcional.py` | Confere as médias, o módulo da gravidade e a integridade do registro |
| `03_calibrar_matriz_completa.py` | Ajusta a matriz 3×3 e os offsets com todas as componentes |
| `03_calibrar_seis_posicoes.py` | Faz o mesmo ajuste por padrão; `--modelo diagonal` usa o método anterior |
| `04_analisar_ruido_psd.py` | Calcula PSD, ASD, RMS e densidade equivalente de ruído |
| `05_analisar_temporizacao.py` | Verifica a taxa, a variação dos intervalos e as perdas |
| `06_analisar_repetibilidade.py` | Compara capturas em repouso |
| `07_analisar_deriva_termica.py` | Analisa o aquecimento e a deriva por janelas |
| `08_analisar_dinamico.py` | Filtra o sinal, calcula o espectro e encontra a frequência dominante |
| `09_desvio_allan.py` | Calcula o desvio de Allan sobreposto |
| `10_gerar_resumo.py` | Reúne as análises e indica o estado de cada uma |
| `11_validar_calibracao.py` | Confere componentes, módulo e direção em novas capturas |
| `12_exportar_corrigido.py` | Exporta um CSV em g e m/s² e registra a transformação nos metadados |

`07_analisar_deriva_aquecimento.py` é outro nome para a análise térmica. Os analisadores aceitam `--help`. Você pode indicar vários CSVs separados por espaços ou a pasta de uma campanha. Escolha uma pasta que contenha somente as capturas do ensaio.

## Registros, resultados e limites

Cada captura e análise tem sua própria pasta, identificada por data, hora, microssegundos e um código exclusivo. Assim, repetir um comando não apaga a saída anterior. Para abrir as tabelas no Excel, prefira o XLSX, que já contém células numéricas.

O programa preserva os CSVs brutos e confere o hash na leitura. A captura verifica o CRC da serial e guarda o arquivo parcial em caso de falha. As análises espectrais recusam registros incompletos ou com perdas detectadas. Essa checagem do CRC cobre a transmissão serial, sem garantir a integridade de toda a comunicação SPI.

Os scripts de verificação funcional, ruído/PSD, repetibilidade, deriva, dinâmica e Allan aceitam a matriz por `--calibracao`. O ajuste também é aceito na exportação corrigida, e os JSONs do modelo diagonal continuam compatíveis. Os coeficientes são aplicados no computador, sem alterar os registradores do sensor. Use os do seu exemplar na montagem, faixa, taxa e filtros com que foi calibrado. O pacote não traz uma calibração pronta.

Este pacote foi feito para ensaios de bancada por USB. Para Wi-Fi e microSD, use o pacote correspondente. Aqui não há OTA nem sincronização entre nós. A calibração estática não verifica a resposta em amplitude e fase entre 0,5 e 50 Hz, e a flexão ou a ressonância da montagem ainda pode aparecer nas medições. Confira a leitura e a temporização na sua placa antes de iniciar registros longos.

## Documentação

- [Calibração completa com o conjunto inclinado](docs/CALIBRACAO_COMPLETA.md)
- [Migração e reutilização de registros brutos](docs/MIGRACAO_V2.md)
- [Primeira leitura](docs/PRIMEIRA_LEITURA.md)
- [Ligação e Arduino](docs/LIGACOES_E_ARDUINO.md)
- [Roteiro dos ensaios](docs/ROTEIRO_DE_ENSAIOS.md)
- [Como os scripts funcionam](docs/EXPLICACAO_DOS_CODIGOS.md)
- [Dicionário dos dados](docs/DICIONARIO_DE_DADOS.md)
- [Organização, Excel e backup](docs/ORGANIZACAO_E_BACKUP.md)
- [Solução de problemas](docs/SOLUCAO_DE_PROBLEMAS.md)
- [Referências](docs/REFERENCIAS.md)
- [Validação do software](docs/VALIDACAO.md)
