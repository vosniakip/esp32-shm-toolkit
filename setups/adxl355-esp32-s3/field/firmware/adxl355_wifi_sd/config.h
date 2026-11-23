#pragma once
// Edite somente com o conjunto desligado. GPIOs sao numeros logicos, nao posicoes do conector.
constexpr int SENSOR_CS=10, SENSOR_MOSI=11, SENSOR_SCK=12, SENSOR_MISO=13, SENSOR_DRDY=14;
constexpr int CARD_CS=15, CARD_SCK=16, CARD_MOSI=17, CARD_MISO=18;
// GPIO19/20 permanecem livres para USB nativo.
constexpr unsigned SENSOR_SPI_HZ=4000000, CARD_SPI_HZ=4000000;
constexpr unsigned SERIAL_BAUD=115200;
constexpr unsigned SAMPLE_QUEUE_LENGTH=2048; // 64 KiB de registros; nao exige PSRAM.
constexpr unsigned IRQ_QUEUE_LENGTH=128;
constexpr unsigned BLOCK_RECORDS=128;
constexpr unsigned MAX_DURATION_S=21600; // 6 h; a 500 Hz, aproximadamente 346 MB.
constexpr unsigned MAX_REPETITIONS=20;
constexpr unsigned SETTLING_US=100000;
constexpr char AP_SSID[]="ADXL355-ENSAIOS";
constexpr char AP_PASSWORD[]="Ensaio355!"; // Troque antes de usar fora da bancada (8-63 caracteres).
constexpr char DEFAULT_NODE[]="adxl355-01";
constexpr char DEFAULT_MOUNT[]="pcb-inclinada-v1";
constexpr char FW_VERSION[]="4.1.0";
constexpr char RAW_FORMAT[]="ADXL355_SD_V3";
static_assert(SAMPLE_QUEUE_LENGTH>=256, "Buffer insuficiente");
static_assert(sizeof(AP_PASSWORD)-1>=8 && sizeof(AP_PASSWORD)-1<=63,"Senha Wi-Fi deve ter 8-63 caracteres");

// Marca externa opcional: DESATIVADA. Antes de ativar, confira o manual da DAQ.
// Aceita somente pulso digital compativel com 3,3 V, com terra comum apropriado.
// Este sinal marca o tempo no ESP32; NAO disciplina o relogio do ADXL355.
constexpr bool ENABLE_SYNC_INPUT=false;
constexpr int SYNC_GPIO=4;
constexpr unsigned MAX_MARKERS=128;
