# Explicação dos códigos e cálculos

## Firmware único

`config.h` concentra pinos, taxa, faixa e baud. `codec.h` contém decodificação de 20 bits e CRC. `adxl355_aquisicao.ino` controla a inicialização, aquisição e transmissão. O programa não usa Wi-Fi, SD nem temporizador do computador para gerar a amostragem.

O ADXL355 é identificado, reinicializado e configurado em standby. Depois começa a medir, e a configuração é lida de volta. `pronto=1` exige IDs e registradores compatíveis. `START` abre uma janela de captura; não reseta o sensor em cada arquivo. Um reset da placa por EN ou abertura da serial, por outro lado, reexecuta a inicialização.

### DRDY, timestamps e integridade

A interrupção registra `esp_timer_get_time()` em uma variável de 64 bits e incrementa um contador, com seção crítica curta. Não faz SPI ou impressão dentro da ISR. O laço principal compara contadores e lê o bloco de nove bytes da aceleração. Eventos intermediários observados sem leitura são contados como perdidos. Leituras atrasadas ou atravessadas por outro DRDY são descartadas para reduzir incoerência entre eixos.

A cada segundo, uma leitura de identidade/configuração verifica falhas persistentes. A temperatura usa comparação do byte alto antes/depois porque seus registradores não são duplamente bufferizados; após três tentativas incoerentes, retorna −1. O CSV converte esse indicador em temperatura ausente na análise.

O timestamp marca atendimento de DRDY, com latência, e não uma referência absoluta calibrada. O sensor também possui atraso interno. Interrupções mascaradas podem ocultar eventos; os contadores representam perdas detectadas, não prova absoluta de ausência de perda. A interface SPI usada não tem CRC de amostra, portanto a verificação periódica não detecta toda corrupção possível.

### Fila e serial

Há uma fila circular de 512 amostras **na RAM do ESP32-S3**. Ela não é o FIFO do ADXL355. O firmware lê diretamente os registradores mais recentes; não drena o FIFO de hardware nem interpreta seu overflow como perda deste caminho de aquisição.

A serial recebe apenas o volume que informa poder aceitar, reduzindo bloqueios. Fila cheia gera descarte contado. Cada linha `D` recebe CRC-16/CCITT-FALSE (início 0xFFFF, polinômio 0x1021), calculado sobre o texto anterior à vírgula do CRC. O checksum protege o transporte serial, não o SPI.

`STOP` termina a janela e esvazia a fila. Se a transmissão não concluir em cinco segundos, encerra com `timeout_transmissao`. Sem DRDY por 1,5 s, encerra com `sem_drdy`. Os totais de `#END` incluem perdas que podem ter ocorrido depois da última amostra transmitida.

## Captura e leitura

`01_capturar.py` abre a porta, espera o boot, pede `INFO`, verifica o protocolo e envia `START`. Guarda fragmentos até completar cada linha; um timeout não parte uma amostra em duas. Valida CRC, formato, limites e crescimento de tempo/índice. Linhas inválidas vão para o log; as válidas continuam salvas.

O bloco `finally` encerra a serial, calcula hash e escreve JSON mesmo em falha ou Ctrl+C. Captura completa exige término por duração, ausência de erros detectados e consistência entre totais enviados e recebidos. Isso é uma verificação de integridade, não aprovação metrológica. Os hashes dos fontes locais não comprovam o binário efetivamente gravado na placa.

`comum.py` exige CSV e JSON juntos, confere o formato e o hash do CSV, recusa valores não inteiros no bruto e centraliza unidades/saídas. `analises.py` implementa as análises; os arquivos numerados chamam suas rotinas. Cada execução possui uma pasta exclusiva e um manifesto com entradas, hashes, parâmetros e estado concluído/falhou/em execução.

## Conversão física

A combinação dos três bytes remove quatro bits inferiores de preenchimento e estende o sinal de 20 bits. O intervalo digital é −524288 a +524287. Em ±2 g, a conversão nominal é:

\[
a_g=r/256000,\qquad a_{m/s^2}=a_g\,9{,}80665.
\]

As sensibilidades nominais para ±4 e ±8 g são 128000 e 64000 LSB/g. Não substitua esses fatores por uma divisão arbitrária do tamanho total do código binário. A temperatura interna aproximada é:

\[
T=25+(r_T-1885)/(-9{,}05).
\]

O valor −1 indica falha de leitura e vira NaN; temperatura interna não equivale à temperatura ambiente calibrada.

## Funcional e calibração completa

A verificação funcional calcula média, desvio-padrão, RMS centralizado e norma amostra a amostra. A norma média não é exatamente a norma do vetor médio quando há ruído. A componente estática é mantida.

A matriz transforma o vetor bruto do sensor no vetor do conjunto:

\[
\mathbf a_n=\mathbf C(\mathbf r-\mathbf b).
\]

As linhas de C correspondem a Xn/Yn/Zn de saída e as colunas a X/Y/Z brutos. C tem unidade g/LSB; b tem unidade LSB. Nove elementos da matriz e três offsets totalizam 12 parâmetros. O modelo linear incorpora a relação fixa de orientação, ganho e mistura de canais; a matriz não separa suas causas físicas.

### Ajuste pelo modelo direto

`modelos_calibracao.py` concentra o cálculo. `calibracao_completa.py` lê as capturas e as referências, monta médias por arquivo e gera resultados. `03_calibrar_matriz_completa.py` e `03_calibrar_seis_posicoes.py` são entradas para a mesma rotina, com modelo completo por padrão.

As direções unitárias vêm do gabarito externo, no JSON de referências. Multiplica-se cada direção por g_local/9,80665 para expressar a referência em g padrão. Dividem-se os brutos pela escala nominal S_nom para evitar colunas com ordens de grandeza muito diferentes. O modelo direto é:

\[
\mathbf r/S_{nom}=\mathbf A\mathbf a_{ref}+\boldsymbol\beta.
\]

Para N arquivos, a matriz de projeto tem uma linha `[ax_ref, ay_ref, az_ref, 1]` por arquivo. `numpy.linalg.lstsq` estima os parâmetros, com peso igual por média de arquivo, sem usar o número de amostras como peso. Como cada arquivo tem três médias, as seis poses com três repetições fornecem 54 valores escalares para 12 parâmetros.

O cálculo final é:

\[
\mathbf C=\mathbf A^{-1}/S_{nom},\qquad \mathbf b=\boldsymbol\beta S_{nom}.
\]

A matriz de projeto precisa ter posto 4. O programa verifica condicionamento, determinante positivo e valores singulares relativos de A entre 0,5 e 1,5. Esses limites amplos são proteções contra erros grosseiros de orientação/escala, não especificações de aceitação do ADXL355. Um referencial refletido ou uma matriz singular são recusados.

`comum.converter` aplica a mesma transformação vetorial a todas as amostras: `(brutos - b) @ C.T`. A transposição decorre de armazenar uma amostra por linha. Não se aplica novamente a calibração diagonal. As colunas brutas permanecem intactas; ax_g/ay_g/az_g passam a representar Xn/Yn/Zn. A conversão em m/s² multiplica por 9,80665. `analise.json` registra o referencial e o hash do JSON da calibração.

### Validação e diagnóstico

`11_validar_calibracao.py` recusa hashes de CSVs usados no ajuste, exige a mesma montagem/configuração e aplica a matriz sem reajustar os coeficientes. Os erros são calculados sobre a média vetorial de cada novo arquivo:

\[
e_v=\|\bar{\mathbf a}_n-\mathbf a_{ref}\|,\quad
 e_m=100\left(\frac{\|\bar{\mathbf a}_n\|}{\|\mathbf a_{ref}\|}-1\right),\quad
 e_\theta=\arccos\left(\frac{\bar{\mathbf a}_n\cdot\mathbf a_{ref}}{\|\bar{\mathbf a}_n\|\|\mathbf a_{ref}\|}\right).
\]

O erro vetorial e os erros por componente são exportados em mg; o angular, em graus. Vetor nulo não tem direção definida e falha na avaliação das metas. Uma rotação errada pode manter norma 1 g; por isso o programa verifica direção e componentes.

Os centros dos pares opostos devem aproximar o mesmo bias quando as referências são antipodais e o modelo é constante. `consistencia_pares_opostos.xlsx` quantifica o desvio em relação ao bias do ajuste; esse diagnóstico também contém erros do gabarito e deriva.

Metas de triagem são configuráveis: 10 mg de erro vetorial, 1% no módulo e 0,5° na direção por padrão. O ajuste permanece `ajustada_nao_validada`; a validação produz seu próprio relatório ligado pelo hash, sem alterar a calibração. O programa não estima incerteza, exatidão do gabarito, resposta dinâmica ou compensação térmica.

### Método diagonal legado

`--modelo diagonal` conserva o ajuste independente por eixo: b=(r_+ + r_-)/2 e S=(r_+ - r_-)/(2 g_ref). Os JSONs diagonais antigos continuam sendo aplicados por `--calibracao`, nos canais do sensor. Eles não determinam a rotação sensor/base.

### Captura e compatibilidade

`01_capturar.py` adiciona montagem e referencial da etiqueta ao JSON. O protocolo serial e o firmware permanecem iguais. A aplicação de matriz exige mesmo exemplar, montagem, faixa, taxa e filtros. Para brutos antigos sem montagem, `--confirmar-montagem` registra a declaração explícita do usuário; uma montagem diferente já registrada continua sendo recusada.

`12_exportar_corrigido.py` salva um novo CSV com brutos, g, m/s², temperatura, tempo relativo e norma, acompanhado do contexto da transformação. Não altera a captura original nem gera XLSX de milhões de amostras.

## Ruído, PSD e ASD

Welch usa janela Hann, sobreposição de 50%, retirada da média por segmento e normalização `density`, em espectro unilateral. O padrão é 8192 pontos ou o comprimento disponível, se menor. A 500 Hz, o espaçamento é cerca de 0,061 Hz, o que não equivale à incerteza da frequência estimada.

PSD \(P(f)\) é expressa em g²/Hz. A raiz fornece ASD em g/√Hz; multiplicar por um milhão converte para µg/√Hz. Para uma banda explícita:

\[
a_{RMS}=\sqrt{\int_{f_1}^{f_2}P(f)\,df},\qquad
n_{eq}=\sqrt{\frac{\int_{f_1}^{f_2}P(f)\,df}{f_2-f_1}}.
\]

A integração é trapezoidal, interpolando apenas os limites de frequência. Não há interpolação de amostras temporais perdidas. Para ruído branco, a densidade equivalente estima seu nível; com picos, é apenas uma média energética da banda. O ambiente e a montagem fazem parte do resultado observado.

## Temporização e repetibilidade

A taxa efetiva é \((N-1)/(t_N-t_1)\). O programa examina intervalos, dispersão, extremos, saltos e contadores. Os analisadores espectrais recusam capturas parciais ou com lacunas; jitter/taxa fora da meta exploratória de 1% gera aviso e exige avaliação antes de interpretar os resultados. Uma taxa média não torna uma amostragem irregular automaticamente adequada para Welch.

A repetibilidade compara médias e RMS centralizado de arquivos com mesma posição, exemplar, faixa, taxa e filtro. O CV só é calculado para RMS positivo; não para médias próximas de zero. Diferenças após remontagem podem ser orientação ou tensão mecânica, além de eletrônica.

## Deriva térmica

O sinal é dividido em janelas, preservando a componente contínua. Calculam-se médias, dispersões, temperatura e deriva relativa à primeira janela. Uma regressão exploratória é permitida com ao menos três janelas válidas e amplitude térmica de 0,2 °C; esse limiar é uma proteção numérica, não garantia de boa calibração térmica. Tempo e temperatura podem estar confundidos. Não há compensação automática.

## Ensaio dinâmico

Um Butterworth passa-banda em seções de segunda ordem é aplicado nos dois sentidos com `sosfiltfilt`. A fase líquida ideal é zero, mas a resposta em amplitude é o quadrado da resposta de uma passagem: a atenuação nas bordas da banda é maior que a de uma passagem só. O programa não corrige o ganho do filtro interno do ADXL355.

São retirados dois segundos de cada extremidade para reduzir transientes nas métricas; outra banda/ordem pode exigir mais. O CSV filtrado conserva todos os pontos e marca `usado_metricas`. Exige-se ao menos quatro ciclos da frequência inferior após as bordas. O eixo automático maximiza RMS; a frequência dominante é o bin de maior PSD na banda, sem ajuste sub-bin.

Um pico não é automaticamente um modo estrutural isolado: excitação, modos próximos, rotação, fixação e fios influenciam o resultado. O RMS da vibração livre depende da janela e do tempo em repouso dentro dela.

## Allan sobreposto

Para médias \(\bar a_i^{(m)}\) de blocos de \(m\) amostras, \(\tau=m/f_s\):

\[
\sigma_A(\tau)=\sqrt{\frac{1}{2(N-2m+1)}\sum_{i=0}^{N-2m}(\bar a_{i+m}^{(m)}-\bar a_i^{(m)})^2}.
\]

Uma soma cumulativa torna o cálculo eficiente. Retirar apenas uma constante melhora a precisão numérica sem mudar Allan; não se retira tendência linear nem se aplica passa-altas. Isso preserva a deriva lenta.

Limita-se \(m\le N/10\), sem presumir que isso assegure baixa incerteza. Pares sobrepostos são correlacionados. O número de blocos não sobrepostos também é fornecido, mas não representa automaticamente graus de liberdade equivalentes. Não se calculam intervalos de confiança.

Inclinação próxima de −1/2 pode ser compatível com ruído branco; regiões planas/crescentes precisam ser interpretadas junto da temperatura e da estabilidade mecânica. O mínimo é descritivo: não se aplica automaticamente um fator para chamá-lo de instabilidade de bias. Consulte El-Sheimy, Hou e Niu nas referências.
