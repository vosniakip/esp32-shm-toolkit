> Pacote 2.0.0: o firmware permanece 1.0.0. Para a nova calibração do conjunto inclinado, siga CALIBRACAO_COMPLETA.md após verificar aquisição e temporização.

# Primeira leitura no Windows

## 1. Ligue e grave

Siga `LIGACOES_E_ARDUINO.md`, incluindo a tabela dos sete fios e a escolha de USB nativo ou UART. Coloque o ADXL355 imóvel sobre base firme e eletricamente isolada; não apoie terminais em metal.

No Monitor Serial, selecione 921600 baud e Nova linha. Envie `INFO`. Confira `pronto=1`, `devid_ad=0xAD`, `devid_mst=0x1D`, `partid=0xED`, `fs_nominal_hz=500` e `faixa_g=2`.

Envie `START,5000`. Durante cinco segundos devem aparecer linhas `D`; ao final, `#END` com aproximadamente 2500 amostras enviadas e zero perdas/erros. Em ±2 g, aproximadamente +256000 ou −256000 LSB representam +1 g ou −1 g. A gravidade se distribui entre os eixos quando o sensor está inclinado; a norma fica próxima de 1 g.

## 2. Prepare o Python

Extraia o ZIP. Abra a pasta `ADXL355_ESP32S3_Ensaios`, onde estão `README.md`, `requirements.txt`, `firmware` e `python`. Na barra de endereço do Explorador, digite `powershell` e pressione Enter.

Execute um comando por vez:

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Se `py` não existir, instale Python de 64 bits pelo [site oficial](https://www.python.org/downloads/windows/) e reabra o PowerShell. A validação usou Python 3.12. Não copie a pasta `.venv` de outro pacote/computador.

## 3. Salve 30 segundos

Feche Monitor Serial e Serial Plotter. Liste as portas:

```powershell
.\.venv\Scripts\python.exe .\python\00_listar_portas.py
```

Se for COM3:

```powershell
.\.venv\Scripts\python.exe .\python\01_capturar.py --porta COM3 --duracao 30 --ensaio funcional --posicao Zpos --sensor ADXL355-01 --repeticao 1 --montagem NO01_M1 --referencial conjunto
```

Substitua a porta pela sua. Use Zpos apenas se tiver identificado a orientação positiva de Z; caso contrário use `--posicao na` nesta verificação exploratória. `--sensor` identifica o exemplar físico; mantenha esse nome para ele nos ensaios seguintes.

Aguarde a conclusão. São esperadas aproximadamente 15000 amostras. O capturador imprime caminhos para CSV, JSON e log. Se houver erro, os arquivos parciais ficam preservados, mas não devem ser considerados uma aquisição aprovada.

## 4. Analise

Copie o caminho real de `aquisicao.csv` mostrado pelo programa. Coloque-o entre aspas nestes comandos:

```powershell
.\.venv\Scripts\python.exe .\python\02_verificar_funcional.py "CAMINHO_REAL\aquisicao.csv"
.\.venv\Scripts\python.exe .\python\05_analisar_temporizacao.py "CAMINHO_REAL\aquisicao.csv"
```

`CAMINHO_REAL` é um marcador: substitua-o. Cada programa mostra uma pasta nova de resultados. Abra os XLSX e PNG dessa pasta. Preserve o CSV original e seu JSON.

Confira gravidade plausível, taxa próxima de 500 Hz, ausência de perdas e sinais longe dos limites digitais. Os avisos de 5% na norma e de 1% na temporização são critérios de triagem do projeto, não tolerâncias de calibração certificada.

## 5. Encerre

Espere o programa informar os arquivos salvos antes de desconectar. Ctrl+C uma vez interrompe e preserva um registro parcial. Desconecte o USB antes de alterar os fios.
