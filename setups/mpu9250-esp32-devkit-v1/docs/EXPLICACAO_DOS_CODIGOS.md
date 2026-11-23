# Explicação aprofundada dos códigos

## 1. Filosofia do sistema

Existe apenas um firmware no ESP32. Isso é importante porque usar um programa
diferente em cada ensaio poderia alterar taxa de amostragem, filtro, escala,
formato ou temporização. Os ensaios são distinguidos pelos metadados e pelos
programas de processamento no computador.

O ESP32 envia números inteiros brutos. A conversão para `g` e `m/s²` acontece
no computador. Essa separação permite recalcular os resultados se a calibração
for atualizada.

## 2. Firmware `gy9250_aquisicao.ino`

### 2.1 Bibliotecas

- `Arduino.h`: funções básicas do ambiente Arduino;
- `Wire.h`: comunicação I²C;
- `esp_timer.h`: relógio interno de alta resolução do ESP32.

Nenhuma biblioteca externa de IMU é necessária. Os registradores são
configurados diretamente, tornando explícitas faixa, filtro e taxa.

### 2.2 Configuração dos registradores

O código:

1. localiza o sensor em `0x68` ou `0x69`;
2. reinicializa o MPU-9250;
3. seleciona o clock PLL;
4. ativa os eixos;
5. configura ±2 g;
6. configura o filtro interno próximo de 92 Hz;
7. usa divisor 3 sobre a base de 1 kHz, produzindo 250 Hz;
8. habilita `Data Ready`.

Na faixa ±2 g, o valor nominal é 16.384 contagens por `g`. O ESP32 não aplica
esse valor aos dados: ele grava as contagens originais.

### 2.3 Interrupção `Data Ready`

O MPU-9250 gera um pulso no pino `INT` quando uma amostra nova está disponível.
A função de interrupção não lê I²C nem escreve na Serial. Ela apenas incrementa
`eventosPendentes`, porque operações demoradas dentro da interrupção poderiam
travar o microcontrolador.

O laço principal retira o contador e lê 14 bytes em uma única transação:

- seis bytes do acelerômetro;
- dois bytes da temperatura;
- seis bytes do giroscópio, lidos no bloco mas não gravados neste projeto.

Se ocorreram várias interrupções antes de uma leitura, somente a amostra mais
recente ainda está nos registradores. O código registra as anteriores como
perdidas.

### 2.4 Timestamp

`esp_timer_get_time()` fornece o tempo em microssegundos. O valor salvo é
relativo ao início da aquisição. Esse timestamp é melhor que o horário de
chegada no PC, porque USB, driver e sistema operacional adicionam atrasos.

### 2.5 Protocolo serial

Linhas iniciadas por `#` são mensagens de controle ou diagnóstico. Linhas
iniciadas por `D` são amostras. O formato é:

```text
D,indice,t_us,ax_raw,ay_raw,az_raw,temp_raw,perdidas_acum,erros_i2c
```

O computador envia `START,duracao_em_ms`. Para 120 s, envia `START,120000`.

## 3. `00_listar_portas.py`

Usa `serial.tools.list_ports` para mostrar as portas reconhecidas. Ele não
modifica nem abre o ESP32. Serve para descobrir `COM5`, `COM6` etc.

## 4. `01_capturar.py`

É o único programa que conversa diretamente com o ESP32.

### 4.1 Abertura da porta

Ao abrir a porta, muitas placas reiniciam. O código espera 2,5 s, limpa dados
antigos, solicita `INFO` e somente então envia `START`.

### 4.2 Escrita contínua

Cada linha válida é escrita diretamente no CSV. O programa não espera o final
para guardar tudo na memória. Isso reduz o risco de perder um ensaio longo em
caso de falta de memória.

### 4.3 Três arquivos

- CSV: somente a tabela de dados;
- JSON: descrição do ensaio e do computador;
- LOG: mensagens `#INFO`, `#START`, `#END` e linhas inválidas.

O JSON guarda ainda um SHA-256 do firmware presente no pacote. Esse código
identifica exatamente a versão do arquivo-fonte utilizada como referência.

## 5. `02_verificar_funcional.py`

Converte os dados pela calibração informada ou, na ausência dela, por 16.384
LSB/g. Calcula:

- média de cada eixo;
- desvio-padrão;
- módulo do vetor médio;
- eixo dominante;
- quantidade de valores distintos;
- saturação.

A faixa prática de 0,8 a 1,2 g é apenas uma verificação grosseira para detectar
erros grandes. Não é critério normativo de aprovação.

## 6. `03_calibrar_seis_posicoes.py`

O programa procura `Xpos`, `Xneg`, `Ypos`, `Yneg`, `Zpos` e `Zneg` nos JSONs
laterais ou nomes de arquivos. Ele agrupa automaticamente as repetições.

Para cada eixo:

```text
offset = (media_positiva + media_negativa) / 2
sensibilidade = (media_positiva - media_negativa) / 2
aceleracao_corrigida = (valor_bruto - offset) / sensibilidade
```

O JSON de calibração é lido pelos outros scripts. O modelo é diagonal: corrige
offset e escala individualmente, mas não calcula a matriz completa de
desalinhamento entre eixos.

## 7. `04_analisar_ruido_psd.py`

O ruído temporal é calculado após retirar a média:

```text
ruido = sinal - media(sinal)
RMS = raiz(media(ruido²))
```

Isso evita que a gravidade seja confundida com ruído.

A PSD usa `scipy.signal.welch` com:

- janela Hann;
- 4.096 amostras por segmento;
- 50% de sobreposição;
- retirada da média de cada segmento;
- frequência efetiva calculada do arquivo.

O RMS da banda é a raiz da integral da PSD entre 0,5 e 50 Hz. O script salva
PSD em `g²/Hz` e ASD em `g/raiz(Hz)`.

## 8. `05_analisar_temporizacao.py`

Calcula diferenças sucessivas dos timestamps e índices. Detecta:

- taxa efetiva;
- erro em relação a 250 Hz;
- média, desvio e percentis de `Delta t`;
- lacunas acima de 1,5 vezes o intervalo nominal;
- índices ausentes, repetidos ou fora de ordem;
- timestamps não crescentes;
- perdas reportadas pelo firmware.

Os limites de ±1%, 1%, `1,5 Delta t` e 0,1% são critérios internos do projeto,
não valores universais de uma norma.

## 9. `06_analisar_repetibilidade.py`

Compara as cinco aquisições usando:

- média de cada eixo;
- RMS do ruído;
- RMS por PSD na banda;
- frequência efetiva;
- média, desvio-padrão e coeficiente de variação entre repetições.

Quando a média é próxima de zero, o CV não é adequado e aparece vazio/NaN.
Nessa situação, use o desvio absoluto.

## 10. `07_analisar_deriva_termica.py`

Divide o arquivo longo em janelas de 60 s. Para cada janela calcula média,
desvio e temperatura interna. A referência é a média das últimas dez janelas.

Também ajusta regressão linear de aceleração média em função da temperatura e
apresenta mg/°C e R². Isso mostra associação, mas não separa perfeitamente tempo
e temperatura, porque ambos variam durante o aquecimento.

A conversão usada pelo datasheet é:

```text
temperatura_C = temp_raw / 333,87 + 21
```

Ela representa a temperatura interna aproximada do chip, não uma temperatura
ambiente metrologicamente calibrada.

## 11. `08_analisar_dinamico.py`

Aplica Butterworth passa-banda de quarta ordem entre 0,5 e 50 Hz por
`sosfiltfilt`. A filtragem é de fase zero porque o sinal é processado para
frente e para trás. Isso é adequado para análise posterior, mas não pode ser
usado em uma aplicação em tempo real sem atraso.

O eixo automático é aquele com maior RMS filtrado. O programa calcula:

- frequência dominante pela maior PSD na banda;
- RMS filtrado;
- pico absoluto;
- saturação;
- CV de frequência e amplitude entre repetições;
- erro de frequência, se uma referência for informada.

Cada execução cria uma subpasta exclusiva em `dados/processados/dinamico`, com
data, hora e identificação do primeiro CSV no nome. Além das tabelas e figuras,
o arquivo `analise.json` registra entradas, calibração, filtro e demais
parâmetros, preservando a rastreabilidade e impedindo sobrescritas.

## 12. `09_desvio_allan.py`

Para cada tempo de integração `tau`, o código forma médias móveis de `m`
amostras. Depois compara médias separadas por `m` amostras:

```text
variancia_Allan = 0,5 * media[(media[k+m] - media[k])²]
```

O desvio de Allan é a raiz dessa variância. Não se aplica passa-altas, pois ele
apagaria componentes lentas que o ensaio pretende caracterizar.

## 13. `10_gerar_resumo.py`

Percorre os CSVs processados e gera um índice Markdown. Ele não substitui os
arquivos de resultado e não altera nenhum dado.

## 14. `comum.py`

Centraliza operações que precisam ser iguais em todas as análises:

- leitura e validação do CSV;
- carregamento da calibração;
- conversão para `g` e `m/s²`;
- cálculo da taxa efetiva;
- descarte controlado do início;
- integração da PSD;
- gravação segura de JSON.

Centralizar essas operações evita que cada script use uma fórmula diferente.
