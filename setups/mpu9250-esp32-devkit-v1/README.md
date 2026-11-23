# Ensaios do GY-9250 com ESP32 DevKit V1

O firmware registra a aceleração do módulo GY-9250/MPU-9250 com um ESP32 DevKit V1 e envia os dados pela porta serial. Os scripts em Python salvam as amostras e processam os ensaios. Faça primeiro uma captura curta na bancada; ela ajuda a conferir a comunicação antes da calibração e dos registros mais longos.

## 1. Arquivos do pacote

```text
GY9250_ESP32_Ensaios/
├── firmware/
│   └── gy9250_aquisicao/
│       └── gy9250_aquisicao.ino
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

| GY-9250 | ESP32 DevKit V1 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO21 |
| SCL | GPIO22 |
| INT | GPIO27 |
| AD0/ADO | GND |
| NCS/CS, se existir | 3V3 |
| EDA, ECL e FSYNC | Sem conexão |

Desconecte o USB antes de mudar a fiação. Os GPIO do ESP32 não devem receber 5 V. Confira também o identificador eletrônico nos metadados da captura: o nome impresso no módulo não substitui essa verificação.

## 3. Instalação no Windows

### Arduino IDE

1. No Arduino IDE, instale o pacote de placas `esp32 by Espressif Systems`.
2. Selecione `DOIT ESP32 DEVKIT V1`. Se essa opção não aparecer, use `ESP32 Dev Module`.
3. Abra `firmware/gy9250_aquisicao/gy9250_aquisicao.ino`.
4. Conecte o ESP32, selecione a porta, compile e grave o firmware na placa.
5. Feche o Monitor Serial antes de fazer a captura pelo Python. A porta precisa estar livre para o script.

`Arduino.h`, `Wire.h` e `esp_timer.h` já vêm com o pacote ESP32; não é preciso instalar uma biblioteca adicional para o sensor.

### Python

Instale o Python 3.10 ou superior. Abra o Prompt de Comando ou o PowerShell na pasta deste guia e execute:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Ao abrir outro terminal, volte à pasta do conjunto e ative o ambiente novamente. Substitua o caminho de exemplo pelo caminho no seu computador:

```powershell
cd CAMINHO\PARA\GY9250_ESP32_Ensaios
.venv\Scripts\activate
```

## 4. Porta serial

```powershell
python python/00_listar_portas.py
```

Anote a porta em que o ESP32 aparece. Os exemplos usam `COM5`; troque esse valor se a sua placa estiver em outra porta.

## 5. Primeiro registro

Deixe o eixo Z positivo voltado para cima e faça uma captura de 30 segundos:

```powershell
python python/01_capturar.py --porta COM5 --duracao 30 --ensaio funcional --posicao Zpos --repeticao 1
```

A captura salva três arquivos com o mesmo nome: o CSV de amostras brutas, o JSON de metadados e o log serial em `.log.txt`. Para verificar a leitura, copie o caminho do CSV exibido no terminal e use-o no lugar do exemplo abaixo:

```powershell
python python/02_verificar_funcional.py "dados/brutos/AAAA-MM-DD/funcional/ARQUIVO.csv"
```

## 6. Calibração em seis posições

Faça três capturas de 60 segundos em cada posição. Os comandos a seguir mostram a sequência para X positivo:

```powershell
python python/01_capturar.py --porta COM5 --duracao 60 --ensaio calibracao --posicao Xpos --repeticao 1
python python/01_capturar.py --porta COM5 --duracao 60 --ensaio calibracao --posicao Xpos --repeticao 2
python python/01_capturar.py --porta COM5 --duracao 60 --ensaio calibracao --posicao Xpos --repeticao 3
```

Repita para `Xneg`, `Ypos`, `Yneg`, `Zpos` e `Zneg`. Com as 18 capturas prontas, passe ao script a pasta de calibração do dia:

```powershell
python python/03_calibrar_seis_posicoes.py "dados/brutos/AAAA-MM-DD/calibracao" --sensor GY9250-01
```

O ajuste salva os offsets e as sensibilidades em:

```text
dados/calibracao/calibracao_gy9250-01.json
```

Associe o JSON ao sensor que foi calibrado. Se refizer o ajuste, guarde a versão anterior para saber quais coeficientes foram usados em cada análise. Essa calibração usa a gravidade para avaliar a resposta estática. Uma calibração dinâmica rastreável exige comparação com um sensor de referência.

## 7. Registros em repouso

Depois que o sensor aquecer, mantenha-o imóvel e grave cinco registros de 120 segundos. Mude `--repeticao` de 1 a 5 entre as capturas.

```powershell
python python/01_capturar.py --porta COM5 --duracao 120 --ensaio repouso --posicao Zpos --repeticao 1
```

Use a data real das capturas nos três comandos. Eles avaliam o ruído, a temporização das amostras e a repetibilidade entre os registros.

```powershell
python python/04_analisar_ruido_psd.py "dados/brutos/AAAA-MM-DD/repouso" --calibracao dados/calibracao/calibracao_gy9250-01.json

python python/05_analisar_temporizacao.py "dados/brutos/AAAA-MM-DD/repouso"

python python/06_analisar_repetibilidade.py "dados/brutos/AAAA-MM-DD/repouso" --calibracao dados/calibracao/calibracao_gy9250-01.json
```

## 8. Deriva no aquecimento

Deixe o conjunto desligado por pelo menos 30 minutos. Prepare o comando com antecedência para iniciar a captura de uma hora logo depois de energizar a placa.

```powershell
python python/01_capturar.py --porta COM5 --duracao 3600 --ensaio aquecimento --posicao Zpos --repeticao 1
```

Passe o CSV dessa captura ao script de deriva térmica:

```powershell
python python/07_analisar_deriva_termica.py "CAMINHO_DO_CSV.csv" --calibracao dados/calibracao/calibracao_gy9250-01.json
```

## 9. Ensaio dinâmico

Faça cinco aquisições com a mesma fixação. O exemplo inicia a primeira repetição.

```powershell
python python/01_capturar.py --porta COM5 --duracao 120 --ensaio dinamico --posicao cantilever --repeticao 1
```

Para analisar os registros, indique a pasta do ensaio:

```powershell
python python/08_analisar_dinamico.py "dados/brutos/AAAA-MM-DD/dinamico" --calibracao dados/calibracao/calibracao_gy9250-01.json --eixo auto --fmin 0.5 --fmax 50
```

Se a frequência de referência for conhecida, informe-a com `--freq-referencia`:

```powershell
python python/08_analisar_dinamico.py "dados/brutos/AAAA-MM-DD/dinamico" --calibracao dados/calibracao/calibracao_gy9250-01.json --freq-referencia 7.85
```

Desde a versão 1.0.1, o programa cria uma subpasta para cada análise, identificada pela data, pela hora e pelo nome do primeiro CSV:

```text
dados/processados/dinamico/2026-09-02_14-35-20_gy9250-01_dinamico_cantilever_r01/
```

Ali ficam as duas tabelas, as duas figuras e o `analise.json` com os parâmetros da execução. A opção `--saida` muda a pasta raiz; cada análise continua em uma subpasta própria. Sem uma frequência de referência, os registros permitem avaliar a repetibilidade do ensaio, mas não a exatidão da medição.

## 10. Desvio de Allan

O comando abaixo registra quatro horas:

```powershell
python python/01_capturar.py --porta COM5 --duracao 14400 --ensaio allan --posicao Zpos --repeticao 1
```

Use o CSV dessa captura na análise. Não aplique um filtro passa-altas antes de calcular o desvio de Allan.

```powershell
python python/09_desvio_allan.py "CAMINHO_DO_CSV.csv" --calibracao dados/calibracao/calibracao_gy9250-01.json
```

## 11. Resumo dos resultados

```powershell
python python/10_gerar_resumo.py
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
