# Bancada antes e depois das campanhas

O transporte mudou para Wi-Fi/microSD, mas o sentido físico dos ensaios permanece. Os scripts 02-12 recebem o CSV `aquisicao.csv` com seu JSON e preservam os brutos. A pasta de saída de cada análise é única.

## 1. Configuração e dados

Utilize os perfis de `configuracoes/bancada/`, conferindo sensor, montagem e calibração. Eles vieram da v3 e devem ser personalizados, assim como os perfis novos. A preparação e o comando remoto seguem o guia principal.

| Verificação | Aquisição sugerida | Programa |
| --- | --- | --- |
| Funcional | 30 s em repouso | 02_verificar_funcional.py |
| Calibração matricial | 3 registros por posição: X+, X-, Y+, Y-, Z+, Z- | 03_calibrar_matriz_completa.py |
| Validação independente | Novos registros, sem reajustar coeficientes | 11_validar_calibracao.py |
| Ruído/PSD | 5 x 120 s em repouso | 04_analisar_ruido_psd.py |
| Temporização | Registro curto e outro com duração da campanha | 05_analisar_temporizacao.py |
| Repetibilidade | Mesma montagem, aquisições independentes | 06_analisar_repetibilidade.py |
| Aquecimento | Partida a frio documentada e registro de 60 min | 07_analisar_deriva_termica.py |
| Vibração exploratória | Pequena excitação, sem saturação | 08_analisar_dinamico.py |
| Allan | Registro contínuo longo em repouso | 09_desvio_allan.py |

O script 16 executa roteiros de posições com confirmação de reposicionamento. As seis direções precisam estar definidas por uma referência mecânica do conjunto. Não estime a pose ideal usando o próprio acelerômetro a ser calibrado.

## 2. Exemplos de comandos

Defina o atalho nesta janela:

~~~powershell
$py = '.\.venv\Scripts\python.exe'
& $py .\python\02_verificar_funcional.py 'NO\aquisicao.csv'
& $py .\python\05_analisar_temporizacao.py 'NO\aquisicao.csv'
~~~

Calibração matricial dos dezoito arquivos selecionados, organizados em uma pasta exclusiva:

~~~powershell
& $py .\python\03_calibrar_matriz_completa.py `
  'DADOS_CALIBRACAO' --sensor adxl355-01 `
  --referencias .\fichas\orientacoes_calibracao.json
~~~

Confira as referências de posição antes de usar a ficha fornecida. A geometria é da base/conjunto: o módulo inclinado pode permanecer fixo. Não use uma referência ideal de X/Y/Z se o apoio estiver inclinado de maneira desconhecida.

A gravidade local é definida no ajuste por `--gravidade-local`, em m/s2, quando houver um valor fundamentado para a bancada. A convenção da unidade g no processamento é 9,80665 m/s2; a gravidade de referência já entra nos coeficientes ajustados. Não multiplique novamente por outro g local ao aplicar a matriz, pois isso faria uma segunda alteração de escala.

Valide com arquivos diferentes dos usados no ajuste:

~~~powershell
& $py .\python\11_validar_calibracao.py `
  'DADOS_VALIDACAO' --calibracao 'CAL\calibracao.json' `
  --referencias .\fichas\orientacoes_validacao.json
~~~

Para ruído e repetibilidade, passe a pasta exclusiva dos cinco registros:

~~~powershell
& $py .\python\04_analisar_ruido_psd.py `
  'DADOS_RUIDO' --calibracao 'CAL\calibracao.json'
& $py .\python\06_analisar_repetibilidade.py `
  'DADOS_RUIDO' --calibracao 'CAL\calibracao.json'
~~~

Os demais programas aceitam `--help`. O método diagonal antigo também está disponível, mas não substitui a correção matricial quando é necessário transformar as direções do módulo inclinado para as do conjunto.

## 3. Uso na campanha

Uma validação estática satisfatória não determina a resposta dinâmica, e baixo ruído não comprova o ganho no shaker. Os ensaios comparativos foram acrescentados para observar justamente essas propriedades. Preserve os dois grupos de resultados e identifique a configuração a que cada um se refere.
