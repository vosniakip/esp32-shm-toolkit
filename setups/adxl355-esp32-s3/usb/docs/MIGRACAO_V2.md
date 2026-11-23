# Migrar para o pacote 2.0.0

## Firmware, USB e pastas

O firmware SPI/DRDY continua sendo 1.0.0, com protocolo ADXL355_S3_V1, baud e pinagem preservados. Se suas aquisições já funcionam com esse firmware, não é necessário novo upload. A versão 2.0.0 identifica o pacote Python/documentação, não o binário da placa.

Extraia em uma pasta nova para conservar a versão anterior. Crie/atualize o ambiente virtual usando requirements.txt. Copie os pares CSV/JSON e os logs, ou forneça caminhos absolutos da pasta antiga aos analisadores. Mantenha a identidade ADXL355-01 para o mesmo exemplar. O hash do CSV deve continuar igual; não salve o bruto pelo Excel.

## Calibração atual

O JSON diagonal antigo continua sendo aplicado por `--calibracao`. Para repetir o método diagonal, use `03_calibrar_seis_posicoes.py ... --modelo diagonal`. A partir desta versão, o padrão dos dois programas 03 é a matriz completa.

Para gerar a matriz do conjunto inclinado, faça novas aquisições com as seis posições da base controladas, `--montagem NO01_M1 --referencial conjunto`, conforme CALIBRACAO_COMPLETA.md. Os resíduos antigos não comprovaram poses suficientemente controladas para substituir essa nova campanha. Não existe uma conversão direta do JSON diagonal que determine a rotação da soldagem.

## Reprocessar brutos anteriores

Os brutos anteriores podem receber a nova matriz quando são do mesmo sensor, da mesma configuração e da mesma relação rígida entre sensor e base. Quando falta o metadado de montagem, confirme explicitamente essa identidade:

```powershell
.\.venv\Scripts\python.exe .\python\08_analisar_dinamico.py "CAMINHO_ANTIGO\aquisicao.csv" --calibracao "CAMINHO_NOVO\calibracao.json" --confirmar-montagem NO01_M1 --eixo z
```

Essa declaração não muda os arquivos originais. Se uma captura já registra uma montagem diferente, o programa a recusa. A confirmação não deve ser usada para contornar uma troca real da fixação. A nova calibração e os resultados gerados possuem hashes próprios e pastas exclusivas.

O validador exige novas aquisições com metadados completos de posição e montagem. Registros antigos de ruído ou vibração podem ser reprocessados sem servir como referências de validação estática.

## Relação entre eixos

Sem calibração e com o JSON diagonal antigo, X/Y/Z representam canais do sensor. Com a matriz nova, ax_g/ay_g/az_g representam Xn/Yn/Zn do conjunto; --eixo auto escolhe o maior RMS nesses eixos corrigidos. As colunas brutas nunca mudam de significado.

Mudança da orientação do nó na estrutura deve ser documentada separadamente. Se alterar a inclinação relativa sensor/base, a calibração anterior precisa ser revista.
