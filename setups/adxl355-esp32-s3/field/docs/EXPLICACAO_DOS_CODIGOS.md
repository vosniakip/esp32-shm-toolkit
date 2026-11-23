# Funcionamento dos códigos

## Firmware e transporte

`config.h` reúne GPIOs, frequências SPI, SSID, senha, limites de duração, fila e configuração das marcas. Os números refletem a pinagem lógica do pacote v3, a ser conferida contra a PCB. A entrada opcional de sincronismo não ocupa os GPIO19/20 do USB nativo.

`node.cpp` mantém duas tarefas: aquisição e armazenamento. A primeira recebe os eventos DRDY, associa os tempos ao FIFO e envia registros à fila sem esperar o cartão. A segunda reúne blocos e grava o microSD, com contagem de registros e CRC32. FIFO cheio, sequência inconsistente, lacuna detectada, falha no cartão ou falta de espaço impedem que o registro seja anunciado como uma campanha completa normal.

Os dados são assinados de 20 bits para X/Y/Z. A temperatura é lida nominalmente a 1 Hz e mantida entre atualizações. O registro bruto também contém índice, tempo e flags. O tempo é relativo ao início útil, depois do assentamento inicial; ele não é o tempo de chegada dos pacotes Wi-Fi ao computador.

O finalizador fecha o binário, grava os metadados e o log e calcula SHA-256. `cliente_wifi.py` permite download com retomada, verifica os hashes, converte o arquivo e confirma o recebimento. Nenhuma confirmação apaga a cópia local.

`web_ui.h` contém a página servida pelo próprio ESP32. Ela não carrega bibliotecas de internet. Os botões de perfil preenchem o formulário; não iniciam automaticamente a aquisição. O botão de marca registra uma observação com latência de rede, sem prometer precisão temporal.

A versão 4 adiciona as marcas em um buffer de eventos protegido por exclusão mútua. A ISR externa guarda apenas tempo e tipo. O cartão é acessado depois, pela tarefa de armazenamento. Assim uma latência de gravação não entra diretamente na interrupção do pulso.

## Controle e importação

`17_controlar_campanha.py` oferece ações de controle. Iniciar sem `--acompanhar` permite operar a DAQ em paralelo; com essa opção, usa o fluxo de espera e download verificado. Uma falha do START não provoca uma segunda tentativa automática de iniciar a aquisição.

`18_importar_referencia.py` utiliza um mapa JSON explícito. O script converte unidades, aplica o sinal declarado e normaliza a origem de tempo. Não adivinha nomes de colunas, sensibilidade ou separador decimal. A exportação original é preservada e seu hash acompanha o arquivo canônico.

`19_ajustar_tempo.py` estima a relação afim entre os relógios. O deslocamento inicial a e a escala b têm funções diferentes. Um só evento não permite estimar deriva; dois eventos não deixam resíduos para examinar a consistência. O mínimo de três foi escolhido para permitir essa inspeção, mantendo a recomendação de mais marcas distribuídas no tempo. O arquivo de ajuste é vinculado aos hashes do par de CSVs.

`25_extrair_marcas.py` lê o log do firmware e separa as marcas. Ele não cria correspondências com a DAQ automaticamente. Essa decisão evita alinhar sequências com pulsos ausentes ou identificações equivocadas sem deixar evidência.

## Núcleo numérico

`campo.py` organiza os sinais em Trace: tempo, canais SI, metadados e diagnóstico. Os registros do nó reutilizam a leitura protegida e a calibração do pacote anterior. Séries com índices/tempos inválidos, perdas reconhecidas ou saturação próxima do limite são recusadas nos novos ensaios. As referências também são verificadas quanto a tempo monotônico, valores finitos, hash e limites declarados.

A comparação temporal aplica o mapeamento de relógio, filtra a banda nos registros completos e recorta a janela com margem. A redução de taxa utiliza `resample_poly`, com FIR antialias. A passagem final para a grade comum utiliza uma interpolação sinc/Kaiser de 49 pontos. Essa etapa é importante porque uma interpolação linear na grade final poderia reduzir a amplitude em frequências altas da banda.

`metodos_campo.py` implementa os três procedimentos principais. No shaker, a frequência é inicializada pelo espectro e refinada minimizando o resíduo de um modelo senoidal com constante e tendência. Amplitudes das cadeias são ajustadas independentemente; a origem de fase não é comparada.

Na treliça, as janelas declaradas do mesmo impacto são analisadas na mesma banda. Sem alinhamento, a saída limita-se à resposta espectral e RMS. Com marcas válidas, surgem NRMSE e correlação em uma grade comum. O código não reajusta ganho nem desloca o sinal por correlação para tornar o resultado mais favorável.

Na passarela, cada canal recebe Welch e os canais simultâneos formam uma matriz espectral. Como SciPy usa conj(X)·Y na CSD, o código conjuga a entrada correspondente para manter a convenção Sij = Xi·conj(Xj). A decomposição Hermitiana é ordenada do maior para o menor autovalor. Os testes incluem uma relação complexa conhecida para conferir essa convenção.

A detecção de picos ocorre em escala logarítmica com proeminência declarada. Em seguida, o código procura o pico nos blocos temporais, dentro de uma tolerância relacionada ao espaçamento espectral e à frequência. Persistência é um mecanismo de triagem, não uma prova de origem modal.

## Consolidação e impacto instrumentado

`23_consolidar_frequencias.py` cruza resultados da passarela e evita contar reprocessamentos do mesmo CSV como novas aquisições. Canais e FDD de um mesmo registro não aumentam artificialmente o número de repetições. As agrupações são submetidas à revisão humana, sobretudo para modos próximos e harmônicos.

`24_resumir_shaker.py` reúne frequência comandada e nível, calcula média e desvio-padrão entre aquisições e mantém os valores individuais. Não estabelece uma incerteza expandida nem uma aprovação normativa.

`frf_impacto.py` e `26_analisar_frf_martelo.py` exigem força medida. A H1 é formada pelas médias de espectros cruzados e autoespectros de impactos distintos. O código rejeita janelas sobrepostas e exige pelo menos três impactos utilizáveis. A triagem examina força acima do ruído e possível duplo impacto, mantendo os motivos informados pelo operador. A validade da janela retangular depende de a resposta ter decaído dentro dela.

A FRF do nó só é calculada com arquivo de alinhamento associado ao par real de dados. Nesta versão, compara-se o módulo da FRF; os atrasos dos filtros e da cadeia não são calibrados para declarar exatidão de fase.

## Rastreabilidade

Cada análise recebe uma pasta nova. O JSON informa parâmetros e hashes; tabelas são CSVs em unidades declaradas e figuras são PNG/SVG. Coeficientes reais não são embutidos no código nem nos exemplos. Os dados sintéticos têm identificação própria e não devem entrar nas tabelas de resultados experimentais do TCC.

A entrada de dados profissional é deliberadamente genérica porque o modelo da DAQ ainda não foi informado. O mapa de importação precisa ser conferido com um arquivo exportado real antes da campanha definitiva.
