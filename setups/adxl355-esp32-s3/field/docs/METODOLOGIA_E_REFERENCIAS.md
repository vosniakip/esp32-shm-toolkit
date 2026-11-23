# Metodologia e apoio bibliográfico

Consulta inicial: 4 nov. 2026; atualização da campanha UFPR: 11 nov. 2026. Os parâmetros operacionais do pacote são propostas para este projeto; não são transcrições de protocolos normativos. Os documentos completos das fontes não foram redistribuídos no ZIP.

## Relação entre as decisões e as fontes

| Decisão ou ensaio | Apoio consultado | Aplicação e limite |
| --- | --- | --- |
| Comparar amplitudes e frequências sob seno estacionário no shaker | Crognale et al. (2024), seção 3.2; ISO 16063-21 | Fundamenta a comparação com uma cadeia de referência; não torna a campanha automaticamente uma calibração normativa |
| Avaliar a cadeia completa, não apenas valores de catálogo | Komarizadehasl et al. (2021); Komarizadehasl (2022), capítulos de desenvolvimento/validação | Integra ruído, aquisição e verificação experimental; não transfere o desempenho publicado para este exemplar |
| Verificar amostragem, posição e sincronização antes de comparar | Delgado Zhagui (2026), capítulos 4 e 5, em especial 5.2.5 | Relaciona comparação profissional e preparação dos dados; o alinhamento afim por marcas deste pacote é uma implementação própria |
| Impactos com força medida, controle de duplo impacto e média de eventos | Brüel & Kjær, BP 2601; documentação ARTeMIS de FRF | Dá suporte à qualidade do impacto e ao estimador H1; sem força registrada, a rotina produz apenas análise de resposta |
| PSD por média de segmentos | Welch (1967); documentação SciPy | Fundamenta o estimador e a normalização em densidade; duração e segmentação foram escolhidas para a campanha |
| PP como rotina inicial de frequências | Hasani e Freddi (2023), seção 4.2.1; aplicações experimentais de Crognale et al. (2024) | Adequado a uma leitura inicial com picos observáveis; picos próximos e excitação harmônica limitam a atribuição modal |
| FDD complementar em canais simultâneos | Brincker, Zhang e Andersen (2001); Delgado Zhagui (2026), 5.2.5.5 | Decompõe a matriz espectral. Os três canais de um ponto fornecem vetores locais, sem representar a deformada espacial da passarela |
| Repetição em posições e condições de excitação | Komarizadehasl (2022), capítulo 6; Delgado Zhagui (2026), capítulo 5 | Ajuda a examinar observabilidade e coerência da interpretação; campanhas sucessivas não preservam fase espacial |
| Rede própria, memória local e transferência posterior | Hasani et al. (2024); documentação Espressif de Wi-Fi/SPI/SD; arquitetura do firmware v3 | Implementa controle local sem roteador; não promete sincronismo de aquisição entre equipamentos |
| Contexto da passarela UFPR Botânico-Politécnico | Medeiros, Faggion e Alves (2020) | Estudo na mesma estrutura por ETR/GNSS; seus pontos e frequências não substituem medir a geometria e documentar esta campanha |
| Resposta sob pedestres e escolha da instrumentação | Heinemeyer et al. (2009) | Apoia o planejamento de medição e o reconhecimento da excitação humana; não determina os 20 min ou os dois pontos deste projeto |

A tese de Komarizadehasl (2022) e o trabalho de Delgado Zhagui (2026) foram consultados no Drive para a relação entre caracterização do sensor, validação experimental e aplicação estrutural. O artigo de Hasani e Freddi (2023) ajuda a comparar famílias de identificação. A formulação efetivamente implementada da FDD se apoia no artigo original de Brincker, Zhang e Andersen (2001).

## Por que não chamar todo pico de frequência natural

A PSD da resposta depende da estrutura e da excitação. Uma linha periódica pode corresponder a passos, motores, interferência ou outra força persistente. Por outro lado, um modo pode não aparecer se for pouco excitado ou se o sensor estiver próximo de um nó daquela forma modal. A atribuição física requer examinar repetições, posições e condições de excitação, além do espectro.

A presença de vários canais não equivale necessariamente a vários pontos espaciais. A FDD do pacote combina X, Y e Z simultâneos do ADXL355, já no referencial declarado. Seus vetores expressam relações locais entre direções. Para formas modais ao longo da passarela seria necessário ampliar a instrumentação espacial e o controle de sincronismo ou adotar um arranjo com referência fixa adequadamente validado.

SSI-COV e outras técnicas continuam sendo alternativas de evolução. A decisão por PP com persistência e FDD local não decorre de uma suposta impossibilidade de aplicar SSI com poucos canais. Decorre do alcance atual: estimar frequências de modo verificável e evitar uma automatização de polos e amortecimento sem validação específica.

## Equações implementadas

No shaker, cada janela é ajustada por a(t) = c0 + c1·t + B·sen(2πft) + C·cos(2πft). A frequência é procurada em torno da comandada; os coeficientes lineares são estimados por mínimos quadrados. A amplitude de pico é raiz(B²+C²), e a amplitude RMS da fundamental é esse valor dividido por raiz de 2.

O desvio relativo entre as cadeias é 100·(grandeza_no/grandeza_ref - 1). O denominador vem da medição profissional, não da configuração nominal do shaker. Não se estima uma incerteza expandida apenas a partir desse desvio.

A PSD de Welch usa janela Hann, sobreposição de 50%, média aritmética e remoção da média por segmento. O RMS em banda é a raiz da integral da PSD entre os limites declarados. O espaçamento entre linhas é fs/N; a largura equivalente de ruído da Hann é 1,5·fs/N. A grade não representa, sozinha, a incerteza do pico.

Na FDD, a matriz espectral S(f) é Hermitiana, com Sij = Xi·conj(Xj) no conjunto de médias. O programa usa sua decomposição em autovalores/autovetores, equivalente aos valores singulares/vetores de uma matriz espectral semidefinida positiva. A ordenação é decrescente. A fase global do vetor local é normalizada por seu maior componente.

No alinhamento, t_ref = a + b·t_no. O ajuste pondera os pares pelo inverso do quadrado do erro temporal declarado. A coerência dos resíduos é verificada, mas erros sistemáticos comuns às marcas e atrasos dos filtros não são eliminados pelo ajuste.

Com força medida, H1(f) = média[Y(f)·conj(F(f))]/média[|F(f)|²]. A coerência é |média[Y·conj(F)]|²/(média[|Y|²]·média[|F|²]). A média reúne impactos diferentes, não apenas um registro cujo estimador de coerência seria trivial. A suposição de ruído de saída não correlacionado com a força é relevante para H1; ruído substancial no canal de força limita esse estimador.

## Decisões próprias que devem ser relatadas como tais

Cinco impactos iniciais, três repetições por condição no shaker, dois pontos de meia extensão nos vãos A-B e B-C, com um registro por ponto, registros de vinte minutos, segmentos de 64 s, quatro blocos, 75% de persistência, 6 dB de proeminência, limite de jitter e triagens de força/coerência são escolhas operacionais deste pacote. Devem ser revistas no piloto e registradas antes da análise definitiva. A literatura dá fundamento ao procedimento; não fornece autorização para generalizar limiares de um sistema para todos os demais.

## Referências e acesso

1. BRINCKER, Rune; ZHANG, Lingmi; ANDERSEN, Palle. Modal identification of output-only systems using frequency domain decomposition. Smart Materials and Structures, v. 10, n. 3, p. 441-445, 2001. DOI: https://doi.org/10.1088/0964-1726/10/3/303. Registro institucional consultado: https://vbn.aau.dk/en/publications/modal-identification-of-output-only-systems-using-frequency-domai-2/.

2. WELCH, Peter D. The use of fast Fourier transform for the estimation of power spectra: a method based on time averaging over short, modified periodograms. IEEE Transactions on Audio and Electroacoustics, v. 15, n. 2, p. 70-73, 1967. DOI: https://doi.org/10.1109/TAU.1967.1161901. Registro do autor/instituição: https://research.ibm.com/publications/the-use-of-fast-fourier-transform-for-the-estimation-of-power-spectra-a-method-based-on-time-averaging-over-short-modified-periodograms.

3. CROGNALE, Marianna; RINALDI, Cecilia; POTENZA, Francesco; GATTULLI, Vincenzo; COLARIETI, Andrea; FRANCHI, Fabio. Developing and Testing High-Performance SHM Sensors Mounting Low-Noise MEMS Accelerometers. Sensors, v. 24, n. 8, art. 2435, 2024. DOI: https://doi.org/10.3390/s24082435. Texto primário: https://pmc.ncbi.nlm.nih.gov/articles/PMC11054890/. Também localizado na pasta Fontes TCC: https://drive.google.com/file/d/1ER7ZNsnfVdGz-aPt60w4oRGnmSTePr_D/view.

4. KOMARIZADEHASL, Seyedmilad; MOBARAKI, Behnam; MA, Haiying; LOZANO-GALANT, Jose-Antonio; TURMO, Jose. Development of a Low-Cost System for the Accurate Measurement of Structural Vibrations. Sensors, v. 21, n. 18, art. 6191, 2021. DOI: https://doi.org/10.3390/s21186191. Consultado no Drive: https://drive.google.com/file/d/1rse2mZM2cXfyD9xLQlXMUoig-JpVqMnm/view.

5. KOMARIZADEHASL, Seyedmilad. Development of Low-Cost Sensors for Structural Health Monitoring Applications. 2022. Tese (Doutorado em Engenharia da Construção) - Universitat Politècnica de Catalunya, Barcelona, 2022. Consultada no Drive: https://drive.google.com/file/d/1XVcXlQhVKyF4_yEk-Vczups0SVPQCOUa/view. Os ensaios de validação e a aplicação em ponte/passarela orientam a progressão da campanha; não se adotam os resultados quantitativos do autor como critérios de aprovação deste nó.

6. DELGADO ZHAGUI, Erika Beatriz. Validation of MEMS Accelerometers for Static and Dynamic Bridge Assessment Integrating Automated Synchronization and Modal Parameter Extraction. 2026. Tese (Doutorado em Engenharia da Construção) - Universitat Politècnica de Catalunya, Barcelona, 2026. Consultada no Drive: https://drive.google.com/file/d/15wCg2R4qCPIMpF5V6bVWmrXd-Cuqk1gy/view.

7. HASANI, Hamed; FREDDI, Francesco. Operational Modal Analysis on Bridges: A Comprehensive Review. Infrastructures, v. 8, n. 12, art. 172, 2023. DOI: https://doi.org/10.3390/infrastructures8120172. Consultado no Drive: https://drive.google.com/file/d/1kLLLuCBEUm4VMlb9JgQxoK4pJD_8AWEK/view. É uma revisão, utilizada para contextualizar a escolha de método.

8. ISO. ISO 16063-21:2003: Methods for the calibration of vibration and shock transducers - Part 21: Vibration calibration by comparison to a reference transducer. Geneva: International Organization for Standardization, 2003. Página oficial consultada, com indicação de emendas: https://www.iso.org/standard/27053.html. O texto integral pago da norma não foi utilizado para declarar conformidade.

9. BRÜEL & KJÆR. BK Connect Structural Dynamics / Hammer Impact Applet Type 8491-A-N-SYS. Product Data BP 2601-13. Documento técnico do fabricante. https://www.bksv.com/-/media/literature/Product-Data/bp2601.ashx. Apoia a revisão de força, duplo impacto, coerência e médias do ensaio.

10. STRUCTURAL VIBRATION SOLUTIONS. Frequency Response Function estimation. ARTeMIS Modal Help. Documentação técnica do desenvolvedor. https://www.svibs.com/resources/ARTeMIS_Modal_Help/Frequency%20Response%20Function%20estimation.html. Formulações dos estimadores H1, H2 e Hv.

11. ANALOG DEVICES. ADXL354/ADXL355: Low Noise, Low Drift, Low Power, 3-Axis MEMS Accelerometers. Data Sheet, Rev. D, 2025. https://www.analog.com/media/en/technical-documentation/data-sheets/adxl354_adxl355.pdf. Apoio aos registradores, FIFO, DRDY, escalas e modos do sensor.

12. ESPRESSIF SYSTEMS. Arduino-ESP32: Wi-Fi API; SPI API; SD library; USB CDC and DFU Flashing. Documentação oficial. https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html ; https://docs.espressif.com/projects/arduino-esp32/en/latest/api/spi.html ; https://github.com/espressif/arduino-esp32/tree/master/libraries/SD ; https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/cdc_dfu_flash.html. Base das APIs embarcadas; disponibilidade exata dos menus depende da placa/core.

13. SCIPY DEVELOPERS. scipy.signal.welch; scipy.signal.resample_poly. Documentação oficial. https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html ; https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html. Base de implementação computacional, não de validação física do nó.

14. MEDEIROS, Leandro Ítalo Barbosa de; FAGGION, Pedro Luís; ALVES, Samir de Souza Oliveira. Análise do Desempenho de ETR no Monitoramento Dinâmico de Estrutura Metálica por Leitura Contínua de Direções. Revista Brasileira de Cartografia, v. 72, n. 2, p. 280-293, 2020. DOI: https://doi.org/10.14393/rbcv72n2-52637. Fonte primária: https://seer.ufu.br/index.php/revistabrasileiracartografia/article/view/52637.

15. HASANI, Hamed; FREDDI, Francesco; PIAZZA, Riccardo; CERUFFI, Fabio. A Wireless Data Acquisition System Based on MEMS Accelerometers for Operational Modal Analysis of Bridges. Sensors, v. 24, n. 7, art. 2121, 2024. DOI: https://doi.org/10.3390/s24072121. Fonte primária: https://www.mdpi.com/1424-8220/24/7/2121. Emprega ADXL355, memória local, ESP32 para comunicação e um microcontrolador STM32 como controlador; não é o mesmo circuito deste pacote.

16. HEINEMEYER, Christoph et al. Design of Lightweight Footbridges for Human Induced Vibrations. Luxembourg: Office for Official Publications of the European Communities, 2009. EUR 23984 EN. DOI: https://doi.org/10.2788/33846. https://eurocodes.jrc.ec.europa.eu/publications/design-lightweight-footbridges-human-induced-vibrations.
