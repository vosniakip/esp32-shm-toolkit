# Referências e alcance metodológico

As fontes fundamentam componentes, conceitos e algoritmos. Durações, repetições, bandas e metas de triagem são escolhas deste protocolo de bancada, não exigências textuais dessas fontes.

| Ensaio/recurso | Apoio | Alcance |
|---|---|---|
| Funcional e identificação | Datasheet ADXL355; Fisher AN-1057 | Programação, gravidade e orientação |
| Calibração completa / validação estática | Pedley AN4399 | Modelo linear de 12 parâmetros, referências conhecidas e mínimos quadrados |
| Método diagonal legado | Fisher AN-1057 | Dois pontos por eixo para offset e sensibilidade |
| Rigidez e estabilidade da montagem | Perrault e Sadeghi (2020) | Influência de soldagem, tensões, temperatura e apoio no ADXL355 |
| Ruído, PSD e ASD | Welch (1967); SciPy | Estimação espectral e normalização |
| Temporização | Espressif ESP Timer; SciPy | Timestamp da placa e taxa usada no espectro; ensaio de jitter é verificação do projeto |
| Repetibilidade | JCGM 200:2012 | Definições de precisão e condições de repetibilidade |
| Aquecimento | Datasheet ADXL355 | Dependência térmica dos parâmetros; acompanhamento temporal adaptado ao projeto |
| Barra em vibração livre | Welch (1967), quanto ao espectro | Observação exploratória própria; não calibração normativa |
| Allan | El-Sheimy, Hou e Niu (2008) | Caracterização estocástica de sensores inerciais |
| Futura comparação dinâmica | ISO 16063-21 | Calibração por referência, não implementada integralmente aqui |

1. **ANALOG DEVICES.** *ADXL354/ADXL355: Low Noise, Low Drift, Low Power, 3-Axis MEMS Accelerometers*. Data sheet, Rev. D, 2025. [Documento oficial](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl354_adxl355.pdf). Referência de SPI, registradores, escala, filtro e temperatura. ADXL354 é analógico; este pacote usa ADXL355 digital.

2. **FISHER, Christopher J.** *AN-1057: Using an Accelerometer for Inclination Sensing*. Analog Devices. [Nota de aplicação](https://www.analog.com/en/resources/app-notes/an-1057.html). A seção Basic Calibration Techniques apresenta +1 g e −1 g por eixo. É uma nota técnica de fabricante, não artigo revisado por pares.

3. **WELCH, Peter D.** The use of the fast Fourier transform for the estimation of power spectra: a method based on time averaging over short, modified periodograms. *IEEE Transactions on Audio and Electroacoustics*, v. 15, n. 2, p. 70–73, 1967. [DOI 10.1109/TAU.1967.1161901](https://doi.org/10.1109/TAU.1967.1161901).

4. **EL-SHEIMY, Naser; HOU, Haiying; NIU, Xiaoji.** Analysis and modeling of inertial sensors using Allan variance. *IEEE Transactions on Instrumentation and Measurement*, v. 57, n. 1, p. 140–149, 2008. [DOI 10.1109/TIM.2007.908635](https://doi.org/10.1109/TIM.2007.908635). Allan caracteriza a estabilidade/ruído do sensor; não verifica a resposta dinâmica da estrutura.

5. **JCGM.** *International vocabulary of metrology — Basic and general concepts and associated terms (VIM)*. 3. ed. JCGM 200:2012. [BIPM](https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf). Base para distinguir ajuste, calibração, repetibilidade, precisão e exatidão.

6. **ISO.** *ISO 16063-21:2003 — Methods for the calibration of vibration and shock transducers — Part 21: Vibration calibration by comparison to a reference transducer*. [Página oficial](https://www.iso.org/standard/27053.html). Para realizar essa etapa, consulte integralmente a norma e alterações aplicáveis; o pacote não fornece declaração de conformidade ou certificado.

7. **SCIPY.** *scipy.signal.welch*. [Documentação](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html). Janela, sobreposição, espectro unilateral e density.

8. **ESPRESSIF SYSTEMS.** *ESP Timer (High Resolution Timer)*. [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/system/esp_timer.html). Referência de esp_timer_get_time(); não é sincronização de múltiplos nós.

9. **ESPRESSIF SYSTEMS.** *ESP32-S3-DevKitC-1 v1.0 User Guide*. [Pinagem](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.0.html). Confira a variante física da sua placa.

10. **ESPRESSIF SYSTEMS.** *USB CDC and DFU Flashing*. [Arduino ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/cdc_dfu_flash.html).

Fontes do pacote anterior preservadas; consulte VALIDACAO.md para o alcance da verificacao nesta versao.

## Referências acrescentadas na versão 2.0.0

11. **PEDLEY, Mark.** *High-Precision Calibration of a Three-Axis Accelerometer*. Freescale Semiconductor, 2015. Application Note AN4399, Rev. 2.0, out. 2015. [PDF oficial hospedado pela NXP](https://www.nxp.com/docs/en/application-note/AN4399.pdf). A seção 7 apresenta a matriz completa e offsets para relacionar leituras às referências conhecidas da placa. Fundamenta o modelo deste pacote; durações, repetições e metas de triagem são decisões do projeto. É uma nota de aplicação de fabricante.

12. **PERRAULT, Paul; SADEGHI, Mahdi.** *Managing Stress and Strain to Get the Best Performance in High Precision Tilt/Angle Sensing*. Analog Devices, 1 out. 2020. [Artigo técnico oficial](https://www.analog.com/en/resources/technical-articles/2020/10/26/11/24/managing-stress-and-strain-to-get-the-best-perf-in-hi-prec-tilt-angle-sensing.html). Discute especificamente a influência de tensões mecânicas, gradientes térmicos, apoio e soldagem no ADXL355. Os valores de datasheet citados no artigo histórico devem ser distinguidos dos valores da revisão D atual.

Consulta das fontes acrescentadas e do datasheet: 5 out. 2026. O modelo de 12 parâmetros é estático e linear; não substitui comparação dinâmica rastreável nem demonstra exatidão do gabarito. A proposta de validação independente e as metas de 10 mg, 1% e 0,5° são o protocolo adotado para este projeto, sem atribuí-las à AN4399 como exigências normativas.


## Fontes de armazenamento e comunicacao acrescentadas na v3

13. **KOENE, Ivar; KLAR, Ville; VIITALA, Raine.** IoT connected device for vibration analysis and measurement. HardwareX, v. 7, e00109, 2020. DOI: https://doi.org/10.1016/j.ohx.2020.e00109. Texto aberto institucional: https://acris.aalto.fi/ws/portalfiles/portal/42677035/ENG_Koene_et_al_IoT_connected_device_HardwareX.pdf. Fundamenta ADXL355/ESP32, buffer circular, tarefas e armazenamento em cartao; validacao do artigo envolve maquinas/atuador, nao uma passarela.

14. **BONO, Francesco Morgan et al.** Wireless Accelerometer Architecture for Bridge SHM: From Sensor Design to System Deployment. Future Internet, v. 17, n. 1, 29, 2025. DOI: https://doi.org/10.3390/fi17010029. Fonte tambem consultada na pasta Fontes TCC do Drive. Apoia fases de aquisicao e transmissao, ADXL355/ESP32-S3, gateway e MQTT; o armazenamento descrito no no e na memoria do ESP32. A v3 aqui usa microSD e HTTP local, uma adaptacao de engenharia.

15. **HASANI, Hamed; FREDDI, Francesco; PIAZZA, Riccardo; CERUFFI, Fabio.** A Wireless Data Acquisition System Based on MEMS Accelerometers for Operational Modal Analysis of Bridges. Sensors, v. 24, n. 7, 2121, 2024. DOI: https://doi.org/10.3390/s24072121. Fonte tambem no Drive. Fundamenta preservacao local de aceleracoes, timestamps e deteccao de erros; o hardware do artigo utiliza memoria flash e outro microcontrolador.

16. **PONCETTI, Bernardo Lopes; VEGA RUIZ, Dianelys; FUTAI, Marcos Massao.** A low-cost system for continuous dynamic monitoring and autonomous data analysis using the Internet of Things and Machine Learning. CILAMCE, 2024. DOI: https://doi.org/10.55592/cilamce.v6i06.10213. https://publicacoes.softaliza.com.br/cilamce/article/view/10213. Fonte tambem no Drive. Apoia ESP32, microSD e envio posterior dos dados em blocos. O trabalho reconhece a limitacao de sincronizacao entre nos; o gatilho por evento ali utilizado nao foi adotado como modo principal destes ensaios.

17. **WANG, Yinhao et al.** A Prototype of a Lightweight Structural Health Monitoring System Based on Edge Computing. Sensors, v. 25, n. 18, 5612, 2025. DOI: https://doi.org/10.3390/s25185612. Utiliza ADXL355/ESP32-S3, fila em PSRAM e transmissao MQTT. A PSRAM nao e requisito do firmware entregue, que usa fila em RAM interna.

18. **DRAGOS, Kosmas; THEILER, Michael; MAGALHAES, Filipe; MOUTINHO, Carlos; SMARSLY, Kay.** On-board data synchronization in wireless structural health monitoring systems based on phase locking. Structural Control and Health Monitoring, v. 25, e2248, 2018. DOI: https://doi.org/10.1002/stc.2248. Fonte tambem no Drive. Fundamenta a importancia do alinhamento de registros; seu algoritmo especifico nao foi implementado neste pacote de um no.

19. **ESPRESSIF SYSTEMS.** Arduino-ESP32 Wi-Fi API. https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html. Ponto de acesso e rede local.

20. **ESPRESSIF SYSTEMS.** SD SPI Host Driver; SD Pull-up Requirements. https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/sdspi_host.html e https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/sd_pullup_requirements.html. Interface eletrica e acesso ao cartao.

Os GPIOs, tamanho do buffer, limite de duracao, formato de blocos, SHA-256/ACK,
nomes de arquivos, tempos e repeticoes sao escolhas deste pacote. Nao foram
atribuidos a uma norma ou apresentados como reproducao integral de um artigo.
A implementacao requer validacao fisica. Consulta das fontes novas: 21 out. 2026.
