# Ensaios do MPU-6050 (GY-521) com ESP32 DevKit V1

Este guia reúne a montagem e os ensaios de bancada do MPU-6050 (módulo GY-521) com o ESP32 DevKit V1. Comece com uma captura curta para conferir a comunicação e os eixos. Depois, use os scripts em Python para calibrar o sensor e avaliar os registros em repouso, durante o aquecimento e sob vibração.

## 1. Arquivos do pacote

```text
MPU6050_ESP32_Ensaios/
├── firmware/
│   └── mpu6050_aquisicao/
│       └── mpu6050_aquisicao.ino
├── python/
│   ├── comum.py
│   ├── 00_listar_portas.py
│   ├── 01_capturar.py
│   ├── 02_verificar_funcional.py
│   ├── 03_calibrar_seis_posicoes.py
│   ├── 04_analisar_ruido_psd.py
│   ├── 05_analisar_temporizacao.py
│   ├── 06_analisar_repetibilidade.py
│   ├── 07_analisar_deriva_termica.py
│   ├── 08_analisar_dinamico.py
│   ├── 09_desvio_allan.py
│   └── 10_gerar_resumo.py
├── dados/
│   ├── brutos/
│   ├── calibracao/
│   ├── processados/
│   ├── figuras/
│   └── logs/
├── templates/
├── docs/
└── requirements.txt
```

## 2. Ligação do sensor

| GY-521 | ESP32 DevKit V1 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO21 |
| SCL | GPIO22 |
| INT | GPIO27 |
| AD0/ADO | GND |
| XDA e XCL | Sem conexão |

Desconecte o USB antes de mudar a fiação. Os GPIO do ESP32 não devem receber 5 V.

Com `AD0` no GND, o sensor responde no endereço I²C `0x68`. O firmware também espera `0x68` no registrador `WHO_AM_I`. Se o identificador for diferente, a captura é interrompida para que o registro não seja associado ao MPU-6050 por engano.

## 3. Instalação no Windows

### Arduino IDE

1. No Arduino IDE, instale o pacote de placas `esp32 by Espressif Systems`.
2. Selecione `DOIT ESP32 DEVKIT V1`. Se essa opção não aparecer, use `ESP32 Dev Module`.
3. Abra `firmware/mpu6050_aquisicao/mpu6050_aquisicao.ino`.
4. Conecte o ESP32, selecione a porta, compile e grave o firmware na placa.
5. Feche o Monitor Serial antes de fazer a captura pelo Python. A porta precisa estar livre para o script.

`Arduino.h`, `Wire.h` e `esp_timer.h` já vêm com o pacote ESP32; não é preciso instalar uma biblioteca adicional para o sensor.

### Python

Instale o Python 3.10 ou superior. Abra o PowerShell na pasta deste guia e execute:

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Os exemplos já chamam o Python da pasta `.venv`. Você pode rodá-los sem ativar o ambiente virtual.

## 4. Porta serial

```powershell
.\.venv\Scripts\python.exe .\python\00_listar_portas.py
```

Anote a porta em que o ESP32 aparece. Os exemplos usam `COM5`; troque esse valor se a sua placa estiver em outra porta.

## 5. Primeiro registro

Deixe o eixo Z positivo voltado para cima e faça uma captura de 30 segundos:

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM5 --duracao 30 --ensaio funcional --posicao Zpos --repeticao 1
```

A captura salva três arquivos com o mesmo nome: o CSV de amostras brutas, o JSON de metadados e o log serial em `.log.txt`. Para verificar a leitura, copie o caminho do CSV exibido no terminal e use-o no lugar do exemplo abaixo:

```powershell
.\.venv\Scripts\python.exe .\python\02_verificar_funcional.py "dados/brutos/AAAA-MM-DD/funcional/ARQUIVO.csv"
```

## 6. Calibração em seis posições

Faça três capturas de 60 segundos em cada posição. Os comandos a seguir mostram a sequência para X positivo:

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM5 --duracao 60 --ensaio calibracao --posicao Xpos --repeticao 1
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM5 --duracao 60 --ensaio calibracao --posicao Xpos --repeticao 2
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM5 --duracao 60 --ensaio calibracao --posicao Xpos --repeticao 3
```

Repita para `Xneg`, `Ypos`, `Yneg`, `Zpos` e `Zneg`. Com as 18 capturas prontas, passe ao script a pasta de calibração do dia:

```powershell
.\.venv\Scripts\python.exe .\python\03_calibrar_seis_posicoes.py "dados/brutos/AAAA-MM-DD/calibracao" --sensor MPU6050-01
```

O ajuste salva os offsets e as sensibilidades em:

```text
dados/calibracao/calibracao_mpu6050-01.json
```

Associe o JSON ao sensor que foi calibrado. Se refizer o ajuste, guarde a versão anterior para saber quais coeficientes foram usados em cada análise. Essa calibração usa a gravidade para avaliar a resposta estática. Uma calibração dinâmica rastreável exige comparação com um sensor de referência.

## 7. Registros em repouso

Depois que o sensor aquecer, mantenha-o imóvel e grave cinco registros de 120 segundos. Mude `--repeticao` de 1 a 5 entre as capturas.

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM5 --duracao 120 --ensaio repouso --posicao Zpos --repeticao 1
```

Use a data real das capturas nos três comandos. Eles avaliam o ruído, a temporização das amostras e a repetibilidade entre os registros.

```powershell
.\.venv\Scripts\python.exe .\python\04_analisar_ruido_psd.py "dados/brutos/AAAA-MM-DD/repouso" --calibracao dados/calibracao/calibracao_mpu6050-01.json

.\.venv\Scripts\python.exe .\python\05_analisar_temporizacao.py "dados/brutos/AAAA-MM-DD/repouso"

.\.venv\Scripts\python.exe .\python\06_analisar_repetibilidade.py "dados/brutos/AAAA-MM-DD/repouso" --calibracao dados/calibracao/calibracao_mpu6050-01.json
```

## 8. Deriva no aquecimento

Deixe o conjunto desligado por pelo menos 30 minutos. Prepare o comando com antecedência para iniciar a captura de uma hora logo depois de energizar a placa.

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM5 --duracao 3600 --ensaio aquecimento --posicao Zpos --repeticao 1
```

Passe o CSV dessa captura ao script de deriva térmica:

```powershell
.\.venv\Scripts\python.exe .\python\07_analisar_deriva_termica.py "CAMINHO_DO_CSV.csv" --calibracao dados/calibracao/calibracao_mpu6050-01.json
```

## 9. Ensaio dinâmico

Faça cinco aquisições com a mesma fixação. O exemplo inicia a primeira repetição.

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM5 --duracao 120 --ensaio dinamico --posicao cantilever --repeticao 1
```

Para analisar os registros, indique a pasta do ensaio:

```powershell
.\.venv\Scripts\python.exe .\python\08_analisar_dinamico.py "dados/brutos/AAAA-MM-DD/dinamico" --calibracao dados/calibracao/calibracao_mpu6050-01.json --eixo auto --fmin 0.5 --fmax 50
```

Se a frequência de referência for conhecida, informe-a com `--freq-referencia`:

```powershell
.\.venv\Scripts\python.exe .\python\08_analisar_dinamico.py "dados/brutos/AAAA-MM-DD/dinamico" --calibracao dados/calibracao/calibracao_mpu6050-01.json --freq-referencia 7.85
```

Desde a versão 1.0.1, o programa cria uma subpasta para cada análise, identificada pela data, pela hora e pelo nome do primeiro CSV:

```text
dados/processados/dinamico/2026-09-02_14-35-20_mpu6050-01_dinamico_cantilever_r01/
```

Ali ficam as duas tabelas, as duas figuras e o `analise.json` com os parâmetros da execução. A opção `--saida` muda a pasta raiz; cada análise continua em uma subpasta própria. Sem uma frequência de referência, os registros permitem avaliar a repetibilidade do ensaio, mas não a exatidão da medição.

## 10. Desvio de Allan

O comando abaixo registra quatro horas:

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM5 --duracao 14400 --ensaio allan --posicao Zpos --repeticao 1
```

Use o CSV dessa captura na análise. Não aplique um filtro passa-altas antes de calcular o desvio de Allan.

```powershell
.\.venv\Scripts\python.exe .\python\09_desvio_allan.py "CAMINHO_DO_CSV.csv" --calibracao dados/calibracao/calibracao_mpu6050-01.json
```

## 11. Resumo dos resultados

```powershell
.\.venv\Scripts\python.exe .\python\10_gerar_resumo.py
```

O script salva o índice em `dados/processados/RELATORIO_RESUMO.md`.

## 12. Como guardar os registros

Mantenha os CSVs de `dados/brutos` como saíram da captura. Se precisar excluir uma amostra, anote o critério e aplique-o durante o processamento. Guarde o dado bruto, o JSON e o log com a calibração e a versão do código usados. Preserve também as tabelas e figuras resultantes.

Para mais detalhes, consulte:

- [Roteiro dos ensaios](docs/ROTEIRO_DE_ENSAIOS.md)
- [Como os scripts funcionam](docs/EXPLICACAO_DOS_CODIGOS.md)
- [Organização e backup](docs/ORGANIZACAO_E_BACKUP.md)
- [Dicionário dos dados](docs/DICIONARIO_DE_DADOS.md)
- [Referências](docs/REFERENCIAS.md)
- [Solução de problemas](docs/SOLUCAO_DE_PROBLEMAS.md)
