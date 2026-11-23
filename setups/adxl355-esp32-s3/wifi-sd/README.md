# ADXL355 + ESP32-S3: ensaios com Wi-Fi e microSD

O firmware da versão 3.0.0 usa o Wi-Fi do nó para receber comandos de um computador ou celular. O ESP32-S3 executa os ensaios e grava as amostras brutas no cartão microSD, de onde podem ser baixadas depois. A matriz de calibração é aplicada no computador, durante a análise.

O [guia completo](docs/GUIA_COMPLETO.md) mostra a montagem, a instalação do software e a sequência de cada ensaio.

## Montagem e gravação

1. Com o conjunto desligado, confira as ligações pela tabela de pinos do guia.
2. Abra `firmware/adxl355_wifi_sd/adxl355_wifi_sd.ino` no Arduino IDE e revise `config.h`.
3. Selecione `ESP32S3 Dev Module` com o Arduino-ESP32 3.x. Use a configuração de flash da sua placa e uma partição com pelo menos 3 MB para o aplicativo.
4. Compile e grave o firmware pelo USB. No Monitor Serial, selecione 115200 baud e a opção Nova linha. Envie `INFO` para conferir a identificação.

## Primeira captura pela página do nó

Conecte o computador ou celular à rede `ADXL355-ENSAIOS`, com a senha inicial `Ensaio355!`. Abra `http://192.168.4.1`, confira a seção Identificação e inicie um ensaio funcional de 30 segundos. O cartão guarda os arquivos mesmo que o computador se desconecte. Aguarde o fim da gravação antes de transferir o registro.

## Captura e download pelo Python

A rede do nó funciona sem internet. Instale as dependências no computador antes de entrar nela:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Já conectado à rede do nó, consulte a identificação e, para baixar os registros concluídos, use:

```powershell
.\.venv\Scripts\python.exe .\python\00_controlar_no.py info
.\.venv\Scripts\python.exe .\python\13_baixar_dados.py --todos
```

Você também pode iniciar a captura pelo terminal:

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar_wifi.py --duracao 30 --ensaio funcional --posicao zpos --repeticao 1
```

O programa aguarda o fim da aquisição, baixa os arquivos, verifica SHA-256 e CRC32 e produz o CSV e o JSON. O script `01_capturar.py` também aceita esse fluxo. Para mudar o endereço do nó, passe `--host 192.168.4.1` em vez da opção serial `--porta COM3`; as amostras ficam no cartão.

Com Wi-Fi ativo, o nó responde aos comandos `STOP` e `STATUS`. Se usar `--radio desligado`, a conexão só volta quando a sequência termina. Para o ensaio de aquecimento a frio, há uma partida automática que é usada uma única vez. Esta versão não oferece atualização OTA, envio automático à nuvem ou sincronização validada entre nós.

## Onde encontrar os arquivos

| Se você precisa de… | Abra |
|---|---|
| Firmware e página web embarcada | `firmware/adxl355_wifi_sd/` |
| Instalação e comandos dos ensaios | [Guia completo](docs/GUIA_COMPLETO.md) |
| Formato binário, metadados e comandos HTTP | [API e formato dos arquivos](docs/API_E_FORMATO.md) |
| Funcionamento e matemática dos scripts | [Explicação dos códigos](docs/EXPLICACAO_DOS_CODIGOS.md) |
| Fontes e limites dos ensaios | [Referências](docs/REFERENCIAS.md) |
| Roteiros prontos | `configuracoes/` |
| Eixos e direções de referência para a calibração | `fichas/` |
| Scripts de captura e análise | `python/` |
| Como testar sem o nó | [Testes locais](exemplos/LEIA_ME.md) |
| Testes | `tests/` |

Cada análise cria uma pasta com data, hora e identificador. Guarde o CSV e o JSON juntos. Se abrir o CSV bruto no Excel, faça as alterações em uma cópia.

## O que foi verificado

Os testes cobrem a análise dos sinais, o ajuste da matriz, a leitura binária e o cliente HTTP com dados sintéticos e um servidor local simulado. Também comparam o CRC32 em C++ com o leitor Python. A verificação de sintaxe C++ usa interfaces de teste; o pacote não inclui um firmware pré-compilado. Compile com o core Espressif e confirme o funcionamento com a sua placa, sensor e cartão. O [relato da validação](docs/VALIDACAO.md) descreve o que os testes verificam.
