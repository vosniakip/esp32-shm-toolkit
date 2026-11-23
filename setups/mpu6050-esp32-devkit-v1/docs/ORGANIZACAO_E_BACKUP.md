# Organização, identificação e backup

## 1. Princípio

Os dados brutos são imutáveis. Qualquer correção, remoção de registro, filtro,
calibração ou recorte deve produzir um novo arquivo em `dados/processados`.

## 2. Estrutura recomendada por campanha

O capturador cria automaticamente:

```text
dados/brutos/2026-08-21/repouso/
├── 20260821_143000_mpu6050-01_repouso_zpos_r01.csv
├── 20260821_143000_mpu6050-01_repouso_zpos_r01.json
└── 20260821_143000_mpu6050-01_repouso_zpos_r01.log.txt
```

Não renomeie apenas um desses três arquivos. Eles devem permanecer com o mesmo
nome-base.

## 3. Identificação dos sensores

Cole uma pequena etiqueta `MPU6050-01` no módulo ou na caixa. Se houver outro,
use `MPU6050-02`. Não use apenas “sensor novo” ou “sensor azul”.

Identifique também o ESP32, porque trocar o microcontrolador pode alterar a
temporização e a alimentação.

## 4. Versões de calibração

Quando recalibrar, não apague a calibração anterior. Crie, por exemplo:

```text
dados/calibracao/MPU6050-01/
├── 2026-08-21_calibracao_mpu6050-01.json
└── 2026-09-15_calibracao_mpu6050-01.json
```

Registre em cada análise qual arquivo de calibração foi aplicado.

## 5. Cópias de segurança

Use a regra 3-2-1:

1. três cópias;
2. em dois tipos de armazenamento;
3. uma cópia fora do computador principal.

Exemplo:

- pasta de trabalho no computador;
- SSD ou pendrive dedicado;
- Google Drive institucional.

Faça a primeira cópia imediatamente após cada campanha. Não espere o final do
TCC.

## 6. O que arquivar ao concluir uma campanha

- pasta `dados/brutos` daquele dia;
- JSON de calibração usado;
- pasta `dados/processados`;
- firmware `.ino`;
- pasta `python`;
- fotografias da montagem;
- ficha preenchida;
- versão do texto metodológico;
- identificação do instrumento profissional, quando usado.

## 7. Verificação de integridade

O JSON de captura guarda o hash SHA-256 do firmware-fonte. Para arquivos muito
importantes, também se pode calcular hash do CSV. No PowerShell:

```powershell
Get-FileHash "CAMINHO_DO_ARQUIVO.csv" -Algorithm SHA256
```

Salve o resultado em um arquivo de inventário. Se o hash mudar, o arquivo foi
alterado.

## 8. Planilha mestre

Mantenha uma planilha ou CSV com uma linha por aquisição:

- código do ensaio;
- nome do arquivo;
- sensor;
- ESP32;
- data e hora;
- posição;
- repetição;
- duração;
- temperatura;
- montagem;
- ocorrência;
- aprovado/rejeitado;
- motivo da rejeição;
- arquivo de calibração;
- versão do processamento.

