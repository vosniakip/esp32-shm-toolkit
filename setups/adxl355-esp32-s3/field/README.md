# ADXL355 + ESP32-S3: ensaios comparativos e campanha na passarela

Versão 4.1.0 · 11 de novembro de 2026

Este pacote reúne o que é necessário para comandar um nó triaxial ADXL355/ESP32-S3 em campo. O nó cria a própria rede Wi-Fi, grava os sinais em microSD e permite baixar os arquivos com verificação de integridade. Nos ensaios comparativos, o instrumento de referência continua ligado ao seu sistema de aquisição.

## Preparação

1. Consulte o [guia da campanha na passarela da UFPR](docs/GUIA_CAMPO_PASSARELA_UFPR.md) para os pontos e a sequência de campo. O [guia geral](docs/GUIA_COMPLETO.md) cobre a instalação e os demais ensaios.
2. Compare a pinagem de `firmware/adxl355_wifi_sd/config.h` com a placa e a fiação usadas. A configuração segue o pacote de bancada v3.
3. Com o Arduino-ESP32 3.x, grave `firmware/adxl355_wifi_sd/adxl355_wifi_sd.ino` pelo USB nativo. O guia explica as opções para o ESP32-S3 N16R8.
4. Instale as dependências no computador antes de entrar no Wi-Fi do nó. No perfil da campanha, registre o sensor, a montagem e o arquivo de calibração correspondente.
5. Conecte-se à rede `ADXL355-ENSAIOS`, com a senha inicial `Ensaio355!`, e abra `http://192.168.4.1`. O controle e a transferência funcionam sem internet.
6. Inicie a aquisição e espere a gravação terminar. Baixe os arquivos pelo Python para verificar o SHA-256 e converter o registro em CSV.

## Campanha na passarela da UFPR

Identifique os vãos no sentido Botânico–Politécnico. P01 é o meio do vão A–B, e P02 é o meio do vão B–C. Use o meio de cada vão conforme verificado em campo: os comprimentos podem ser diferentes. Grave 1200 s em cada ponto e reserve, além dos 40 minutos de aquisição, tempo para preparar o conjunto, estabilizar a leitura, transferir os arquivos e mudar de posição.

Crie a campanha com `27_passarela_ufpr.py preparar --calibracao CAMINHO_DO_JSON`. Em P01, use `iniciar`, `status` e `baixar`. Confira o registro antes de passar a P02 e repetir a sequência. Ao final, `analisar` processa cada registro e reúne as frequências candidatas. O [guia de campo](docs/GUIA_CAMPO_PASSARELA_UFPR.md) traz os comandos e o esquema da campanha.

O firmware v4.0 já aceita registros de 1200 s e funciona com o roteiro em Python. Grave o v4.1 se quiser usar os atalhos de P01 e P02 na página do nó. Para salvar o andamento e retomar a campanha, use o script `27_passarela_ufpr.py`.

### Como são identificadas as frequências

O método principal procura picos na densidade espectral de potência (PSD) de Welch e verifica quais persistem em diferentes blocos do registro. A FDD usa as três componentes simultâneas em cada ponto para complementar essa análise. As frequências são **candidatas**, e os vetores da FDD descrevem a relação entre os canais medidos naquele ponto. Como os registros de P01 e P02 são sucessivos, eles não são combinados como canais sincronizados. O pacote não estima formas modais espaciais, MAC espacial ou amortecimento automático.

## Programas de campo e comparação

| Script | O que faz |
| --- | --- |
| `17_controlar_campanha.py` | Inicia aquisições, consulta o estado, marca eventos e baixa registros pela rede do nó |
| `18_importar_referencia.py` | Converte a exportação do instrumento de referência em tempo numérico e unidades SI |
| `19_ajustar_tempo.py` | Estima a diferença de origem e de taxa entre os relógios usando marcas correspondentes |
| `20_analisar_shaker.py` | Compara frequência e amplitude senoidal em regime estacionário |
| `21_comparar_trelica.py` | Compara a resposta ao impacto e os espectros; com alinhamento temporal, compara também os sinais no tempo |
| `22_identificar_passarela.py` | Procura picos com PP/Welch, verifica a persistência por blocos e aplica FDD local |
| `23_consolidar_frequencias.py` | Reúne as frequências candidatas entre posições e repetições para revisão |
| `24_resumir_shaker.py` | Reúne as repetições por frequência e nível |
| `25_extrair_marcas.py` | Localiza no log os tempos das marcas físicas |
| `26_analisar_frf_martelo.py` | Calcula a FRF H1 quando há força medida; usa a média de pelo menos três impactos |
| `27_passarela_ufpr.py` | Prepara, comanda, retoma e analisa a campanha de 1200 s por ponto em P01 e P02 |

Os scripts de 00 a 16 são os de bancada. O [guia de bancada](docs/BANCADA.md) explica a captura, a conversão, a calibração matricial, a validação e as análises de ruído, repetibilidade, temporização, deriva, dinâmica e Allan.

## Referência, resultados e verificações

O shaker e o sistema de aquisição profissional são operados separadamente. Para importar os dados de referência, preencha `fichas/mapa_referencia.json` de acordo com as colunas, a escala e as unidades da exportação real.

Cada download e análise recebe uma pasta própria com data, hora, microssegundos e identificador aleatório. Guarde os novos resultados junto aos metadados. Para experimentar o software sem o nó, siga as [instruções de geração local](exemplos/LEIA_ME.md).

O pacote reúne testes numéricos, testes de integridade com transferência simulada e uma checagem de sintaxe C++ com interfaces de teste. Antes de medir em campo, compile com as ferramentas da Espressif e confira a gravação e a aquisição na placa.
