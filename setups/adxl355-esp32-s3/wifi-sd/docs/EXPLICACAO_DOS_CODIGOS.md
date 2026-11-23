# Funcionamento dos códigos

## 1. Firmware

`adxl355_wifi_sd.ino` e uma entrada pequena que chama nodeSetup/nodeLoop.
A implementacao fica em node.cpp, evitando que o pre-processador do Arduino
gere prototipos de funções antes da definição de tipos personalizados.

`config.h` centraliza pinos, clocks SPI, limites, senha e memória. `format.h`
define as estruturas binarias, CRC32, extensão do sinal de 20 bits e verificação
dos marcadores FIFO. `web_ui.h` contem HTML, CSS e JavaScript locais; o navegador
consulta STATUS e envia formulários, sem dependencias externas.

Na inicialização, o firmware verifica IDs, configura o sensor e tenta montar
o SD. As filas e tarefas são criadas antes de aceitar campanhas. Abertura de
USB não é uma condição de início. Preferences armazena o contador de boot e,
somente quando solicitado, uma configuração de partida futura.

### acquisitionTask

A tarefa de leitura tem prioridade superior ao loop da interface e usa o
barramento dedicado do ADXL355. O ISR de DRDY salva um par sequencia/timestamp
numa fila curta e notifica a tarefa; ele não acessa SPI nem o sistema de arquivos.

Antes da campanha, o sensor passa brevemente a standby, recebe a configuração,
tem o FIFO esvaziado e volta a medir. Os eventos e amostras do pre-roll de
100 ms são consumidos sem entrar no registro. A cada evento aceito, a tarefa
retira XYZ do FIFO e verifica marcador X, ordem dos eixos e indicador de vazio.

O pareamento inicia com FIFO e fila DRDY vazios. Uma perda/ambiguidade interrompe
a captura: não se atribuem timestamps ideais a dados cujo pareamento deixou
de ser confiável. A verificação de lacunas de DRDY e conservadora e não comprova
por si só exatidão do relógio. IDs/configuracao são novamente conferidos durante
o ensaio. SPI não possui CRC de cada leitura neste dispositivo; erros_spi conta
as falhas que essas verificações conseguem detectar, não todos os erros possíveis.

O RawRecord e enviado sem espera a uma fila de 2048 posições. Se ela ficar cheia,
a campanha e encerrada. O resultado passa a ser um prefixo identificado como
incompleto, em vez de uma serie supostamente continua com amostras fabricadas.

### storageTask

Essa tarefa recebe um plano com uma ou mais repetições. Para cada registro,
cria uma pasta exclusiva, escreve cabecalho e metadados iniciais, inicia a
aquisição e drena a fila em blocos de até 128 registros. Escritas são agrupadas;
flush ocorre periodicamente e ao finalizar. Cada payload recebe CRC32.

Depois que a tarefa de aquisição termina e a fila esvazia, storageTask escreve
o rodape, fecha o arquivo e renomeia raw.bin.part para raw.bin quando possível.
Atualiza os metadados, registra eventos e calcula hashes SHA-256. O estado
ocupado só e liberado ao concluir a sequência e a finalização. Uma sequência
de várias repetições e executada no próprio no; não depende de consultas do PC.

O buffer de 64 KiB oferece aproximadamente 4,1 s de margem a 500 Hz somente
para a fila RAM, se inicialmente vazia. O FIFO do sensor oferece uma margem
muito menor e pode ser o primeiro limite se a tarefa de leitura atrasar.
Esses números não garantem tolerancia a qualquer cartao ou carga de CPU.

### Controle, estado e comunicação

O loop atende WebServer e diagnóstico serial. Contadores compartilhados são
lidos com proteção; sinais entre tarefas usam atomicos. Listagens, downloads,
alteracao do relógio e da partida futura são bloqueados durante a sequência.
Nenhuma rotina HTTP e usada como relógio de amostragem.

No modo quiet, a tarefa solicita desligamento do radio e aguarda a confirmacao
do loop. O radio retorna depois de finalizar a sequência, inclusive quando
há falha. Nesse intervalo STOP remoto não funciona; existe a duração programada.

## 2. Captura e transporte no PC

`00_controlar_no.py` consulta INFO/STATUS, lista, solicita STOP e arma/desarma
a partida futura. Não inicia captura como efeito de uma consulta.

`01_capturar_wifi.py` e `01_capturar.py` chamam captura_wifi.main. Os parâmetros
de linha de comando são traduzidos para os campos HTTP. `cliente_wifi.py`
usa urllib da biblioteca padrão, sem proxy para a rede local.

Antes do START, o cliente cria comando.json e um request_id. Ele envia uma
unica requisicao de início. Se a resposta for incerta, preserva esse contexto
e pede consulta do estado; não cria automaticamente outra medição. Durante
a espera, queda de conexão e reconexão são toleradas dentro da margem.

Ao final, o cliente baixa primeiro o manifesto. Os downloads seguintes usam
os hashes esperados e um arquivo temporario .download.part. Uma resposta
interrompida pode ser retomada por offset. Só depois de tamanho/SHA-256 corretos
e conversão com CRC valido ele envia ACK. O cartao conserva sua cópia.

`13_baixar_dados.py` faz apenas recuperacao/download de registros existentes.
`14_converter_binario.py` importa conjuntos copiados pelo cartao ou navegador.
`16_executar_roteiro.py` conduz várias poses com confirmacao física do operador;
o sensor não é capaz de saber que a orientação atribuida ao nome foi realizada.

## 3. Conversão e rastreabilidade

`formato_sd.py` valida cabecalho, tipos, sequência de blocos, CRC, rodape, hashes,
contagens e identidade entre JSON e binário. A leitura e em blocos pequenos,
sem carregar todo o bruto em memória. O CSV e produzido em arquivo temporario
e recebe nome final depois das verificações. Saidas diferentes não sobrescrevem
arquivos existentes. Uma conversão identica pode reutilizar a saida ja verificada.

`comum.py` e a camada compartilhada pelos analisadores. Ela exige CSV/JSON
juntos, confirma hashes, inteiros, 20 bits, monotonicidade, unidades e contexto
da calibração. Pastas de análise usam data/hora com microssegundos e identificador
aleatorio. analise.json registra entradas, parâmetros, hashes e estado final.

## 4. Calibração

`modelos_calibracao.py` contem a algebra sem acesso a hardware. O modelo direto
e r/s_nominal = A a_ref + beta. Uma matriz de projeto com as tres componentes
de a_ref e uma coluna de uns estima A e beta por mínimos quadrados.
Depois C = inv(A)/s_nominal e b = beta s_nominal.

`calibracao_completa.py` transforma cada arquivo em uma media XYZ, verifica
identificação, montagem, referências, repetições e configuração. O ajuste
usa peso igual por arquivo, para que duração maior não represente artificialmente
outra repetição independente. Posto, condicionamento, determinante e ganhos
globais são verificados antes de aceitar a inversao.

`03_calibrar_matriz_completa.py` e a entrada principal. O nome legado
`03_calibrar_seis_posicoes.py` continua disponível e também usa matriz por
padrão. --modelo diagonal conserva o ajuste independente de cada eixo, que
não corrige o alinhamento entre os eixos do sensor e os da base.

`11_validar_calibracao.py` aplica os coeficientes a novos arquivos de orientação
conhecida. Calcula erro de norma, angular e vetorial e recusa hashes de arquivos
usados no ajuste. Novos arquivos não comprovam, sozinhos, exatidão do gabarito.
`12_exportar_corrigido.py` gera CSV processado com g e m/s2, sem alterar brutos.

O modelo C(r-b) pode combinar rotacao fixa, escala e acoplamento linear. Ele
não separa as causas fisicas nem corrige folga, histerese, deformacao variavel
da montagem ou resposta dinâmica dependente da frequência.

## 5. Funcional, tempo, repetibilidade e temperatura

`02_verificar_funcional.py` mostra medias por eixo, media das normas e módulo
do vetor medio. Esses dois últimos números são diferentes quando há movimento
ou ruído. A gravidade permanece no sinal.

`05_analisar_temporizacao.py` calcula fs = (N-1)/(t_ultimo-t_primeiro), intervalos,
DP, extremos, lacunas e contadores. Não interpola dados ausentes. A proporcao
DP(dt)/media(dt) e uma metrica exploratoria de jitter observado no ISR.

`06_analisar_repetibilidade.py` compara medias, suas amplitudes e RMS entre
arquivos. As repetições devem ter o mesmo exemplar, montagem, modo de radio,
posição, taxa, faixa e filtros. CV de medias proximas de zero não é usado.

`07_analisar_deriva_aquecimento.py` e `07_analisar_deriva_termica.py` chamam a
mesma rotina. Janelas temporais preservam a componente continua e exibem medias,
temperatura e deriva. A conversão nominal e T = 25 + (temp_raw - 1885)/(-9,05).
O coeficiente de regressao com temperatura e exploratorio e não é compensacao.

## 6. PSD, densidade e dinâmico

`04_analisar_ruido_psd.py` calcula periodogramas de segmentos Hann, com metade
de sobreposicao, retira a media de cada segmento e faz a media dos espectros.
A PSD e unilateral, em g2/Hz; ASD = raiz(PSD), em g/raiz(Hz).
RMS na banda = raiz(integral da PSD nessa banda).

A densidade equivalente e RMS_banda/raiz(largura_banda). Ela coincide com
uma densidade branca constante apenas sob as hipoteses adequadas. Picos
ambientais e inclinacoes do espectro precisam ser examinados, não apagados
sem criterio. O programa salva os valores espectrais para reprocessamento.

`08_analisar_dinamico.py` aplica Butterworth por sosfiltfilt, descarta bordas,
seleciona eixo por maior RMS filtrado quando auto, e estima o bin dominante
por Welch. A ida e volta modifica a resposta de magnitude e elimina a fase
do filtro de processamento; não é uma implementacao causal para o nó.

O CSV filtrado e apenas uma saida de análise. Calibração, temperatura e Allan
continuam utilizando os registros sem passa-altas. Proximidade do limite
digital e informada porque saturação não é reparada por filtragem.

## 7. Allan

`09_desvio_allan.py` usa medias adjacentes de m pontos. Para cada m, calcula
a raiz de metade da media dos quadrados das diferencas entre essas medias,
incluindo todas as posições sobrepostas disponíveis. tau = m/fs.

A soma cumulativa torna o calculo eficiente. Uma constante e subtraida antes
para reduzir erro numérico, sem retirar tendencia temporal. O máximo tau e
limitado a aproximadamente T/10. A tabela informa pares sobrepostos e blocos
não sobrepostos; nenhuma contagem e apresentada como número de observações
estatisticamente independentes. O mínimo da curva e somente descritivo.

## 8. Resumos e verificações de sistema

`10_gerar_resumo.py` indexa os analise.json das pastas escolhidas, com estado
e referências. Ele não aprova automaticamente os ensaios.

`15_validar_armazenamento_wifi.py` resume integridade e continuidade por modo
de radio. Comparacoes numericas usam os timestamps registrados; validação
de amplitude e sincronização externa requerem referências adicionais.

Os testes sintéticos verificam valores conhecidos, rejeição de corrupção,
recuperacao parcial, não sobrescrita e retomada HTTP. Eles não modelam as
latencias reais do SD, regulador, Wi-Fi, GPIO ou a mecânica da sua montagem.
