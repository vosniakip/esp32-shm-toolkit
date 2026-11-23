# Roteiro dos ensaios

As durações, repetições e bandas propostas são decisões iniciais do projeto, não exigências de uma norma. Mantenha exemplar, faixa, taxa, filtro, montagem e condição térmica ao comparar resultados. Registre alterações em uma ficha e fotografe a montagem.

Um aquecimento inicial de 20 min pode servir de ponto de partida; o ensaio térmico verificará se esse tempo é suficiente. Abrir a porta UART pode reiniciar algumas placas, então observe o log e evite longas pausas entre capturas. O sensor permanece medindo enquanto o firmware está ocioso, mas um reset reexecuta sua inicialização.

Abra o PowerShell na raiz do projeto. Opcionalmente, defina uma variável para encurtar os comandos:

```powershell
$adxlPython = ".\.venv\Scripts\python.exe"
```

O operador `&` executa o caminho dessa variável. Substitua COM3 e todos os caminhos de exemplo.

## 1. Verificação funcional

Adquira 30 s imóvel e confirme a norma da gravidade. Antes da calibração, X/Y/Z são canais do sensor e podem apresentar componentes transversais com a base horizontal. Depois da matriz, Xn/Yn/Zn são os eixos definidos na base: a seta positiva vertical para cima corresponde à componente positiva. A etiqueta da posição usa a base quando `--referencial conjunto` é informado.

```powershell
& $adxlPython .\python\01_capturar.py --porta COM3 --duracao 30 --ensaio funcional --posicao Zpos --sensor ADXL355-01 --repeticao 1 --montagem NO01_M1 --referencial conjunto
& $adxlPython .\python\02_verificar_funcional.py "CAMINHO_DO_CSV"
& $adxlPython .\python\05_analisar_temporizacao.py "CAMINHO_DO_CSV"
```

Uma componente abaixo de 1 g pode resultar de inclinação; examine os três eixos e a norma. Não aplique passa-altas para avaliar offset/gravidade.

## 2. Calibração completa do conjunto

A versão 2.0.0 usa uma matriz 3×3 e três offsets, permitindo manter o ADXL355 inclinado quando está rigidamente preso à base. Oriente o conjunto pelo gabarito, nas direções Xn/Yn/Zn marcadas na base. Faça três capturas de 30 s por posição (Xpos, Xneg, Ypos, Yneg, Zpos, Zneg), com reposicionamento entre repetições e estabilização antes de cada captura.

Use a campanha `calibracao_completa`, declarando `--montagem NO01_M1 --referencial conjunto`. Ajuste com `03_calibrar_matriz_completa.py`. O nome antigo `03_calibrar_seis_posicoes.py` também usa a matriz por padrão; o método diagonal continua disponível com `--modelo diagonal`.

Siga o procedimento completo em [CALIBRACAO_COMPLETA.md](CALIBRACAO_COMPLETA.md), incluindo a identificação da montagem, os vetores conhecidos, os comandos, a interpretação dos resíduos e a validação em registros independentes com `11_validar_calibracao.py`.

A validação pode usar um gabarito de direções intermediárias conhecidas ou uma nova campanha nas seis faces com a referência correspondente. Metas vetorial/angular/de módulo são triagem do projeto. Nenhum coeficiente é gravado no sensor e o ajuste não comprova exatidão dinâmica nem rastreabilidade.

Com a matriz, as acelerações corrigidas representam Xn/Yn/Zn do conjunto. Registre a relação desses eixos com a estrutura. Os JSONs diagonais antigos continuam aceitos; [MIGRACAO_V2.md](MIGRACAO_V2.md) explica o reprocessamento de brutos sem montagem registrada.

## 3. Ruído e densidade espectral

Fixe o sensor em base pesada, em local quieto, sem ventilador próximo, espuma ou fios tensionados. Após estabilizar, faça cinco registros de 120 s na mesma posição e configuração.

```powershell
& $adxlPython .\python\01_capturar.py --porta COM3 --duracao 120 --ensaio ruido --posicao Zpos --sensor ADXL355-01 --repeticao 1 --montagem NO01_M1 --referencial conjunto
```

Repita para 2 a 5 e analise a pasta:

```powershell
& $adxlPython .\python\04_analisar_ruido_psd.py "PASTA_DAS_CINCO_CAPTURAS" --calibracao "CAMINHO_REAL\calibracao.json" --fmin 0.5 --fmax 50 --densidade-fmin 10 --densidade-fmax 40
```

São gerados PSD em g²/Hz, ASD em µg/√Hz, RMS em 0,5–50 Hz e densidade equivalente em 10–40 Hz. A região 10–40 Hz não é automaticamente livre de vibração nem branca: examine picos e inclinação. Justifique outras bandas e mantenha a mesma nas comparações.

A densidade observada inclui ambiente, montagem, alimentação e sensor. Não a chame de ruído intrínseco isolado. Comparações com datasheet devem considerar filtro, banda, convenção unilateral e condições do ensaio. A integração da PSD evita presumir que frequência de corte e largura equivalente de ruído sejam a mesma grandeza.

## 4. Temporização

Use os arquivos anteriores, sem adquirir um novo sinal:

```powershell
& $adxlPython .\python\05_analisar_temporizacao.py "CAMINHO_DO_CSV"
```

A 500 Hz, espere intervalo médio próximo de 2000 µs. Examine extremos, dispersão, histograma, lacunas e contadores. A taxa vem dos timestamps da placa, não da chegada USB. Zero perdas detectadas não prova ausência de todos os possíveis erros elétricos ou interrupções mascaradas.

## 5. Repetibilidade

Analise os cinco arquivos em repouso:

```powershell
& $adxlPython .\python\06_analisar_repetibilidade.py "PASTA_DAS_CINCO_CAPTURAS" --calibracao "CAMINHO_REAL\calibracao.json"
```

Compare médias, dispersão entre médias e RMS centralizado. Não use CV de médias próximas de zero; o programa fornece CV apenas para RMS positivo. Para avaliar remontagem, faça outra campanha retirando e recolocando o sensor e registre essa diferença de procedimento.

## 6. Aquecimento e deriva

Deixe o conjunto desligado por pelo menos 30 min. Mantenha ambiente estável, energize e inicie a captura tão logo a comunicação esteja disponível. Anote o atraso do boot/handshake: a primeira amostra não corresponde necessariamente ao instante de energização.

```powershell
& $adxlPython .\python\01_capturar.py --porta COM3 --duracao 3600 --ensaio aquecimento --posicao Zpos --sensor ADXL355-01 --repeticao 1 --montagem NO01_M1 --referencial conjunto
& $adxlPython .\python\07_analisar_deriva_termica.py "CAMINHO_DO_CSV" --janela 60
```

Não toque nem mova o conjunto. Analise médias por minuto, ruído centralizado, temperatura interna e deriva relativa à primeira janela. A temperatura do chip não é um termômetro ambiente calibrado. A regressão temperatura × aceleração é exploratória, pois temperatura e tempo podem variar juntos; não se aplica compensação automática.

## 7. Vibração livre em uma barra

Engaste uma extremidade e fixe rigidamente o conjunto próximo à ponta livre. Preserve a relação sensor/base usada na calibração. Se o ESP32 e o sensor já formam um único conjunto, mantenha a fixação do nó inteiro; sua massa também modifica a resposta da barra. Isole eletricamente a placa e evite espuma/folgas. Prenda os cabos perto do engaste e deixe uma curva de folga para não restringir o movimento.

Comece a captura, espere cerca de 10 s, desloque a ponta poucos milímetros e solte sem bater. Aguarde o decaimento; repita duas ou três vezes. Faça cinco arquivos, preservando geometria e excitação aproximada.

```powershell
& $adxlPython .\python\01_capturar.py --porta COM3 --duracao 120 --ensaio dinamico --posicao barra --sensor ADXL355-01 --repeticao 1 --montagem NO01_M1 --referencial conjunto
& $adxlPython .\python\08_analisar_dinamico.py "CAMINHO_DO_CSV" --eixo auto --calibracao "CAMINHO_REAL\calibracao.json"
```

Com a matriz, o eixo automático maximiza o RMS filtrado nos eixos Xn/Yn/Zn do conjunto. Para comparar depois, prefira fixar `--eixo x`, `y` ou `z`. O filtro padrão é 0,5–50 Hz e retira 2 s em cada extremidade para as métricas; os dados brutos ficam intactos. Padronize a duração: o RMS de todo o registro depende também dos períodos sem vibração.

Um pico reprodutível demonstra observação da frequência do conjunto barra + sensor + fios. Não prova exatidão dinâmica de amplitude. A inclinação variável também muda a projeção da gravidade. Se o sinal se aproxima dos limites digitais, reduza a excitação; mudar faixa exige regravar e usar calibração compatível.

## 8. Desvio de Allan

Após estabilização, registre duas a quatro horas imóvel, sem passa-altas e com temperatura estável. Evite suspensão do computador e garanta espaço livre.

```powershell
& $adxlPython .\python\01_capturar.py --porta COM3 --duracao 7200 --ensaio allan --posicao Zpos --sensor ADXL355-01 --repeticao 1 --montagem NO01_M1 --referencial conjunto
& $adxlPython .\python\09_desvio_allan.py "CAMINHO_DO_CSV" --calibracao "CAMINHO_REAL\calibracao.json" --pontos 60
```

O programa calcula Allan sobreposto até aproximadamente um décimo da duração, mostrando número de pares e de blocos não sobrepostos. Os pares não são independentes. O mínimo é descritivo, não uma estimativa automática de instabilidade de bias. Não são calculados intervalos de confiança.

Quatro horas a 500 Hz geram cerca de 7,2 milhões de amostras. Reserve aproximadamente 1 GB por aquisição como margem de disco, mais backup. Os analisadores carregam o registro em RAM; para esses arquivos longos, prefira computador com 16 GB e feche aplicações pesadas. Não tente abrir milhões de linhas em uma única planilha Excel; use os resumos.

## 9. Índice e comparação com referência

```powershell
& $adxlPython .\python\10_gerar_resumo.py .\dados\processados .\dados\calibracao
```

O índice informa a pasta e o estado das análises; não é certificado. Uma comparação dinâmica rastreável exige excitador, instrumento de referência, sincronização apropriada e orçamento de incerteza. A opção `--freq-referencia` do analisador apenas compara um número informado com o pico estimado; não implementa essa calibração completa.
